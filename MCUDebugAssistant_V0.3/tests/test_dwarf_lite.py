from symbols.dwarf_lite import eval_member_offset, eval_static_address


def test_armcc_member_location_plus_uconst():
    # ARMCC5 emits e.g. 23 84 01 => DW_OP_plus_uconst 132.
    assert eval_member_offset(bytes([0x23, 0x84, 0x01])) == 132
    assert eval_member_offset(bytes([0x23, 0x88, 0x01])) == 136


def test_armcc_global_location_dw_op_addr():
    # DW_OP_addr 0x20002894, little-endian Cortex-M / DWARF3.
    expr = bytes([0x03, 0x94, 0x28, 0x00, 0x20])
    assert eval_static_address(expr, 4, "<") == 0x20002894
