from construct import (
    Bytes,
    Const,
    GreedyBytes,
    GreedyString,
    NullTerminated,
    PaddedString,
    Select,
    Struct,
)

from .const import FS, RS
from .structure import (
    AuthorizationTypeField,
    ResponseCodeField,
    StatusCodeField,
)


def _terminated_string(encoding, terminator):
    return NullTerminated(GreedyString(encoding), term=terminator)


def _terminated_bytes(terminator):
    return NullTerminated(GreedyBytes, term=terminator)


# Common payload structures

ErrorPayload = Struct(
    "status" / Const(b"N"),
    Const(FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)

CardInfo = Struct(
    "serial_number" / _terminated_string("ascii", RS),
    "acquirer_id" / _terminated_string("ascii", RS),
    "acquirer_name" / _terminated_string("euc-kr", RS),
    "issuer_id" / _terminated_string("ascii", RS),
    "issuer_name" / _terminated_string("euc-kr", RS),
    "merchant_id" / _terminated_string("ascii", RS),
    "date_time" / GreedyString("ascii"),
)

ItemInfo = Struct(
    "name" / Bytes(10),
    "quantity" / Bytes(2),
    "total_price" / Bytes(6),
)


# Age check

AgeCheckRequest = Struct(
    Const(FS),
)

AgeCheckResponse = Struct(
    Const(FS),
    "qr_data" / _terminated_bytes(FS),
    "message" / _terminated_string("euc-kr", FS),
)


# Token transactions

TransactionTokenInitializeRequest = Struct(
    Const(FS),
)

TransactionTokenInitializeResponse = Struct(
    Const(FS),
    "message" / _terminated_string("euc-kr", FS),
)

TransactionTokenGenerateRequest = Struct(
    "message" / _terminated_string("euc-kr", FS),
)

TransactionTokenGenerateResponse = Struct(
    "status" / StatusCodeField,
    Const(FS),
    "vankey_hash" / _terminated_string("ascii", FS),
    "card_info" / NullTerminated(Select(CardInfo, GreedyString("ascii")), term=FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)

TransactionTokenApproveRequest = Struct(
    "amount" / _terminated_string("ascii", FS),
    "vankey_hash" / _terminated_string("ascii", FS),
    "message" / _terminated_bytes(FS),
)

TransactionTokenApproveResponse = Struct(
    "status" / StatusCodeField,
    Const(FS),
    "authorization_number" / _terminated_string("ascii", FS),
    "card_info" / NullTerminated(Select(CardInfo, GreedyString("ascii")), term=FS),
    "vankey" / _terminated_string("ascii", FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)

TransactionTokenCancelRequest = Struct(
    "amount" / _terminated_string("ascii", FS),
    "original_authorization_number" / PaddedString(8, "ascii"),
    Const(FS),
    "original_authorization_date" / PaddedString(6, "ascii"),
    Const(FS),
    "vankey_hash" / PaddedString(24, "ascii"),
    Const(FS),
)

TransactionTokenCancelResponse = Struct(
    "status" / StatusCodeField,
    Const(FS),
    "card_info" / NullTerminated(Select(CardInfo, GreedyString("ascii")), term=FS),
    "vankey" / _terminated_string("ascii", FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)


# RFID

TransactionRFIDInitializeRequest = Struct(
    "data" / PaddedString(10, "ascii"),
    Const(FS),
)


# Samsung Pay transactions

TransactionSPayInitializeRequest = Struct(
    Const(FS),
)

TransactionSPayInitializeResponse = Struct(
    Const(FS),
    "message" / _terminated_string("euc-kr", FS),
)

TransactionSPayApproveRequest = Struct(
    "amount" / _terminated_string("ascii", FS),
    "authorization_type" / AuthorizationTypeField,
    Const(FS),
    "message" / _terminated_bytes(FS),
)

TransactionSPayApproveResponse = Struct(
    "status" / StatusCodeField,
    Const(FS),
    "authorization_number" / _terminated_string("ascii", FS),
    "vankey" / _terminated_string("ascii", FS),
    "card_info" / NullTerminated(Select(CardInfo, GreedyString("ascii")), term=FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)

TransactionSPayCancelRequest = Struct(
    "amount" / _terminated_string("ascii", FS),
    "original_authorization_number" / PaddedString(8, "ascii"),
    Const(FS),
    "original_authorization_date" / PaddedString(6, "ascii"),
    Const(FS),
    "vankey" / PaddedString(16, "ascii"),
    Const(FS),
)

TransactionSPayCancelResponse = Struct(
    "status" / StatusCodeField,
    Const(FS),
    "card_info" / NullTerminated(Select(CardInfo, GreedyString("ascii")), term=FS),
    "vankey" / _terminated_string("ascii", FS),
    "response_code" / ResponseCodeField,
    Const(RS),
    "message" / _terminated_string("euc-kr", FS),
)


# Device

DeviceCheckRequest = Struct(
    "message" / _terminated_string("euc-kr", FS),
)

DeviceCheckResponse = Struct(
    "response_code" / ResponseCodeField,
    Const(FS),
)
