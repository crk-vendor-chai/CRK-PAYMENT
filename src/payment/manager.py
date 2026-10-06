import asyncio
import logging
from typing import Any

from construct import ConstructError

from exceptions import CommunicationError, TimeoutError as PaymentTimeoutError

from .const import (
    STX,
    ControlFrame,
    MessageType,
)
from .structure import FrameLength, ProtocolFrame

logger = logging.getLogger(__name__)

CONTROL_FRAME_TIMEOUT = 3.0


async def _read_and_parse(
    reader: asyncio.StreamReader,
    stx_byte: bytes | None = None,
):
    if stx_byte is None:
        stx_byte = await reader.readexactly(1)
    if stx_byte != STX:
        raise ValueError(f"Invalid STX byte: {stx_byte!r}")

    length_bytes = await reader.readexactly(2)
    try:
        length = FrameLength.parse(length_bytes)
    except ConstructError as e:
        raise ValueError(f"Length parse error: {e}") from e

    if length < 9:
        raise ValueError(f"Invalid protocol length: {length}")

    remaining_bytes = await reader.readexactly(length - 3)

    raw_request = stx_byte + length_bytes + remaining_bytes
    try:
        request = ProtocolFrame.parse(raw_request)
    except ConstructError as e:
        raise ValueError(f"Protocol parse error: {e}") from e

    return request


async def _read_frame(reader: asyncio.StreamReader):
    """Read one protocol message or one three-byte control frame."""
    first_byte = await reader.readexactly(1)
    if first_byte == STX:
        return await _read_and_parse(reader, stx_byte=first_byte)

    if first_byte in {b"\x04", b"\x05", b"\x06"}:
        raw_frame = first_byte + await reader.readexactly(2)
        try:
            return ControlFrame(raw_frame)
        except ValueError as e:
            raise ValueError(f"Invalid control frame: {raw_frame!r}") from e

    raise ValueError(f"Unknown frame prefix: {first_byte!r}")


