"""
Payment command layer for CAT device communication.

This module provides high-level functions for sending payment commands
to the CAT device and processing responses. All commands include:
- Input validation
- Configurable timeout
- Protocol validation
- Structured error handling
- Request/response logging

Timeout behavior:
- Uses COMM_TIMEOUT from config (default 120 seconds)
- Raises TimeoutError if device doesn't respond in time
- Can be overridden per-command if needed
"""

import logging
from collections.abc import Sequence

from construct import ConstructError

from exceptions import ProtocolError, ValidationError

from .const import (
    AuthorizationType,
    MessageType,
    ResponseCode,
    ServiceCode,
)
from .manager import Communication
from .models import (
    CardInfo,
    DeviceCheckResult,
    DeviceInitiatedRequest,
    PaymentItem,
    SamsungPayApprovalResult,
    SamsungPayCancelResult,
    TokenApprovalResult,
    TokenCancelResult,
    TokenGenerationResult,
)
from .payload import (
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
    TransactionTokenApproveRequest,
    TransactionTokenApproveResponse,
    TransactionTokenCancelRequest,
    TransactionTokenCancelResponse,
    TransactionTokenGenerateRequest,
    TransactionTokenGenerateResponse,
    TransactionTokenInitializeRequest,
)
from .structure import ProtocolFrame

logger = logging.getLogger(__name__)


def _to_card_info(card_info) -> CardInfo | None:
    if card_info is None or isinstance(card_info, str):
        return None
    return CardInfo(
        serial_number=card_info.serial_number,
        acquirer_id=card_info.acquirer_id,
        acquirer_name=card_info.acquirer_name,
        issuer_id=card_info.issuer_id,
        issuer_name=card_info.issuer_name,
        merchant_id=card_info.merchant_id,
        date_time=card_info.date_time,
    )


def _build_item_message(items: Sequence[PaymentItem]) -> bytes:
    chunks = []
    for item in items:
        name = item.name.encode("euc-kr", errors="ignore")[:10].ljust(10, b"\x00")
        quantity = str(item.quantity).encode("ascii")[:2].ljust(2, b"\x00")
        total_price = str(item.total_price).encode("ascii")[:6].ljust(6, b"\x00")
        chunks.append(
            ItemInfo.build(
                {
                    "name": name,
                    "quantity": quantity,
                    "total_price": total_price,
                }
            )
        )
    return b"".join(chunks)


def _log_payment_recovery(service_code: ServiceCode, **fields) -> None:
    """Write unmasked payment identifiers needed for manual recovery."""
    field_text = " ".join(f"{name}={value}" for name, value in fields.items())
    logger.info(
        "PAYMENT_RECOVERY service_code=%s %s",
        service_code.value,
        field_text,
        extra={
            "payment_recovery": True,
            "service_code": service_code.value,
            **fields,
        },
    )


def _validate_amount(amount: str, field_name: str = "amount") -> None:
    """
    Validate amount field format.
    
    Args:
        amount: Amount string to validate
        field_name: Name of field for error message
        
    Raises:
        ValidationError: If amount is invalid format
    """
    if not amount:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
        )
    
    if len(amount) < 1 or len(amount) > 9:
        raise ValidationError(
            f"{field_name} must be between 1 and 9 digits, got {len(amount)}",
            field=field_name,
            value=amount,
        )
    
    if not amount.isdigit():
        raise ValidationError(
            f"{field_name} must contain only digits 0-9",
            field=field_name,
            value=amount,
        )


def _validate_authorization_number(auth_number: str, field_name: str = "authorization_number") -> None:
    """
    Validate authorization number format.
    
    Args:
        auth_number: Authorization number to validate
        field_name: Name of field for error message
        
    Raises:
        ValidationError: If authorization number is invalid
    """
    if not auth_number:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
        )
    
    if len(auth_number) != 8:
        raise ValidationError(
            f"{field_name} must be exactly 8 characters, got {len(auth_number)}",
            field=field_name,
            value=auth_number,
        )


