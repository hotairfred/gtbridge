"""
WSJT-X UDP Protocol Encoder

Encodes messages in the WSJT-X UDP binary format (QDataStream)
so that applications like GridTracker 2 can receive them.

Message types implemented:
  0 - Heartbeat
  1 - Status
  2 - Decode

Reference: WSJT-X NetworkMessage.hpp
"""

import struct
import time

WSJTX_MAGIC = 0xADBCCBDA
WSJTX_SCHEMA = 2  # schema 2 is widely compatible


def _encode_utf8_string(s):
    """Encode a string as QDataStream QString-like: 4-byte length + UTF-8 bytes.

    py-wsjtx and many implementations use UTF-8 with a 4-byte length prefix
    rather than true UTF-16BE. GridTracker and other consumers accept this.
    A None/null string is encoded as 0xFFFFFFFF.
    """
    if s is None:
        return struct.pack('>I', 0xFFFFFFFF)
    encoded = s.encode('utf-8')
    return struct.pack('>I', len(encoded)) + encoded


def _encode_quint32(val):
    return struct.pack('>I', val)


def _encode_qint32(val):
    return struct.pack('>i', val)


def _encode_quint64(val):
    return struct.pack('>Q', val)


def _encode_quint8(val):
    return struct.pack('>B', val)


def _encode_bool(val):
    return struct.pack('>?', val)


def _encode_double(val):
    return struct.pack('>d', val)


def _header(msg_type, client_id):
    """Build the common WSJT-X UDP message header."""
    buf = b''
    buf += _encode_quint32(WSJTX_MAGIC)
    buf += _encode_quint32(WSJTX_SCHEMA)
    buf += _encode_quint32(msg_type)
    buf += _encode_utf8_string(client_id)
    return buf


def heartbeat(client_id="GTBRIDGE", max_schema=3, version="2.6.1", revision=""):
    """Build a Heartbeat message (type 0)."""
    buf = _header(0, client_id)
    buf += _encode_quint32(max_schema)
    buf += _encode_utf8_string(version)
    buf += _encode_utf8_string(revision)
    return buf


def status(client_id="GTBRIDGE", dial_freq=14074000, mode="FT8",
           dx_call="", report="", tx_mode="FT8", tx_enabled=False,
           transmitting=False, decoding=True, rx_df=1500, tx_df=1500,
           de_call="", de_grid="", dx_grid="", tx_watchdog=False,
           sub_mode="", fast_mode=False, special_op=0,
           freq_tolerance=0, tr_period=15, config_name="Default"):
    """Build a Status message (type 1)."""
    buf = _header(1, client_id)
    buf += _encode_quint64(dial_freq)
    buf += _encode_utf8_string(mode)
    buf += _encode_utf8_string(dx_call)
    buf += _encode_utf8_string(report)
    buf += _encode_utf8_string(tx_mode)
    buf += _encode_bool(tx_enabled)
    buf += _encode_bool(transmitting)
    buf += _encode_bool(decoding)
    buf += _encode_quint32(rx_df)
    buf += _encode_quint32(tx_df)
    buf += _encode_utf8_string(de_call)
    buf += _encode_utf8_string(de_grid)
    buf += _encode_utf8_string(dx_grid)
    buf += _encode_bool(tx_watchdog)
    buf += _encode_utf8_string(sub_mode)
    buf += _encode_bool(fast_mode)
    buf += _encode_quint8(special_op)
    buf += _encode_quint32(freq_tolerance)
    buf += _encode_quint32(tr_period)
    buf += _encode_utf8_string(config_name)
    return buf


def decode(client_id="GTBRIDGE", is_new=True, time_ms=0, snr=-10,
           delta_time=0.0, delta_freq=1500, mode="~", message="",
           low_confidence=False, off_air=False):
    """Build a Decode message (type 2).

    Args:
        client_id: WSJT-X instance identifier
        is_new: True for new decode, False for replay
        time_ms: Milliseconds since midnight UTC
        snr: Signal-to-noise ratio in dB
        delta_time: Time offset in seconds (float)
        delta_freq: Audio frequency offset in Hz
        mode: Decode mode character (~ for FT8, + for FT4, etc.)
        message: The decoded message text (e.g. "CQ K1ABC FN42")
        low_confidence: Low confidence flag
        off_air: Off-air (playback) flag
    """
    buf = _header(2, client_id)
    buf += _encode_bool(is_new)
    buf += _encode_quint32(time_ms)
    buf += _encode_qint32(snr)
    buf += _encode_double(delta_time)
    buf += _encode_quint32(delta_freq)
    buf += _encode_utf8_string(mode)
    buf += _encode_utf8_string(message)
    buf += _encode_bool(low_confidence)
    buf += _encode_bool(off_air)
    return buf


def current_time_ms():
    """Return milliseconds since midnight UTC (for decode time field)."""
    now = time.gmtime()
    return ((now.tm_hour * 3600) + (now.tm_min * 60) + now.tm_sec) * 1000
