"""
WSJT-X UDP Protocol Encoder/Decoder

Encodes and decodes messages in the WSJT-X UDP binary format (QDataStream)
so that applications like GridTracker 2 can receive and send them.

Message types implemented:
  Encode: 0 - Heartbeat, 1 - Status, 2 - Decode, 5 - QSO Logged
  Decode: 4 - Reply (sent by GridTracker when a callsign is clicked)

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


def _encode_qint64(val):
    return struct.pack('>q', val)


def _encode_double(val):
    return struct.pack('>d', val)


def _encode_qdatetime(year, month, day, hour=0, minute=0, second=0):
    """Encode date/time as QDataStream QDateTime (UTC).

    Args: year, month, day, hour, minute, second (integers).
    """
    # QDate: Julian Day Number as qint64
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    jdn = (day + (153 * m + 2) // 5 + 365 * y
           + y // 4 - y // 100 + y // 400 - 32045)
    buf = _encode_qint64(jdn)
    # QTime: milliseconds since midnight as quint32
    buf += _encode_quint32((hour * 3600 + minute * 60 + second) * 1000)
    # Timespec: 1 = UTC
    buf += _encode_quint8(1)
    return buf


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


def qso_logged(client_id="GTBRIDGE", dx_call="", dx_grid="", freq_hz=0,
               mode="", report_sent="", report_rcvd="",
               tx_power="", comments="", name="",
               date_time_off=None, date_time_on=None,
               operator_call="", my_call="", my_grid="",
               exchange_sent="", exchange_rcvd="", adif_prop_mode=""):
    """Build a QSO Logged message (type 5).

    Sent to GridTracker so it can mark the station as worked.

    Args:
        date_time_off: Tuple (year, month, day, hour, min, sec) or None for now.
        date_time_on: Tuple (year, month, day, hour, min, sec) or None for now.
    """
    now = time.gmtime()
    now_dt = (now.tm_year, now.tm_mon, now.tm_mday,
              now.tm_hour, now.tm_min, now.tm_sec)

    buf = _header(5, client_id)
    buf += _encode_qdatetime(*(date_time_off or now_dt))
    buf += _encode_utf8_string(dx_call)
    buf += _encode_utf8_string(dx_grid)
    buf += _encode_quint64(freq_hz)
    buf += _encode_utf8_string(mode)
    buf += _encode_utf8_string(report_sent)
    buf += _encode_utf8_string(report_rcvd)
    buf += _encode_utf8_string(tx_power)
    buf += _encode_utf8_string(comments)
    buf += _encode_utf8_string(name)
    buf += _encode_qdatetime(*(date_time_on or date_time_off or now_dt))
    buf += _encode_utf8_string(operator_call)
    buf += _encode_utf8_string(my_call)
    buf += _encode_utf8_string(my_grid)
    buf += _encode_utf8_string(exchange_sent)
    buf += _encode_utf8_string(exchange_rcvd)
    buf += _encode_utf8_string(adif_prop_mode)
    return buf


def current_time_ms():
    """Return milliseconds since midnight UTC (for decode time field)."""
    now = time.gmtime()
    return ((now.tm_hour * 3600) + (now.tm_min * 60) + now.tm_sec) * 1000


# ------------------------------------------------------------------ #
#  Decoders                                                            #
# ------------------------------------------------------------------ #

def _decode_utf8_string(data, offset):
    """Decode a length-prefixed UTF-8 string. Returns (string, new_offset)."""
    length = struct.unpack_from('>I', data, offset)[0]
    offset += 4
    if length == 0xFFFFFFFF:
        return None, offset
    s = data[offset:offset + length].decode('utf-8')
    return s, offset + length


def _decode_quint32(data, offset):
    return struct.unpack_from('>I', data, offset)[0], offset + 4


def _decode_qint32(data, offset):
    return struct.unpack_from('>i', data, offset)[0], offset + 4


def _decode_quint8(data, offset):
    return struct.unpack_from('>B', data, offset)[0], offset + 1


def _decode_bool(data, offset):
    return struct.unpack_from('>?', data, offset)[0], offset + 1


def _decode_double(data, offset):
    return struct.unpack_from('>d', data, offset)[0], offset + 8


def parse_header(data):
    """Parse the common WSJT-X message header.

    Returns (msg_type, client_id, payload_offset) or None on error.
    """
    if len(data) < 12:
        return None
    magic = struct.unpack_from('>I', data, 0)[0]
    if magic != WSJTX_MAGIC:
        return None
    schema = struct.unpack_from('>I', data, 4)[0]
    msg_type = struct.unpack_from('>I', data, 8)[0]
    client_id, offset = _decode_utf8_string(data, 12)
    return msg_type, client_id, offset


def parse_reply(data):
    """Parse a Reply message (type 4) from GridTracker.

    Returns a dict with: client_id, time_ms, snr, delta_time, delta_freq,
    mode, message, low_confidence, modifiers.  Or None on error.
    """
    hdr = parse_header(data)
    if hdr is None or hdr[0] != 4:
        return None
    _, client_id, off = hdr
    try:
        time_ms, off = _decode_quint32(data, off)
        snr, off = _decode_qint32(data, off)
        delta_time, off = _decode_double(data, off)
        delta_freq, off = _decode_quint32(data, off)
        mode, off = _decode_utf8_string(data, off)
        message, off = _decode_utf8_string(data, off)
        low_confidence, off = _decode_bool(data, off)
        modifiers, off = _decode_quint8(data, off)
    except (struct.error, IndexError):
        return None
    return {
        'client_id': client_id,
        'time_ms': time_ms,
        'snr': snr,
        'delta_time': delta_time,
        'delta_freq': delta_freq,
        'mode': mode,
        'message': message,
        'low_confidence': low_confidence,
        'modifiers': modifiers,
    }
