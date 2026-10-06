import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from exceptions import CommunicationError, TimeoutError as PaymentTimeoutError
from payment.command import (
    send_device_check,
    send_tx_spay_approve,
    send_tx_spay_cancel,
    send_tx_token_approve,
    send_tx_token_cancel,
    send_tx_token_generate,
)
from payment.const import (
    AuthorizationType,
    ControlFrame,
    MessageType,
    ResponseCode,
    StatusCode,
)
from payment.manager import Communication, _read_frame
from payment.payload import (
    TransactionSPayApproveResponse,
    TransactionSPayCancelResponse,
    TransactionTokenApproveResponse,
    TransactionTokenCancelResponse,
    TransactionTokenGenerateResponse,
)
from payment.structure import FrameLength, ProtocolFrame


def build_protocol(service_code: str, message_type: MessageType) -> bytes:
    return ProtocolFrame.build(
        {
            "service_code": service_code,
            "message_type": message_type,
            "payload": b"",
        }
    )


async def read_protocol_bytes(reader: asyncio.StreamReader) -> bytes:
    stx = await reader.readexactly(1)
    length_bytes = await reader.readexactly(2)
    length = FrameLength.parse(length_bytes)
    remaining = await reader.readexactly(length - 3)
    return stx + length_bytes + remaining


class CommunicationHarness:
    def __init__(self, test_case: unittest.TestCase, handler):
        self.test_case = test_case
        self.handler = handler
        self.server = None
        self.comm = Communication()
        self.comm_task = None
        self.handler_done = None
        self.handler_tasks = set()

    async def __aenter__(self):
        loop = asyncio.get_running_loop()
        self.handler_done = loop.create_future()

        async def guarded_handler(reader, writer):
            handler_task = asyncio.current_task()
            self.handler_tasks.add(handler_task)
            try:
                result = await self.handler(reader, writer)
                if not self.handler_done.done():
                    self.handler_done.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self.handler_done.done():
                    self.handler_done.set_exception(exc)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        self.server = await asyncio.start_server(
            guarded_handler,
            "127.0.0.1",
            0,
        )
        port = self.server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        self.comm_task = asyncio.create_task(self.comm.run(reader, writer))

        for _ in range(20):
            if self.comm.writer is not None and not self.comm._connection_lost.is_set():
                break
            await asyncio.sleep(0)
        else:
            self.test_case.fail("Communication did not become connected")

        return self

    async def __aexit__(self, exc_type, exc, traceback):
        if self.comm_task is not None and not self.comm_task.done():
            self.comm._abort_connection("test cleanup")
            try:
                await asyncio.wait_for(
                    asyncio.shield(self.comm_task),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                self.comm_task.cancel()
                await asyncio.gather(self.comm_task, return_exceptions=True)
        elif self.comm_task is not None:
            await asyncio.gather(self.comm_task, return_exceptions=True)
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
        if self.handler_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.handler_tasks, return_exceptions=True),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                for task in self.handler_tasks:
                    task.cancel()
                await asyncio.gather(
                    *self.handler_tasks,
                    return_exceptions=True,
                )
        if self.handler_done is not None and not self.handler_done.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(self.handler_done),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                self.handler_done.cancel()
        if self.handler_done is not None and self.handler_done.done():
            handler_exception = (
                None
                if self.handler_done.cancelled()
                else self.handler_done.exception()
            )
            if handler_exception is not None and exc is None:
                raise handler_exception


class FrameReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_fragmented_control_and_coalesced_protocol(self):
        reader = asyncio.StreamReader()
        response = build_protocol("D8", MessageType.RESPONSE)

        control_task = asyncio.create_task(_read_frame(reader))
        reader.feed_data(b"\x06")
        await asyncio.sleep(0)
        reader.feed_data(b"\x06\x06" + response)

        self.assertEqual(await control_task, ControlFrame.ACK)
        parsed_response = await _read_frame(reader)
        self.assertEqual(parsed_response.service_code, "D8")
        self.assertEqual(parsed_response.message_type, MessageType.RESPONSE)

    async def test_rejects_malformed_control_frame(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b"\x06\x06\x04")

        with self.assertRaisesRegex(ValueError, "Invalid control frame"):
            await _read_frame(reader)


class PaymentHandshakeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_flow_waits_for_eot_before_returning(self):
        request = build_protocol("D8", MessageType.REQUEST)
        response = build_protocol("D8", MessageType.RESPONSE)
        response_ack_received = asyncio.Event()
        release_eot = asyncio.Event()
        received = []

        async def cat_handler(reader, writer):
            received.append(await reader.readexactly(3))
            writer.write(b"\x06")
            await writer.drain()
            await asyncio.sleep(0)
            writer.write(b"\x06\x06")
            await writer.drain()

            received.append(await read_protocol_bytes(reader))
            writer.write(response)
            await writer.drain()

            received.append(await reader.readexactly(3))
            response_ack_received.set()
            await release_eot.wait()
            writer.write(ControlFrame.EOT.value)
            await writer.drain()
            return received

        async with CommunicationHarness(self, cat_handler) as harness:
            fetch_task = asyncio.create_task(
                harness.comm.fetch(
                    request,
                    timeout=0.5,
                    control_handshake=True,
                )
            )
            await asyncio.wait_for(response_ack_received.wait(), timeout=0.5)
            self.assertFalse(fetch_task.done())

            release_eot.set()
            parsed_response = await asyncio.wait_for(fetch_task, timeout=0.5)
            self.assertEqual(parsed_response.service_code, "D8")
            self.assertEqual(
                received,
                [ControlFrame.ENQ.value, request, ControlFrame.ACK.value],
            )

    async def test_preflight_ack_timeout_does_not_send_request(self):
        request = build_protocol("D9", MessageType.REQUEST)

        async def cat_handler(reader, writer):
            enq = await reader.readexactly(3)
            remaining = await reader.read()
            return enq, remaining

        with patch("payment.manager.CONTROL_FRAME_TIMEOUT", 0.05):
            async with CommunicationHarness(self, cat_handler) as harness:
                with self.assertRaises(CommunicationError) as raised:
                    await harness.comm.fetch(
                        request,
                        timeout=0.5,
                        control_handshake=True,
                    )
                self.assertEqual(raised.exception.status, 503)
                enq, remaining = await asyncio.wait_for(
                    harness.handler_done,
                    timeout=0.5,
                )
                self.assertEqual(enq, ControlFrame.ENQ.value)
                self.assertEqual(remaining, b"")

    async def test_response_timeout_remains_gateway_timeout(self):
        request = build_protocol("D1", MessageType.REQUEST)

        async def cat_handler(reader, writer):
            enq = await reader.readexactly(3)
            writer.write(ControlFrame.ACK.value)
            await writer.drain()
            sent_request = await read_protocol_bytes(reader)
            await reader.read()
            return enq, sent_request

        async with CommunicationHarness(self, cat_handler) as harness:
            with self.assertRaises(PaymentTimeoutError) as raised:
                await harness.comm.fetch(
                    request,
                    timeout=0.05,
                    control_handshake=True,
                )
            self.assertEqual(raised.exception.status, 504)
            enq, sent_request = await asyncio.wait_for(
                harness.handler_done,
                timeout=0.5,
            )
            self.assertEqual(enq, ControlFrame.ENQ.value)
            self.assertEqual(sent_request, request)

    async def test_eot_timeout_discards_received_response(self):
        request = build_protocol("D8", MessageType.REQUEST)
        response = build_protocol("D8", MessageType.RESPONSE)

        async def cat_handler(reader, writer):
            await reader.readexactly(3)
            writer.write(ControlFrame.ACK.value)
            await writer.drain()
            await read_protocol_bytes(reader)
            writer.write(response)
            await writer.drain()
            response_ack = await reader.readexactly(3)
            await reader.read()
            return response_ack

        with patch("payment.manager.CONTROL_FRAME_TIMEOUT", 0.05):
            async with CommunicationHarness(self, cat_handler) as harness:
                with self.assertRaises(CommunicationError) as raised:
                    await harness.comm.fetch(
                        request,
                        timeout=0.5,
                        control_handshake=True,
                    )
                self.assertIn("EOT", raised.exception.detail)
                response_ack = await asyncio.wait_for(
                    harness.handler_done,
                    timeout=0.5,
                )
                self.assertEqual(response_ack, ControlFrame.ACK.value)

    async def test_out_of_order_control_frame_fails_transaction(self):
        request = build_protocol("TQ", MessageType.REQUEST)

        async def cat_handler(reader, writer):
            await reader.readexactly(3)
            writer.write(ControlFrame.EOT.value)
            await writer.drain()
            await reader.read()

        async with CommunicationHarness(self, cat_handler) as harness:
            with self.assertRaises(CommunicationError) as raised:
                await harness.comm.fetch(
                    request,
                    timeout=0.5,
                    control_handshake=True,
                )
            self.assertIn("Expected ACK", raised.exception.detail)

    async def test_malformed_control_frame_is_reported_as_communication_error(self):
        request = build_protocol("D8", MessageType.REQUEST)

        async def cat_handler(reader, writer):
            await reader.readexactly(3)
            writer.write(b"\x06\x06\x04")
            await writer.drain()
            await reader.read()

        async with CommunicationHarness(self, cat_handler) as harness:
            with self.assertLogs("payment.manager", level="ERROR"):
                with self.assertRaises(CommunicationError) as raised:
                    await harness.comm.fetch(
                        request,
                        timeout=0.5,
                        control_handshake=True,
                    )
            self.assertIn("Invalid control frame", raised.exception.detail)

    async def test_disconnect_is_reported_without_waiting_for_timeout(self):
        request = build_protocol("D7", MessageType.REQUEST)

        async def cat_handler(reader, writer):
            await reader.readexactly(3)
            return None

        with patch("payment.manager.CONTROL_FRAME_TIMEOUT", 1.0):
            async with CommunicationHarness(self, cat_handler) as harness:
                loop = asyncio.get_running_loop()
                started = loop.time()
                with self.assertRaises(CommunicationError):
                    await harness.comm.fetch(
                        request,
                        timeout=1.0,
                        control_handshake=True,
                    )
                self.assertLess(loop.time() - started, 0.5)

    async def test_non_handshake_fetch_starts_with_protocol_message(self):
        request = build_protocol("PC", MessageType.REQUEST)
        response = build_protocol("PC", MessageType.RESPONSE)

        async def cat_handler(reader, writer):
            sent_request = await read_protocol_bytes(reader)
            writer.write(response)
            await writer.drain()
            return sent_request

        async with CommunicationHarness(self, cat_handler) as harness:
            parsed_response = await harness.comm.fetch(request, timeout=0.5)
            self.assertEqual(parsed_response.service_code, "PC")
            sent_request = await asyncio.wait_for(
                harness.handler_done,
                timeout=0.5,
            )
            self.assertEqual(sent_request, request)

    async def test_concurrent_transactions_do_not_interleave(self):
        first_request = build_protocol("D8", MessageType.REQUEST)
        second_request = build_protocol("D9", MessageType.REQUEST)
        first_response = build_protocol("D8", MessageType.RESPONSE)
        second_response = build_protocol("D9", MessageType.RESPONSE)
        received = []

        async def cat_handler(reader, writer):
            for response in (first_response, second_response):
                received.append(await reader.readexactly(3))
                writer.write(ControlFrame.ACK.value)
                await writer.drain()
                received.append(await read_protocol_bytes(reader))
                writer.write(response)
                await writer.drain()
                received.append(await reader.readexactly(3))
                writer.write(ControlFrame.EOT.value)
                await writer.drain()
            return received

        async with CommunicationHarness(self, cat_handler) as harness:
            first_task = asyncio.create_task(
                harness.comm.fetch(
                    first_request,
                    timeout=0.5,
                    control_handshake=True,
                )
            )
            await asyncio.sleep(0)
            second_task = asyncio.create_task(
                harness.comm.fetch(
                    second_request,
                    timeout=0.5,
                    control_handshake=True,
                )
            )
            first_result, second_result = await asyncio.gather(
                first_task,
                second_task,
            )

            self.assertEqual(first_result.service_code, "D8")
            self.assertEqual(second_result.service_code, "D9")
            self.assertEqual(
                received,
                [
                    ControlFrame.ENQ.value,
                    first_request,
                    ControlFrame.ACK.value,
                    ControlFrame.ENQ.value,
                    second_request,
                    ControlFrame.ACK.value,
                ],
            )


class WriteCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_response_ack_write_failure_is_communication_error(self):
        class FailingWriter:
            def __init__(self):
                self.messages = []
                self.closed = False

            def write(self, message):
                self.messages.append(message)

            async def drain(self):
                raise OSError("write failed")

            def is_closing(self):
                return self.closed

        comm = Communication()
        comm.writer = FailingWriter()
        comm._connection_lost = asyncio.Event()
        comm.writing_task = asyncio.create_task(comm._write())

        try:
            with self.assertRaises(CommunicationError) as raised:
                await comm._send(
                    ControlFrame.ACK.value,
                    service_code="D8",
                    phase="response_ack",
                    timeout=0.5,
                )
            self.assertIn("response_ack", raised.exception.detail)
            self.assertEqual(comm.writer.messages, [ControlFrame.ACK.value])
        finally:
            comm.writing_task.cancel()
            await asyncio.gather(comm.writing_task, return_exceptions=True)


class CommandHandshakeSelectionTests(unittest.IsolatedAsyncioTestCase):
    class FetchCalled(Exception):
        pass

    async def assert_handshake_enabled(self, command, **kwargs):
        comm = AsyncMock()
        comm.fetch.side_effect = self.FetchCalled

        with self.assertRaises(self.FetchCalled):
            await command(comm=comm, **kwargs)

        self.assertTrue(comm.fetch.await_args.kwargs["control_handshake"])

    async def test_handshake_enabled_for_all_revised_service_codes(self):
        await self.assert_handshake_enabled(send_tx_token_generate)
        await self.assert_handshake_enabled(
            send_tx_token_approve,
            amount="1000",
            vankey_hash="V" * 24,
            items=[],
        )
        await self.assert_handshake_enabled(
            send_tx_token_cancel,
            amount="1000",
            original_authorization_number="12345678",
            original_authorization_date="260101",
            vankey_hash="V" * 24,
        )
        await self.assert_handshake_enabled(
            send_tx_spay_approve,
            amount="1000",
            authorization_type=AuthorizationType.PURCHASE,
            items=[],
        )
        await self.assert_handshake_enabled(
            send_tx_spay_cancel,
            amount="1000",
            original_authorization_number="12345678",
            original_authorization_date="260101",
            vankey="V" * 16,
        )

    async def test_device_check_keeps_legacy_flow(self):
        comm = AsyncMock()
        comm.fetch.side_effect = self.FetchCalled

        with self.assertRaises(self.FetchCalled):
            await send_device_check(comm=comm)

        self.assertNotIn("control_handshake", comm.fetch.await_args.kwargs)


class PaymentRecoveryLoggingTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def response(service_code, payload):
        return ProtocolFrame.parse(
            ProtocolFrame.build(
                {
                    "service_code": service_code,
                    "message_type": MessageType.RESPONSE,
                    "payload": payload,
                }
            )
        )

    async def invoke_and_capture(self, command, response, **kwargs):
        comm = AsyncMock()
        comm.fetch.return_value = response
        with self.assertLogs("payment.command", level="INFO") as captured:
            await command(comm=comm, **kwargs)
        return "\n".join(captured.output)

    async def test_request_keys_are_logged_before_communication_failure(self):
        token_vankey_hash = "TOKENVANKEY00001HASH0001"
        samsung_vankey = "SPAYVANKEY000001"
        comm = AsyncMock()
        comm.fetch.side_effect = CommunicationError("network failed")

        with self.assertLogs("payment.command", level="INFO") as token_logs:
            with self.assertRaises(CommunicationError):
                await send_tx_token_approve(
                    comm=comm,
                    amount="1000",
                    vankey_hash=token_vankey_hash,
                    items=[],
                )
        token_output = "\n".join(token_logs.output)
        self.assertIn("phase=request", token_output)
        self.assertIn(f"vankey_hash={token_vankey_hash}", token_output)

        with self.assertLogs("payment.command", level="INFO") as spay_logs:
            with self.assertRaises(CommunicationError):
                await send_tx_spay_cancel(
                    comm=comm,
                    amount="1000",
                    original_authorization_number="87654321",
                    original_authorization_date="260101",
                    vankey=samsung_vankey,
                )
        spay_output = "\n".join(spay_logs.output)
        self.assertIn("phase=request", spay_output)
        self.assertIn(f"vankey={samsung_vankey}", spay_output)

    async def test_recovery_logs_include_full_vankey_and_vankey_hash(self):
        token_vankey_hash = "TOKENVANKEY00001HASH0001"
        token_vankey = "TOKENVANKEY00001"
        samsung_vankey = "SPAYVANKEY000001"

        token_generate_payload = TransactionTokenGenerateResponse.build(
            {
                "status": StatusCode.Y,
                "vankey_hash": token_vankey_hash,
                "card_info": "",
                "response_code": ResponseCode.SUCCESS,
                "message": "ok",
            }
        )
        token_generate_logs = await self.invoke_and_capture(
            send_tx_token_generate,
            self.response("TQ", token_generate_payload),
        )
        self.assertIn("PAYMENT_RECOVERY service_code=TQ", token_generate_logs)
        self.assertIn(f"vankey_hash={token_vankey_hash}", token_generate_logs)

        token_approve_payload = TransactionTokenApproveResponse.build(
            {
                "status": StatusCode.Y,
                "authorization_number": "12345678",
                "card_info": "",
                "vankey": token_vankey,
                "response_code": ResponseCode.SUCCESS,
                "message": "ok",
            }
        )
        token_approve_logs = await self.invoke_and_capture(
            send_tx_token_approve,
            self.response("D8", token_approve_payload),
            amount="1000",
            vankey_hash=token_vankey_hash,
            items=[],
        )
        self.assertIn(f"vankey={token_vankey}", token_approve_logs)
        self.assertIn(f"vankey_hash={token_vankey_hash}", token_approve_logs)
        self.assertIn("authorization_number=12345678", token_approve_logs)

        token_cancel_payload = TransactionTokenCancelResponse.build(
            {
                "status": StatusCode.Y,
                "card_info": "",
                "vankey": token_vankey,
                "response_code": ResponseCode.SUCCESS,
                "message": "ok",
            }
        )
        token_cancel_logs = await self.invoke_and_capture(
            send_tx_token_cancel,
            self.response("D9", token_cancel_payload),
            amount="1000",
            original_authorization_number="12345678",
            original_authorization_date="260101",
            vankey_hash=token_vankey_hash,
        )
        self.assertIn(f"vankey={token_vankey}", token_cancel_logs)
        self.assertIn(f"vankey_hash={token_vankey_hash}", token_cancel_logs)

        spay_approve_payload = TransactionSPayApproveResponse.build(
            {
                "status": StatusCode.Y,
                "authorization_number": "87654321",
                "vankey": samsung_vankey,
                "card_info": "",
                "response_code": ResponseCode.SUCCESS,
                "message": "ok",
            }
        )
        spay_approve_logs = await self.invoke_and_capture(
            send_tx_spay_approve,
            self.response("D1", spay_approve_payload),
            amount="1000",
            authorization_type=AuthorizationType.PURCHASE,
            items=[],
        )
        self.assertIn(f"vankey={samsung_vankey}", spay_approve_logs)
        self.assertIn("authorization_number=87654321", spay_approve_logs)

        spay_cancel_payload = TransactionSPayCancelResponse.build(
            {
                "status": StatusCode.Y,
                "card_info": "",
                "vankey": samsung_vankey,
                "response_code": ResponseCode.SUCCESS,
                "message": "ok",
            }
        )
        spay_cancel_logs = await self.invoke_and_capture(
            send_tx_spay_cancel,
            self.response("D7", spay_cancel_payload),
            amount="1000",
            original_authorization_number="87654321",
            original_authorization_date="260101",
            vankey=samsung_vankey,
        )
        self.assertIn(f"vankey={samsung_vankey}", spay_cancel_logs)
        self.assertIn(f"response_vankey={samsung_vankey}", spay_cancel_logs)


if __name__ == "__main__":
    unittest.main()
