from enum import Enum


class ServiceCode(str, Enum):
    # TOKEN
    TX_TOKEN_INIT = "PS"
    TX_TOKEN_GENERATE = "TQ"
    TX_TOKEN_APPROVE = "D8"
    TX_TOKEN_CANCEL = "D9"
    # SAMSUNG WALLET
    TX_SPAY_INIT = "PA"
    TX_SPAY_APPROVE = "D1"
    TX_SPAY_CANCEL = "D7"
    # RFID
    TX_RFID_INIT = "PR"
    # MISC
    AGE_CHECK = "AC"
    DEVICE_CHECK = "PC"


class MessageType(bytes, Enum):
    REQUEST = b"10"
    RESPONSE = b"20"


class ControlFrame(bytes, Enum):
    """Three-byte CAT control frames from the TCP-40 protocol."""

    ENQ = b"\x05" * 3
    ACK = b"\x06" * 3
    EOT = b"\x04" * 3


class StatusCode(int, Enum):
    Y = 0x59  # 'Y'
    N = 0x4E  # 'N'


class AuthorizationType(int, Enum):
    PRE_AUTH = 0x00
    PURCHASE = 0x01


class ResponseCode(int, Enum):
    SUCCESS = 0x00
    TIMEOUT = 0xB0
    CANCEL = 0xB1
    CONDITION_FAIL = 0xB2
    FORMAT_ERROR = 0xB3
    SERVICE_UNAVAILABLE = 0xB4
    ERROR_RF = 0xB5
    ERROR_VAN = 0xB6
    ERROR_POS = 0xC0
    NETWORK_ERROR = 0xC1
    NOCHK_NETWORK = 0xC2
    ERROR = 0xFF


STX = b"\x02"
ETX = b"\x03"

FS = b"\x1C"
RS = b"\x1E"
