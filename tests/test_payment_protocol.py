import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import AsyncMock

from construct import ConstructError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api.schemas import CardInfoData, TokenGeneratedStream
from payment.command import (
    retrieve_request,
    send_device_check,
    send_tx_spay_approve,
    send_tx_spay_cancel,
    send_tx_token_approve,
    send_tx_token_cancel,
    send_tx_token_generate,
)
from payment.const import (
    AuthorizationType,
    MessageType,
    ResponseCode,
    StatusCode,
)
from payment.models import (
    CardInfo as CardInfoModel,
    DeviceCheckResult,
    DeviceInitiatedRequest,
    PaymentItem,
    SamsungPayApprovalResult,
    SamsungPayCancelResult,
    TokenApprovalResult,
    TokenCancelResult,
    TokenGenerationResult,
)
from payment.payload import (
    AgeCheckRequest,
    AgeCheckResponse,
    CardInfo,
    DeviceCheckRequest,
    DeviceCheckResponse,
    ErrorPayload,
    ItemInfo,
    TransactionRFIDInitializeRequest,
    TransactionSPayApproveRequest,
    TransactionSPayApproveResponse,
    TransactionSPayCancelRequest,
    TransactionSPayCancelResponse,
    TransactionSPayInitializeRequest,
    TransactionSPayInitializeResponse,
    TransactionTokenApproveRequest,
    TransactionTokenApproveResponse,
    TransactionTokenCancelRequest,
    TransactionTokenCancelResponse,
    TransactionTokenGenerateRequest,
    TransactionTokenGenerateResponse,
    TransactionTokenInitializeRequest,
    TransactionTokenInitializeResponse,
)
from payment.structure import (
    AuthorizationTypeField,
    FrameLength,
    MessageTypeField,
    ProtocolFrame,
    ResponseCodeField,
    StatusCodeField,
)


class ProtocolFieldTests(unittest.TestCase):
    def test_enum_fields_round_trip_every_member(self):
        fields = (
            (MessageTypeField, MessageType),
            (ResponseCodeField, ResponseCode),
            (StatusCodeField, StatusCode),
            (AuthorizationTypeField, AuthorizationType),
        )

        for field, enum_type in fields:
            for member in enum_type:
                with self.subTest(field=field, member=member):
                    raw = member.value
                    if isinstance(raw, int):
                        raw = bytes([raw])
                    self.assertEqual(field.build(member), raw)
                    self.assertEqual(field.parse(raw), member)

    def test_bcd_frame_length(self):
        self.assertEqual(FrameLength.build(0), b"\x00\x00")
        self.assertEqual(FrameLength.build(1234), b"\x12\x34")
        self.assertEqual(FrameLength.parse(b"\x99\x99"), 9999)

    def test_protocol_frame_matches_golden_bytes(self):
        raw = ProtocolFrame.build(
            {
                "service_code": "D8",
                "message_type": MessageType.REQUEST,
                "payload": b"",
            }
        )

        self.assertEqual(raw, b"\x02\x00\x09D810\x03\x77")
        parsed = ProtocolFrame.parse(raw)
        self.assertEqual(parsed.service_code, "D8")
        self.assertEqual(parsed.message_type, MessageType.REQUEST)
        self.assertEqual(parsed.payload, b"")

    def test_protocol_frame_rejects_bad_checksum(self):
        raw = ProtocolFrame.build(
            {
                "service_code": "D8",
                "message_type": MessageType.REQUEST,
                "payload": b"",
            }
        )
        corrupted = raw[:-1] + bytes([raw[-1] ^ 0xFF])

        with self.assertRaises(ConstructError):
            ProtocolFrame.parse(corrupted)


