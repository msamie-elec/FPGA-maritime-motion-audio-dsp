from __future__ import annotations
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
from serial_protocol import crc16,encode_request,decode_response,encode_response_for_test,pack24,unpack24


def test_ccitt_false_standard_check():
    assert crc16(b'123456789') == 0x29b1


def test_24bit_signed_roundtrip():
    for v in [-8388608,-180,-1,0,1,32768,8388607]:
        assert unpack24(pack24(v))==v


def test_request_binary_format_and_crc():
    frame=encode_request([-9,0,32768],77)
    assert frame[:2]==b'\xa5\x5a'
    assert frame[2:7]==bytes([1,1,77,3,0])
    assert frame[7:10]==pack24(-9)
    assert frame[-2:]==crc16(frame[2:-2]).to_bytes(2,'little')


def test_response_roundtrip_and_tamper_rejected():
    response=encode_response_for_test([0,1,-1,1445],17)
    assert decode_response(response,17,4)==[0,1,-1,1445]
    bad=bytearray(response);bad[10]^=1
    with pytest.raises(ValueError,match='CRC'):decode_response(bytes(bad),17,4)
    with pytest.raises(ValueError,match='job'):decode_response(response,18,4)
    with pytest.raises(ValueError,match='count'):decode_response(response,17,3)


def test_error_status_rejected():
    response=encode_response_for_test([],22,status=2)
    with pytest.raises(RuntimeError,match='BAD_CRC'):decode_response(response,22,0)


def test_invalid_request_dimensions():
    with pytest.raises(ValueError):encode_request([],1)
    with pytest.raises(ValueError):encode_request([0]*513,1)
    with pytest.raises(ValueError):pack24(1<<23)


def test_uart_framing_error_is_not_ignored():
    from serial_protocol import encode_response_for_test, decode_response, FRAMING_ERROR
    import pytest
    frame = encode_response_for_test([], 0x35, status=FRAMING_ERROR)
    with pytest.raises(RuntimeError, match='FRAMING_ERROR'):
        decode_response(frame, 0x35, 6)
