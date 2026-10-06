from functools import reduce

from construct import (
    Adapter,
    Byte,
    Bytes,
    Checksum,
    Const,
    Mapping,
    PaddedString,
    Rebuild,
    Struct,
)

from .const import (
    ETX,
    STX,
    AuthorizationType,
    MessageType,
    ResponseCode,
    StatusCode,
)


class BCD(Adapter):
    def _encode(self, obj, context, path):
        size = self._sizeof(context, path)
        encoded = bytearray(size)
        for i in range(size - 1, -1, -1):
            obj, remainder = divmod(obj, 100)
            encoded[i] = (remainder // 10 << 4) + (remainder % 10)
        return bytes(encoded)

    def _decode(self, obj, context, path):
        decoded = 0
        for i in range(self._sizeof(context, path)):
            octet = obj[i]
            decoded *= 100
            decoded += (octet >> 4) * 10 + (octet & 0x0F)
        return decoded


def _enum_field(subcon, enum_type):
    return Mapping(subcon, {member: member.value for member in enum_type})


def _seek_and_read(stream, offset, length):
    original_position = stream.tell()
    stream.seek(offset)
    data = stream.read(length)
    stream.seek(original_position)
    return data


MessageTypeField = _enum_field(Bytes(2), MessageType)
ResponseCodeField = _enum_field(Byte, ResponseCode)
StatusCodeField = _enum_field(Byte, StatusCode)
AuthorizationTypeField = _enum_field(Byte, AuthorizationType)

FrameLength = BCD(Byte[2])

ProtocolFrame = Struct(
    Const(STX),
    "length" / Rebuild(FrameLength, lambda ctx: len(ctx.payload) + 9),
    "service_code" / PaddedString(2, "ascii"),
    "message_type" / MessageTypeField,
    "payload" / Bytes(lambda ctx: ctx.length - 9),
    Const(ETX),
    Checksum(
        Byte,
        lambda data: reduce(lambda x, y: x ^ y, data),
        lambda ctx: _seek_and_read(ctx._io, 1, ctx.length - 2),
    ),
)