class Communication:
    def __init__(self):
        self.reader = None
        self.writer = None

        self.reading_task = None
        self.writing_task = None

        self.rx_request_queue = asyncio.Queue()

        self.lock = asyncio.Lock()
        self.tx_request_queue = asyncio.Queue()
        self.rx_transaction_queue = asyncio.Queue()

        self._connection_lost = asyncio.Event()
        self._connection_lost.set()
        self._connection_error = "CAT device is not connected"
        self._pending_write_futures: set[asyncio.Future] = set()

    async def run(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._connection_error = None
        self._connection_lost = asyncio.Event()

        self._drain_queue(self.rx_transaction_queue)

        self.reading_task = asyncio.create_task(self._read())
        self.writing_task = asyncio.create_task(self._write())

        try:
            await asyncio.gather(self.reading_task, self.writing_task)
        except asyncio.CancelledError:
            raise
        except asyncio.IncompleteReadError as e:
            self._mark_connection_lost(
                "CAT connection closed before a complete frame was received"
            )
            logger.info(
                "CAT connection closed while reading: expected=%s received=%s",
                e.expected,
                len(e.partial),
            )
        except Exception as e:
            self._mark_connection_lost(f"CAT communication failed: {e}")
            logger.error("Error in CommunicationHandler: %s", e)
        finally:
            self._mark_connection_lost("CAT device connection closed")
            self.reading_task.cancel()
            self.writing_task.cancel()
            await asyncio.gather(
                self.reading_task, self.writing_task, return_exceptions=True
            )
            self._fail_pending_writes("CAT device connection closed")
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            if self.writer is writer:
                self.reader = None
                self.writer = None

    async def _read(self):
        if self.reader is None:
            raise RuntimeError("Reader not initialized")

        try:
            while True:
                frame = await _read_frame(self.reader)

                if isinstance(frame, ControlFrame):
                    logger.debug(
                        "Received CAT control frame",
                        extra={"control_frame": frame.name},
                    )
                    await self.rx_transaction_queue.put(frame)
                    continue

                logger.debug(
                    "Received CAT protocol message",
                    extra={
                        "service_code": frame.service_code,
                        "message_type": frame.message_type.value.decode("ascii"),
                    },
                )

                if frame.message_type == MessageType.REQUEST:
                    await self.rx_request_queue.put(frame)
                else:
                    await self.rx_transaction_queue.put(frame)
        finally:
            logger.info("Closing reading task")

    async def _write(self):
        if self.writer is None:
            raise RuntimeError("Writer not initialized")

        try:
            while True:
                message, completion, service_code, phase = (
                    await self.tx_request_queue.get()
                )
                try:
                    logger.debug(
                        "Transmitting CAT frame",
                        extra={"service_code": service_code, "phase": phase},
                    )

                    self.writer.write(message)
                    await self.writer.drain()
                    if not completion.done():
                        completion.set_result(None)
                except asyncio.CancelledError:
                    if not completion.done():
                        completion.set_exception(
                            CommunicationError("CAT writer stopped before drain completed")
                        )
                    raise
                except Exception as e:
                    if not completion.done():
                        completion.set_exception(e)
                    self._mark_connection_lost(f"CAT write failed: {e}")
                    raise
        finally:
            logger.info("Closing writing task")

    async def read_request(self):
        return await self.rx_request_queue.get()

    async def fetch(
        self,
        message,
        timeout: float | None = None,
        control_handshake: bool = False,
    ):
        """
        Send a request and wait for response with timeout.
        
        Args:
            message: Protocol message to send
            timeout: Timeout in seconds (uses settings.comm_timeout if None)
            control_handshake: Whether to use the ENQ/ACK/response/ACK/EOT flow
            
        Returns:
            Protocol response message
            
        Raises:
            TimeoutError: If response not received within timeout
            CommunicationError: If communication fails
        """
        from config import settings

        if timeout is None:
            timeout = settings.comm_timeout

        service_code = self._service_code(message)

        async with self.lock:
            self._ensure_connected(service_code)
            self._drain_queue(self.rx_transaction_queue)

            try:
                if control_handshake:
                    self._log_phase(service_code, "enq")
                    await self._send(
                        ControlFrame.ENQ.value,
                        service_code=service_code,
                        phase="enq",
                        timeout=CONTROL_FRAME_TIMEOUT,
                    )
                    await self._expect_control(
                        ControlFrame.ACK,
                        service_code=service_code,
                        phase="enq_ack",
                    )

                self._log_phase(service_code, "request")
                await self._send(
                    message,
                    service_code=service_code,
                    phase="request",
                    timeout=timeout,
                )

                self._log_phase(service_code, "response")
                response = await self._receive_response(
                    timeout=timeout,
                    service_code=service_code,
                )

                if control_handshake:
                    self._log_phase(service_code, "response_ack")
                    await self._send(
                        ControlFrame.ACK.value,
                        service_code=service_code,
                        phase="response_ack",
                        timeout=CONTROL_FRAME_TIMEOUT,
                    )
                    await self._expect_control(
                        ControlFrame.EOT,
                        service_code=service_code,
                        phase="eot",
                    )

                return response
            except PaymentTimeoutError:
                if control_handshake:
                    self._abort_connection(
                        f"CAT response timeout for service {service_code}"
                    )
                raise
            except CommunicationError:
                self._abort_connection(
                    f"CAT handshake failed for service {service_code}"
                )
                raise

    async def _send(
        self,
        message: bytes,
        *,
        service_code: str,
        phase: str,
        timeout: float,
    ) -> None:
        self._ensure_connected(service_code)
        loop = asyncio.get_running_loop()
        completion = loop.create_future()
        self._pending_write_futures.add(completion)
        completion.add_done_callback(self._pending_write_futures.discard)

        await self.tx_request_queue.put(
            (message, completion, service_code, phase)
        )

        try:
            await asyncio.wait_for(asyncio.shield(completion), timeout=timeout)
        except asyncio.TimeoutError as e:
            completion.cancel()
            raise CommunicationError(
                f"CAT write did not complete during {phase} within {timeout} seconds"
            ) from e
        except asyncio.CancelledError:
            completion.cancel()
            raise
        except Exception as e:
            raise CommunicationError(
                f"Failed to write CAT frame during {phase}: {e}"
            ) from e

    async def _receive_response(self, *, timeout: float, service_code: str):
        try:
            frame = await self._receive_transaction_frame(timeout)
        except asyncio.TimeoutError as e:
            raise PaymentTimeoutError(
                f"Device did not respond within {timeout} seconds",
                timeout=timeout,
            ) from e

        if isinstance(frame, ControlFrame):
            raise CommunicationError(
                "Unexpected control frame "
                f"{frame.name} while waiting for {service_code} response"
            )
        return frame

    async def _expect_control(
        self,
        expected: ControlFrame,
        *,
        service_code: str,
        phase: str,
    ) -> None:
        self._log_phase(service_code, phase)
        try:
            frame = await self._receive_transaction_frame(
                CONTROL_FRAME_TIMEOUT
            )
        except asyncio.TimeoutError as e:
            raise CommunicationError(
                f"CAT did not send {expected.name} during {phase} "
                f"within {CONTROL_FRAME_TIMEOUT} seconds"
            ) from e

        if frame != expected:
            received = frame.name if isinstance(frame, ControlFrame) else "response"
            raise CommunicationError(
                f"Expected {expected.name} during {phase}, received {received}"
            )

    async def _receive_transaction_frame(self, timeout: float) -> Any:
        connection_lost = self._connection_lost
        frame_task = asyncio.create_task(self.rx_transaction_queue.get())
        disconnect_task = asyncio.create_task(connection_lost.wait())

        try:
            done, _ = await asyncio.wait(
                {frame_task, disconnect_task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if frame_task in done:
                return frame_task.result()
            if disconnect_task in done:
                raise CommunicationError(
                    self._connection_error or "CAT device connection closed"
                )
            raise asyncio.TimeoutError
        finally:
            for task in (frame_task, disconnect_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                frame_task, disconnect_task, return_exceptions=True
            )

    def _ensure_connected(self, service_code: str) -> None:
        if (
            self.writer is None
            or self.writer.is_closing()
            or self._connection_lost.is_set()
        ):
            raise CommunicationError(
                f"CAT device is not connected for service {service_code}"
            )

    def _mark_connection_lost(self, detail: str) -> None:
        if not self._connection_lost.is_set():
            self._connection_error = detail
            self._connection_lost.set()

    def _abort_connection(self, detail: str) -> None:
        self._mark_connection_lost(detail)
        if self.writer is not None and not self.writer.is_closing():
            self.writer.close()

    def _fail_pending_writes(self, detail: str) -> None:
        while True:
            try:
                _, completion, _, _ = self.tx_request_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if not completion.done():
                completion.set_exception(CommunicationError(detail))

        for completion in tuple(self._pending_write_futures):
            if not completion.done():
                completion.set_exception(CommunicationError(detail))

    @staticmethod
    def _drain_queue(queue: asyncio.Queue) -> None:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @staticmethod
    def _service_code(message: bytes) -> str:
        try:
            return message[3:5].decode("ascii")
        except (AttributeError, UnicodeDecodeError):
            return "unknown"

    @staticmethod
    def _log_phase(service_code: str, phase: str) -> None:
        logger.debug(
            "CAT transaction phase",
            extra={"service_code": service_code, "phase": phase},
        )
