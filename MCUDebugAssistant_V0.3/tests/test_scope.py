import struct

from core.scope import (
    HssFrameDecoder,
    JScopeRttPacketDecoder,
    ScopeChannelSpec,
    ScopeReadPlanner,
    parse_jscope_rtt_channel_name,
)


def test_scope_planner_and_hss_decoder():
    channels = [
        ScopeChannelSpec(1, "a", 0x20000000, "float"),
        ScopeChannelSpec(2, "b", 0x20000004, "uint16"),
        ScopeChannelSpec(3, "c", 0x20000020, "int32"),
    ]
    blocks = ScopeReadPlanner().plan(channels)
    assert [(b.address, b.size) for b in blocks] == [
        (0x20000000, 6),
        (0x20000020, 4),
    ]
    dec = HssFrameDecoder(blocks)
    payload = struct.pack("<fH", 12.5, 123) + struct.pack("<i", -45)
    frame1 = struct.pack("<I", 1_000_000) + payload
    frame2 = struct.pack("<I", 1_001_000) + payload

    # Deliberately split a frame across HSS_Read() calls.
    times, rows = dec.feed(frame1 + frame2[:3])
    assert times == [0.0]
    assert len(rows) == 1
    assert rows[0][1] == 12.5
    assert rows[0][2] == 123
    assert rows[0][3] == -45

    times, rows = dec.feed(frame2[3:])
    assert times == [0.001]
    assert rows[0][3] == -45


def test_hss_timestamp_is_not_decoded_as_constant_int16_data():
    channel = ScopeChannelSpec(1, "constant", 0x20001000, "int16")
    blocks = ScopeReadPlanner().plan([channel])
    dec = HssFrameDecoder(blocks)
    raw = b"".join(
        struct.pack("<Ih", timestamp_us, 1000)
        for timestamp_us in (10_000, 11_000, 12_000, 13_000)
    )
    times, rows = dec.feed(raw)
    assert times == [0.0, 0.001, 0.002, 0.003]
    assert [row[1] for row in rows] == [1000, 1000, 1000, 1000]


def test_jscope_rtt_format_and_decoder_with_timestamp():
    fmt = parse_jscope_rtt_channel_name("JScope_t4f4u2i1")
    assert fmt.packet_size == 11
    assert fmt.has_timestamp
    dec = JScopeRttPacketDecoder(fmt)
    packet1 = struct.pack("<IfHb", 1000, 1.25, 7, -2)
    packet2 = struct.pack("<IfHb", 2000, 2.5, 8, 3)
    times, values = dec.feed(packet1 + packet2)
    assert times == [0.0, 0.001]
    assert values[1] == [1.25, 2.5]
    assert values[2] == [7, 8]
    assert values[3] == [-2, 3]


def test_jscope_rtt_without_timestamp_uses_sample_index():
    fmt = parse_jscope_rtt_channel_name("JScope_u4i2")
    dec = JScopeRttPacketDecoder(fmt)
    times, values = dec.feed(struct.pack("<IhIh", 1, -1, 2, -2))
    assert times == [0.0, 1.0]
    assert values[1] == [1, 2]
    assert values[2] == [-1, -2]
