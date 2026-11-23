"""Wire protocol for the Artix-7 maritime camera-motion FIR engine.

Frames use CRC16/CCITT-FALSE over version through payload (not sync bytes),
count and job_id are checked on every response. 24-bit signed little-endian.
"""
from __future__ import annotations

SYNC = b'\xa5\x5a'
VERSION = 1
CMD_FILTER = 1
CMD_FILTER_RESPONSE = 0x81
MAX_SAMPLES = 512
OK, BAD_HEADER, BAD_CRC, BAD_COUNT, TIMEOUT, FRAMING_ERROR = range(6)


def crc16(data: bytes) -> int:
    c = 0xffff
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ (0x1021 if c & 0x8000 else 0)) & 0xffff
    return c


def pack24(x: int) -> bytes:
    if not -(1 << 23) <= x < (1 << 23):
        raise ValueError('motion sample outside signed 24-bit')
    return (x & 0xffffff).to_bytes(3, 'little')


def unpack24(raw: bytes) -> int:
    if len(raw) != 3:
        raise ValueError('expected three bytes')
    v = int.from_bytes(raw, 'little')
    return v - 0x1000000 if v & 0x800000 else v


def encode_request(samples: list[int], job_id: int) -> bytes:
    if not 1 <= len(samples) <= MAX_SAMPLES:
        raise ValueError('require 1..512 samples per job')
    if not 0 <= job_id <= 255:
        raise ValueError('job_id must be a byte')
    body = bytes([VERSION, CMD_FILTER, job_id]) + len(samples).to_bytes(2, 'little') + b''.join(map(pack24, samples))
    return SYNC + body + crc16(body).to_bytes(2, 'little')


def decode_response(frame: bytes, job_id: int, expected_count: int) -> list[int]:
    if len(frame) < 10 or frame[:2] != SYNC:
        raise ValueError('invalid response sync/length')
    if frame[2] != VERSION or frame[3] != CMD_FILTER_RESPONSE or frame[4] != job_id:
        raise ValueError('response version/command/job mismatch')
    status = frame[5]
    count = int.from_bytes(frame[6:8], 'little')
    if len(frame) != 10 + 3*count:
        raise ValueError('incorrect packet byte count')
    if crc16(frame[2:-2]) != int.from_bytes(frame[-2:], 'little'):
        raise ValueError('invalid response CRC')
    if status:
        label={1:'BAD_HEADER',2:'BAD_CRC',3:'BAD_COUNT',4:'TIMEOUT',5:'FRAMING_ERROR'}.get(status, f'UNKNOWN_{status}')
        raise RuntimeError(f'FPGA rejected job: {label}')
    if count != expected_count:
        raise ValueError('wrong result count')
    return [unpack24(frame[8+3*i:11+3*i]) for i in range(count)]


def encode_response_for_test(samples: list[int], job_id: int, status: int = 0) -> bytes:
    """Software-only test fixture; never misrepresent as a hardware response."""
    payload = b''.join(map(pack24, samples)) if status == 0 else b''
    body = bytes([VERSION, CMD_FILTER_RESPONSE, job_id, status]) + (len(samples) if status == 0 else 0).to_bytes(2, 'little') + payload
    return SYNC+body+crc16(body).to_bytes(2, 'little')