def _validate_authorization_date(auth_date: str, field_name: str = "authorization_date") -> None:
    """
    Validate authorization date format (YYMMDD).
    
    Args:
        auth_date: Authorization date to validate
        field_name: Name of field for error message
        
    Raises:
        ValidationError: If date is invalid format
    """
    if not auth_date:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
        )
    
    if len(auth_date) != 6:
        raise ValidationError(
            f"{field_name} must be YYMMDD format (6 digits), got {len(auth_date)}",
            field=field_name,
            value=auth_date,
        )
    
    if not auth_date.isdigit():
        raise ValidationError(
            f"{field_name} must contain only digits",
            field=field_name,
            value=auth_date,
        )


def _validate_response(
    response,
    expected_service_code: ServiceCode,
    expected_message_type: MessageType = MessageType.RESPONSE,
) -> None:
    """
    Validate protocol response matches expected values.
    
    Args:
        response: Protocol response object
        expected_service_code: Expected service code
        expected_message_type: Expected message type
        
    Raises:
        ProtocolError: If response doesn't match expected values
    """
    if response.service_code != expected_service_code.value:
        raise ProtocolError(
            f"Service code mismatch: expected {expected_service_code.value}, got {response.service_code}",
            expected=expected_service_code.value,
            received=response.service_code,
        )
    
    if response.message_type != expected_message_type:
        raise ProtocolError(
            f"Message type mismatch: expected {expected_message_type}, got {response.message_type}",
            expected=expected_message_type,
            received=response.message_type,
        )


async def retrieve_request(comm: Communication) -> DeviceInitiatedRequest:
    while True:
        message = await comm.read_request()

        if not message.service_code in ServiceCode:
            logger.error("Unknown service code: %s", message.service_code)
            continue

        service_code = ServiceCode(message.service_code)

        if service_code == ServiceCode.TX_TOKEN_INIT:
            payload_struct = TransactionTokenInitializeRequest
        elif service_code == ServiceCode.TX_SPAY_INIT:
            payload_struct = TransactionSPayInitializeRequest
        elif service_code == ServiceCode.TX_RFID_INIT:
            payload_struct = TransactionRFIDInitializeRequest
        else:
            logger.error("Service code %s not implemented yet", service_code)
            continue

        break

    payload = payload_struct.parse(message.payload)
    rfid_data = (
        payload.data
        if service_code == ServiceCode.TX_RFID_INIT
        else None
    )

    return DeviceInitiatedRequest(
        service_code=service_code,
        rfid_data=rfid_data,
    )


