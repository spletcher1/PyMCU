"""Lets the tests import PyMCU's modules on a PC. Raspberry Pi libraries that aren't installed are
replaced by empty modules, cobs by a small implementation, and multiprocessing's fork (which
Windows lacks) by the default start method. Import this before any PyMCU module."""
import multiprocessing
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _Stub(name):
    try:
        __import__(name)
    except Exception:
        sys.modules[name] = types.ModuleType(name)


class _DecodeError(Exception):
    pass


def _CobsEncode(data):
    out, block = bytearray(), bytearray()
    for b in data:
        if b == 0:
            out.append(len(block) + 1)
            out += block
            block = bytearray()
        else:
            block.append(b)
            if len(block) == 254:
                out.append(255)
                out += block
                block = bytearray()
    out.append(len(block) + 1)
    out += block
    return bytes(out)


def _CobsDecode(data):
    out, i = bytearray(), 0
    while i < len(data):
        code = data[i]
        if code == 0 or i + code > len(data):
            raise _DecodeError("bad COBS data")
        out += data[i + 1:i + code]
        i += code
        if code < 0xFF and i < len(data):
            out.append(0)
    return bytes(out)


try:
    from cobs import cobs  # noqa: F401
except ImportError:
    _cobs = types.ModuleType("cobs")
    _inner = types.ModuleType("cobs.cobs")
    _inner.encode, _inner.decode, _inner.DecodeError = _CobsEncode, _CobsDecode, _DecodeError
    _cobs.cobs = _inner
    sys.modules["cobs"], sys.modules["cobs.cobs"] = _cobs, _inner

for _name in ("serial", "smbus2", "gpiozero", "board", "busio", "adafruit_si7021", "adafruit_tsl2561", "adafruit_tsl2591"):
    _Stub(_name)

if "fork" not in multiprocessing.get_all_start_methods():
    _getContext = multiprocessing.get_context
    multiprocessing.get_context = lambda method=None: _getContext(None if method == "fork" else method)
