from dataclasses import dataclass

from .const import ResponseCode, ServiceCode, StatusCode


@dataclass(frozen=True, slots=True)
class PaymentItem:
    name: str
    quantity: int
    total_price: int


@dataclass(frozen=True, slots=True)
class CardInfo:
    serial_number: str
    acquirer_id: str
    acquirer_name: str
    issuer_id: str
    issuer_name: str
    merchant_id: str
    date_time: str


@dataclass(frozen=True, slots=True)
class DeviceInitiatedRequest:
    service_code: ServiceCode
    rfid_data: str | None = None


@dataclass(frozen=True, slots=True)
class TokenGenerationResult:
    status: StatusCode
    vankey_hash: str | None
    card_info: CardInfo | None
    response_code: ResponseCode
    message: str


@dataclass(frozen=True, slots=True)
class TokenApprovalResult:
    status: StatusCode
    authorization_number: str | None
    card_info: CardInfo | None
    vankey: str | None
    response_code: ResponseCode
    message: str


@dataclass(frozen=True, slots=True)
class TokenCancelResult:
    status: StatusCode
    card_info: CardInfo | None
    vankey: str | None
    response_code: ResponseCode
    message: str


@dataclass(frozen=True, slots=True)
class SamsungPayApprovalResult:
    status: StatusCode
    authorization_number: str | None
    card_info: CardInfo | None
    vankey: str | None
    response_code: ResponseCode
    message: str


@dataclass(frozen=True, slots=True)
class SamsungPayCancelResult:
    status: StatusCode
    card_info: CardInfo | None
    vankey: str | None
    response_code: ResponseCode
    message: str


@dataclass(frozen=True, slots=True)
class DeviceCheckResult:
    response_code: ResponseCode