class PayloadCompatibilityTests(unittest.TestCase):
    def test_all_payloads_match_golden_bytes_and_round_trip(self):
        card_info = {
            "serial_number": "SN",
            "acquirer_id": "A1",
            "acquirer_name": "매입",
            "issuer_id": "I1",
            "issuer_name": "발급",
            "merchant_id": "M1",
            "date_time": "260101120000",
        }
        vankey_hash = "V" * 24

        cases = (
            (
                ErrorPayload,
                {
                    "response_code": ResponseCode.SERVICE_UNAVAILABLE,
                    "message": "오류",
                },
                b"N\x1c\xb4\x1e" + "오류".encode("euc-kr") + b"\x1c",
            ),
            (
                CardInfo,
                card_info,
                b"SN\x1eA1\x1e"
                + "매입".encode("euc-kr")
                + b"\x1eI1\x1e"
                + "발급".encode("euc-kr")
                + b"\x1eM1\x1e260101120000",
            ),
            (
                ItemInfo,
                {
                    "name": b"0123456789",
                    "quantity": b"01",
                    "total_price": b"001000",
                },
                b"012345678901001000",
            ),
            (AgeCheckRequest, {}, b"\x1c"),
            (
                AgeCheckResponse,
                {"qr_data": b"QR", "message": "ok"},
                b"\x1cQR\x1cok\x1c",
            ),
            (TransactionTokenInitializeRequest, {}, b"\x1c"),
            (
                TransactionTokenInitializeResponse,
                {"message": "ok"},
                b"\x1cok\x1c",
            ),
            (TransactionTokenGenerateRequest, {"message": ""}, b"\x1c"),
            (
                TransactionTokenGenerateResponse,
                {
                    "status": StatusCode.Y,
                    "vankey_hash": vankey_hash,
                    "card_info": "",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                },
                b"Y\x1c" + vankey_hash.encode() + b"\x1c\x1c\x00\x1eok\x1c",
            ),
            (
                TransactionTokenApproveRequest,
                {"amount": "1000", "vankey_hash": vankey_hash, "message": b"I"},
                b"1000\x1c" + vankey_hash.encode() + b"\x1cI\x1c",
            ),
            (
                TransactionTokenApproveResponse,
                {
                    "status": StatusCode.Y,
                    "authorization_number": "12345678",
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                },
                b"Y\x1c12345678\x1c\x1cVK\x1c\x00\x1eok\x1c",
            ),
            (
                TransactionTokenCancelRequest,
                {
                    "amount": "1000",
                    "original_authorization_number": "12345678",
                    "original_authorization_date": "260101",
                    "vankey_hash": vankey_hash,
                },
                b"1000\x1c12345678\x1c260101\x1c"
                + vankey_hash.encode()
                + b"\x1c",
            ),
            (
                TransactionTokenCancelResponse,
                {
                    "status": StatusCode.Y,
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                },
                b"Y\x1c\x1cVK\x1c\x00\x1eok\x1c",
            ),
            (
                TransactionRFIDInitializeRequest,
                {"data": "0123456789"},
                b"0123456789\x1c",
            ),
            (TransactionSPayInitializeRequest, {}, b"\x1c"),
            (
                TransactionSPayInitializeResponse,
                {"message": "ok"},
                b"\x1cok\x1c",
            ),
            (
                TransactionSPayApproveRequest,
                {
                    "amount": "1000",
                    "authorization_type": AuthorizationType.PURCHASE,
                    "message": b"I",
                },
                b"1000\x1c\x01\x1cI\x1c",
            ),
            (
                TransactionSPayApproveResponse,
                {
                    "status": StatusCode.Y,
                    "authorization_number": "12345678",
                    "vankey": "VK",
                    "card_info": "",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                },
                b"Y\x1c12345678\x1cVK\x1c\x1c\x00\x1eok\x1c",
            ),
            (
                TransactionSPayCancelRequest,
                {
                    "amount": "1000",
                    "original_authorization_number": "12345678",
                    "original_authorization_date": "260101",
                    "vankey": "V" * 16,
                },
                b"1000\x1c12345678\x1c260101\x1c" + b"V" * 16 + b"\x1c",
            ),
            (
                TransactionSPayCancelResponse,
                {
                    "status": StatusCode.Y,
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                },
                b"Y\x1c\x1cVK\x1c\x00\x1eok\x1c",
            ),
            (DeviceCheckRequest, {"message": ""}, b"\x1c"),
            (
                DeviceCheckResponse,
                {"response_code": ResponseCode.SUCCESS},
                b"\x00\x1c",
            ),
        )

        for schema, obj, expected in cases:
            with self.subTest(schema=schema):
                built = schema.build(obj)
                self.assertEqual(built, expected)
                self.assertEqual(schema.build(schema.parse(built)), expected)


class DomainBoundaryTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def protocol_response(service_code, payload):
        return ProtocolFrame.parse(
            ProtocolFrame.build(
                {
                    "service_code": service_code,
                    "message_type": MessageType.RESPONSE,
                    "payload": payload,
                }
            )
        )

    async def invoke(self, command, service_code, payload, **kwargs):
        comm = AsyncMock()
        comm.fetch.return_value = self.protocol_response(service_code, payload)
        return await command(comm=comm, **kwargs)

    async def test_commands_return_domain_dataclasses(self):
        card_info = {
            "serial_number": "SN",
            "acquirer_id": "A1",
            "acquirer_name": "매입사",
            "issuer_id": "I1",
            "issuer_name": "발급사",
            "merchant_id": "M1",
            "date_time": "260101120000",
        }
        token_generate = await self.invoke(
            send_tx_token_generate,
            "TQ",
            TransactionTokenGenerateResponse.build(
                {
                    "status": StatusCode.Y,
                    "vankey_hash": "V" * 24,
                    "card_info": card_info,
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                }
            ),
        )
        self.assertIsInstance(token_generate, TokenGenerationResult)
        self.assertIsInstance(token_generate.card_info, CardInfoModel)

        token_approval = await self.invoke(
            send_tx_token_approve,
            "D8",
            TransactionTokenApproveResponse.build(
                {
                    "status": StatusCode.Y,
                    "authorization_number": "12345678",
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                }
            ),
            amount="1000",
            vankey_hash="V" * 24,
            items=[PaymentItem(name="상품", quantity=1, total_price=1000)],
        )
        self.assertIsInstance(token_approval, TokenApprovalResult)

        token_cancel = await self.invoke(
            send_tx_token_cancel,
            "D9",
            TransactionTokenCancelResponse.build(
                {
                    "status": StatusCode.Y,
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                }
            ),
            amount="1000",
            original_authorization_number="12345678",
            original_authorization_date="260101",
            vankey_hash="V" * 24,
        )
        self.assertIsInstance(token_cancel, TokenCancelResult)

        spay_approval = await self.invoke(
            send_tx_spay_approve,
            "D1",
            TransactionSPayApproveResponse.build(
                {
                    "status": StatusCode.Y,
                    "authorization_number": "12345678",
                    "vankey": "VK",
                    "card_info": "",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                }
            ),
            amount="1000",
            authorization_type=AuthorizationType.PURCHASE,
            items=[PaymentItem(name="상품", quantity=1, total_price=1000)],
        )
        self.assertIsInstance(spay_approval, SamsungPayApprovalResult)

        spay_cancel = await self.invoke(
            send_tx_spay_cancel,
            "D7",
            TransactionSPayCancelResponse.build(
                {
                    "status": StatusCode.Y,
                    "card_info": "",
                    "vankey": "VK",
                    "response_code": ResponseCode.SUCCESS,
                    "message": "ok",
                }
            ),
            amount="1000",
            original_authorization_number="12345678",
            original_authorization_date="260101",
            vankey="V" * 16,
        )
        self.assertIsInstance(spay_cancel, SamsungPayCancelResult)

        device_check = await self.invoke(
            send_device_check,
            "PC",
            DeviceCheckResponse.build({"response_code": ResponseCode.SUCCESS}),
        )
        self.assertIsInstance(device_check, DeviceCheckResult)

    async def test_device_request_does_not_expose_construct_container(self):
        comm = AsyncMock()
        comm.read_request.return_value = ProtocolFrame.parse(
            ProtocolFrame.build(
                {
                    "service_code": "PR",
                    "message_type": MessageType.REQUEST,
                    "payload": TransactionRFIDInitializeRequest.build(
                        {"data": "0123456789"}
                    ),
                }
            )
        )

        request = await retrieve_request(comm)

        self.assertIsInstance(request, DeviceInitiatedRequest)
        self.assertEqual(request.rfid_data, "0123456789")

    def test_domain_models_are_frozen(self):
        card_info = CardInfoModel("SN", "A1", "매입", "I1", "발급", "M1", "DATE")
        result = TokenGenerationResult(
            status=StatusCode.Y,
            vankey_hash="V",
            card_info=card_info,
            response_code=ResponseCode.SUCCESS,
            message="ok",
        )

        with self.assertRaises(FrozenInstanceError):
            card_info.date_time = "CHANGED"
        with self.assertRaises(FrozenInstanceError):
            result.message = "CHANGED"

    def test_card_info_keeps_external_json_shape(self):
        card_info = CardInfoModel("SN", "A1", "매입", "I1", "발급", "M1", "DATE")
        expected = {
            "SERIAL_NUMBER": "SN",
            "ACQUIRER_ID": "A1",
            "ACQUIRER_NAME": "매입",
            "ISSUER_ID": "I1",
            "ISSUER_NAME": "발급",
            "MERCHANT_ID": "M1",
            "DATE_TIME": "DATE",
        }

        self.assertEqual(CardInfoData.model_validate(card_info).model_dump(), expected)
        stream = TokenGeneratedStream(
            status="Y",
            vankey_hash="V",
            card_info=card_info,
            response_code=ResponseCode.SUCCESS.value,
            message="ok",
        )
        self.assertEqual(stream.model_dump()["card_info"], expected)