async def send_tx_token_generate(
    comm: Communication,
    timeout: float | None = None,
) -> TokenGenerationResult:
    """
    Request token generation from CAT device.
    
    Args:
        comm: Communication instance
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Token generation data with vankey_hash and card info
        
    Raises:
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    logger.debug("Sending TX_TOKEN_GENERATE request")
    
    request_payload = TransactionTokenGenerateRequest.build(
        {
            "message": "",
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.TX_TOKEN_GENERATE.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(
        request,
        timeout=timeout,
        control_handshake=True,
    )
    _validate_response(response, ServiceCode.TX_TOKEN_GENERATE)
    
    try:
        response_payload = TransactionTokenGenerateResponse.parse(response.payload)
    except ConstructError as e:       
        raise ProtocolError(
            response.payload.decode('euc-kr', errors='ignore')
        ) from e

    _log_payment_recovery(
        ServiceCode.TX_TOKEN_GENERATE,
        phase="response",
        vankey_hash=response_payload.vankey_hash,
        status=response_payload.status.name,
        response_code=response_payload.response_code.name,
    )
    
    logger.info(
        "Token generated",
        extra={
            "status": response_payload.status,
            "response_code": response_payload.response_code.name,
        },
    )
    
    return TokenGenerationResult(
        status=response_payload.status,
        vankey_hash=response_payload.vankey_hash,
        card_info=_to_card_info(response_payload.card_info),
        response_code=response_payload.response_code,
        message=response_payload.message,
    )


async def send_tx_token_approve(
    comm: Communication,
    amount: str,
    vankey_hash: str,
    items: Sequence[PaymentItem],
    timeout: float | None = None,
) -> TokenApprovalResult:
    """
    Approve token payment transaction.
    
    Args:
        comm: Communication instance
        amount: Transaction amount (9-digit numeric string)
        vankey_hash: VAN key hash (24 characters)
        items: List of items in the transaction
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Token approval data with authorization number and card info
        
    Raises:
        ValidationError: If input parameters are invalid
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    _validate_amount(amount)

    _log_payment_recovery(
        ServiceCode.TX_TOKEN_APPROVE,
        phase="request",
        amount=amount,
        vankey_hash=vankey_hash,
    )
    
    logger.debug(
        "Sending TX_TOKEN_APPROVE request",
        extra={"amount": amount, "vankey_hash_len": len(vankey_hash)},
    )

    message = _build_item_message(items)
    
    request_payload = TransactionTokenApproveRequest.build(
        {
            "amount": amount,
            "vankey_hash": vankey_hash,
            "message": message,
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.TX_TOKEN_APPROVE.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(
        request,
        timeout=timeout,
        control_handshake=True,
    )
    _validate_response(response, ServiceCode.TX_TOKEN_APPROVE)
    
    try:
        response_payload = TransactionTokenApproveResponse.parse(response.payload)
    except ConstructError as e:
        raise ProtocolError(
            response.payload.decode('euc-kr', errors='ignore')
        ) from e  

    _log_payment_recovery(
        ServiceCode.TX_TOKEN_APPROVE,
        phase="response",
        amount=amount,
        authorization_number=response_payload.authorization_number,
        vankey=response_payload.vankey,
        vankey_hash=vankey_hash,
        status=response_payload.status.name,
        response_code=response_payload.response_code.name,
    )
    
    logger.info(
        "Token payment approved",
        extra={
            "status": response_payload.status,
            "auth_number": response_payload.authorization_number,
            "response_code": response_payload.response_code.name,
        },
    )
    
    return TokenApprovalResult(
        status=response_payload.status,
        authorization_number=response_payload.authorization_number,
        card_info=_to_card_info(response_payload.card_info),
        vankey=response_payload.vankey,
        response_code=response_payload.response_code,
        message=response_payload.message,
    )


async def send_tx_token_cancel(
    comm: Communication,
    amount: str,
    original_authorization_number: str,
    original_authorization_date: str,
    vankey_hash: str,
    timeout: float | None = None,
) -> TokenCancelResult:
    """
    Cancel token payment transaction.
    
    Args:
        comm: Communication instance
        amount: Transaction amount (9-digit numeric string, must match original)
        original_authorization_number: Authorization number from approval (8 characters)
        original_authorization_date: Authorization date in YYMMDD format (6 digits)
        vankey_hash: VAN key hash from original approval (24 characters)
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Token cancellation data with card info
        
    Raises:
        ValidationError: If input parameters are invalid
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    _validate_amount(amount)
    _validate_authorization_number(original_authorization_number, "original_authorization_number")
    _validate_authorization_date(original_authorization_date, "original_authorization_date")

    _log_payment_recovery(
        ServiceCode.TX_TOKEN_CANCEL,
        phase="request",
        amount=amount,
        original_authorization_number=original_authorization_number,
        original_authorization_date=original_authorization_date,
        vankey_hash=vankey_hash,
    )
    
    logger.debug(
        "Sending TX_TOKEN_CANCEL request",
        extra={
            "amount": amount,
            "auth_number": original_authorization_number,
            "auth_date": original_authorization_date,
        },
    )
    
    request_payload = TransactionTokenCancelRequest.build(
        {
            "amount": amount,
            "original_authorization_number": original_authorization_number,
            "original_authorization_date": original_authorization_date,
            "vankey_hash": vankey_hash,
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.TX_TOKEN_CANCEL.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(
        request,
        timeout=timeout,
        control_handshake=True,
    )
    _validate_response(response, ServiceCode.TX_TOKEN_CANCEL)
    
    try:
        response_payload = TransactionTokenCancelResponse.parse(response.payload)
    except ConstructError as e:
        raise ProtocolError(
            response.payload.decode('euc-kr', errors='ignore')
        ) from e  

    _log_payment_recovery(
        ServiceCode.TX_TOKEN_CANCEL,
        phase="response",
        amount=amount,
        original_authorization_number=original_authorization_number,
        original_authorization_date=original_authorization_date,
        vankey=response_payload.vankey,
        vankey_hash=vankey_hash,
        status=response_payload.status.name,
        response_code=response_payload.response_code.name,
    )
    
    logger.info(
        "Token payment cancelled",
        extra={
            "status": response_payload.status,
            "response_code": response_payload.response_code.name,
        },
    )
    
    return TokenCancelResult(
        status=response_payload.status,
        card_info=_to_card_info(response_payload.card_info),
        vankey=response_payload.vankey,
        response_code=response_payload.response_code,
        message=response_payload.message,
    )


async def send_tx_spay_approve(
    comm: Communication,
    amount: str,
    authorization_type: AuthorizationType,
    items: Sequence[PaymentItem],
    timeout: float | None = None,
) -> SamsungPayApprovalResult:
    """
    Approve Samsung Pay transaction.
    
    Args:
        comm: Communication instance
        amount: Transaction amount (9-digit numeric string)
        authorization_type: Authorization type (PRE_AUTH or PURCHASE)
        items: List of items in the transaction
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Samsung Pay approval data with authorization number and card info
        
    Raises:
        ValidationError: If input parameters are invalid
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    _validate_amount(amount)
    
    logger.debug(
        "Sending TX_SPAY_APPROVE request",
        extra={
            "amount": amount,
            "auth_type": authorization_type.value,
        },
    )

    message = _build_item_message(items)
    
    request_payload = TransactionSPayApproveRequest.build(
        {
            "amount": amount,
            "authorization_type": authorization_type,
            "message": message,
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.TX_SPAY_APPROVE.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(
        request,
        timeout=timeout,
        control_handshake=True,
    )
    _validate_response(response, ServiceCode.TX_SPAY_APPROVE)
    
    try:
        response_payload = TransactionSPayApproveResponse.parse(response.payload)
    except ConstructError as e:
        raise ProtocolError(
            response.payload.decode('euc-kr', errors='ignore')
        ) from e  

    _log_payment_recovery(
        ServiceCode.TX_SPAY_APPROVE,
        phase="response",
        amount=amount,
        authorization_type=authorization_type.name,
        authorization_number=response_payload.authorization_number,
        vankey=response_payload.vankey,
        status=response_payload.status.name,
        response_code=response_payload.response_code.name,
    )
    
    logger.info(
        "Samsung Pay approved",
        extra={
            "status": response_payload.status,
            "auth_number": response_payload.authorization_number,
            "response_code": response_payload.response_code.name,
        },
    )
    
    return SamsungPayApprovalResult(
        status=response_payload.status,
        authorization_number=response_payload.authorization_number,
        card_info=_to_card_info(response_payload.card_info),
        vankey=response_payload.vankey,
        response_code=response_payload.response_code,
        message=response_payload.message,
    )


async def send_tx_spay_cancel(
    comm: Communication,
    amount: str,
    original_authorization_number: str,
    original_authorization_date: str,
    vankey: str,
    timeout: float | None = None,
) -> SamsungPayCancelResult:
    """
    Cancel Samsung Pay transaction.
    
    Args:
        comm: Communication instance
        amount: Transaction amount (9-digit numeric string, must match original)
        original_authorization_number: Authorization number from approval (8 characters)
        original_authorization_date: Authorization date in YYMMDD format (6 digits)
        vankey: VAN key from original approval (24 characters)
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Samsung Pay cancellation data with card info
        
    Raises:
        ValidationError: If input parameters are invalid
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    _validate_amount(amount)
    _validate_authorization_number(original_authorization_number, "original_authorization_number")
    _validate_authorization_date(original_authorization_date, "original_authorization_date")

    _log_payment_recovery(
        ServiceCode.TX_SPAY_CANCEL,
        phase="request",
        amount=amount,
        original_authorization_number=original_authorization_number,
        original_authorization_date=original_authorization_date,
        vankey=vankey,
    )
    
    logger.debug(
        "Sending TX_SPAY_CANCEL request",
        extra={
            "amount": amount,
            "auth_number": original_authorization_number,
            "auth_date": original_authorization_date,
        },
    )
    
    request_payload = TransactionSPayCancelRequest.build(
        {
            "amount": amount,
            "original_authorization_number": original_authorization_number,
            "original_authorization_date": original_authorization_date,
            "vankey": vankey,
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.TX_SPAY_CANCEL.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(
        request,
        timeout=timeout,
        control_handshake=True,
    )
    _validate_response(response, ServiceCode.TX_SPAY_CANCEL)

    try:
        response_payload = TransactionSPayCancelResponse.parse(response.payload)
    except ConstructError as e:
        raise ProtocolError(
            response.payload.decode('euc-kr', errors='ignore')
        ) from e  

    _log_payment_recovery(
        ServiceCode.TX_SPAY_CANCEL,
        phase="response",
        amount=amount,
        original_authorization_number=original_authorization_number,
        original_authorization_date=original_authorization_date,
        vankey=vankey,
        response_vankey=response_payload.vankey,
        status=response_payload.status.name,
        response_code=response_payload.response_code.name,
    )
    
    
    logger.info(
        "Samsung Pay cancelled",
        extra={
            "status": response_payload.status,
            "response_code": response_payload.response_code.name,
        },
    )
    
    return SamsungPayCancelResult(
        status=response_payload.status,
        card_info=_to_card_info(response_payload.card_info),
        vankey=response_payload.vankey,
        response_code=response_payload.response_code,
        message=response_payload.message,
    )


async def send_device_check(
    comm: Communication,
    timeout: float | None = None,
) -> DeviceCheckResult:
    """
    Perform device health check.
    
    Args:
        comm: Communication instance
        timeout: Response timeout in seconds (uses config default if None)
        
    Returns:
        Device check data with response code
        
    Raises:
        TimeoutError: If device doesn't respond in time
        ProtocolError: If response is invalid
        CommunicationError: If communication fails
    """
    logger.debug("Sending DEVICE_CHECK request")
    
    request_payload = DeviceCheckRequest.build(
        {
            "message": "",
        }
    )
    request = ProtocolFrame.build(
        {
            "service_code": ServiceCode.DEVICE_CHECK.value,
            "message_type": MessageType.REQUEST,
            "payload": request_payload,
        }
    )
    
    response = await comm.fetch(request, timeout=timeout)

    
    try:
        response_payload = DeviceCheckResponse.parse(response.payload)
        logger.info(
            "Device check complete",
            extra={"response_code": response_payload.response_code.name},
        )
        return DeviceCheckResult(
            response_code=response_payload.response_code,
        )
    except ConstructError:
        pass

    try:
        error_payload = ErrorPayload.parse(response.payload)
        logger.info(
            "Device check error",
            extra={
                "response_code": error_payload.response_code.name,
                "message": error_payload.message,
            },
        )
        return DeviceCheckResult(
            response_code=error_payload.response_code,
        )
    except ConstructError:
        pass
        # raise ProtocolError(
        #     response.payload.decode('euc-kr', errors='ignore')
        # ) from e  
        
    response_payload = DeviceCheckResponse.parse(
        DeviceCheckResponse.build({
            "response_code": ResponseCode.SERVICE_UNAVAILABLE,
        })
    )
    logger.info(
        "Device check complete",
        extra={"response_code": response_payload.response_code.name},
    )
    return DeviceCheckResult(
        response_code=response_payload.response_code,
    )
