from __future__ import annotations

import struct

from typing import TYPE_CHECKING

from dislib.miscdefs import (
    AT,
)
from dislib.z80ops import (
    CONST_OAS,
    OA,
    OA_MAP_CONST_ADDR,
    OP_SPECS_CB,
    OP_SPECS_DD_XX,
    OP_SPECS_ED,
    OP_SPECS_FD_XX,
    OP_SPECS_XX,
)

if TYPE_CHECKING:
    from dislib.rom import Rom


class Tracer:
    def __init__(self, *, rom: Rom) -> None:
        self.rom = rom

    def run(self) -> None:
        while len(self.rom.tracer_stack) >= 1:
            phys_addr = self.rom.tracer_stack.pop()
            if phys_addr in self.rom.addr_types:
                if self.rom.addr_types[phys_addr] == AT.Op:
                    continue
            self.set_addr_type(phys_addr, AT.Op)

            bank_idx = phys_addr // self.rom.bank_size
            bank_phys_addr = bank_idx * self.rom.bank_size
            rel_addr = phys_addr - bank_phys_addr
            bank_virt_addr = min(2, bank_idx)
            virt_addr = bank_virt_addr + rel_addr
            bank = self.rom.data[bank_idx * self.rom.bank_size :][: self.rom.bank_size]

            pc = rel_addr
            op1 = bank[pc]
            pc += 1
            ixy_cb_mode = False
            ixy_cb_mem = OA.MemHL
            ixy_cb_displacement = 0
            # print(hex(op1), oct(op1))

            # Handle prefixes
            if op1 == 0xED:
                self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_ED
                extragrp = "(ED)"

            elif op1 == 0xCB:
                self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_CB
                extragrp = "(CB)"

            elif op1 == 0xDD:
                self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_DD_XX
                extragrp = "(DD)"
                if op1 == 0xCB:
                    # DD CB xx op
                    self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                    ixy_cb_displacement = bank[pc]
                    pc += 1
                    self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                    op1 = bank[pc]
                    pc += 1
                    ixy_cb_mode = True
                    ixy_cb_mem = OA.MemIXdd
                    spec_bank = OP_SPECS_CB
                    extragrp = "(DDCB)"

            elif op1 == 0xFD:
                self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_FD_XX
                extragrp = "(FD)"
                if op1 == 0xCB:
                    # FD CB xx op
                    self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                    ixy_cb_displacement = bank[pc]
                    pc += 1
                    self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                    op1 = bank[pc]
                    pc += 1
                    ixy_cb_mode = True
                    ixy_cb_mem = OA.MemIYdd
                    spec_bank = OP_SPECS_CB
                    extragrp = "(FDCB)"

            else:
                spec_bank = OP_SPECS_XX
                extragrp = ""

            try:
                spec = spec_bank[op1]
            except LookupError:
                # raise Exception(f"TODO: Basic-decode op {op1:02X} {op1:03o}")
                print(f"TODO: Basic-decode op{extragrp} {op1:02X} {op1:03o}")
                pass
            else:
                op_args: list[str] = []
                for a in spec.args:
                    if a == OA.Byte:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                        (val,) = struct.unpack("<B", bank[pc:][:1])
                        pc += 1
                        op_args.append(f"${val:02X}")

                    elif a == OA.Word:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWord)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        if 0xC000 <= val <= 0xDFFF or (
                            val < 0xE000
                            and val > 0x0038
                            and val in self.rom.labels_from_addr
                        ):
                            label = self.ensure_label(val, relative_to=pc - 2)
                            op_args.append(f"{label}")
                        else:
                            op_args.append(f"${val:04X}")

                    elif a == OA.MemByteImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(val, relative_to=pc - 2)
                        self.set_addr_type(val, AT.DataByte)
                        op_args.append(f"({label})")

                    elif a == OA.MemWordImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(val, relative_to=pc - 2)
                        self.set_addr_type(val, AT.DataWord)
                        op_args.append(f"({label})")

                    elif a == OA.PortByteImm:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<B", bank[pc:][:1])
                        pc += 1
                        op_args.append(f"(${val:02X})")

                    elif a == OA.JumpRelByte:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByteRelLabel)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        val += bank_phys_addr + pc + 1
                        assert val < self.rom.bank_size * 3
                        label = self.ensure_label(
                            val, relative_to=pc - 1, allow_relative_labels=True
                        )
                        self.rom.tracer_stack.append(val)
                        pc += 1
                        op_args.append(f"{label}")

                    elif a == OA.JumpWord:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        upper_bound = self.rom.bank_size * 1
                        # TODO: Better overlay handling --GM
                        if bank_phys_addr + pc >= upper_bound:
                            upper_bound += self.rom.bank_size
                        if bank_phys_addr + pc >= upper_bound:
                            upper_bound += self.rom.bank_size
                        if val < upper_bound:
                            label = self.ensure_label(
                                val, relative_to=pc, allow_relative_labels=True
                            )
                            self.rom.tracer_stack.append(val)
                            op_args.append(f"{label}")
                        else:
                            op_args.append(f"${val:04X}")
                        pc += 2

                    elif a in CONST_OAS:
                        op_args.append(CONST_OAS[a])

                    elif a in OA_MAP_CONST_ADDR:
                        val = OA_MAP_CONST_ADDR[a]
                        self.rom.set_label(val, f"ENTRY_RST_{val:02X}")
                        self.rom.tracer_stack.append(val)
                        op_args.append(f"${val:02X}")

                    elif a == OA.MemHL:
                        if ixy_cb_mode:
                            # DD CB / FD CB case
                            # Format: DD CB xx op
                            val = ixy_cb_displacement
                            reg = CONST_OAS[
                                OA.RegIX if ixy_cb_mem == OA.MemIXdd else OA.RegIY
                            ]
                            if ixy_cb_mem == OA.MemIYdd:
                                # SPECIAL CASE FOR SONIC 1:
                                # IY is, as far as I can tell, always set to D200.
                                val += 0xD200
                                label = self.ensure_label(val, relative_to=pc - 1)
                                op_args.append(f"(iy+{label}-IYBASE)")
                            else:
                                if val >= 0:
                                    op_args.append(f"({reg}+{val})")
                                else:
                                    op_args.append(f"({reg}-{-val})")
                        else:
                            # Normal case
                            op_args.append("(hl)")

                    elif a == OA.MemIXdd:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        pc += 1
                        if val >= 0:
                            op_args.append(f"(ix+{val})")
                        else:
                            op_args.append(f"(ix-{-val})")

                    elif a == OA.MemIYdd:
                        # SPECIAL CASE FOR SONIC 1:
                        # IY is, as far as I can tell, always set to D200.
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        val += 0xD200
                        pc += 1
                        label = self.ensure_label(val, relative_to=pc - 1)
                        op_args.append(f"(iy+{label}-IYBASE)")

                    else:
                        raise Exception(
                            f"TODO: Basic-decode op{extragrp} {op1:02X} {op1:03o} arg type {a!r}"
                        )

                assert len(op_args) == len(spec.args)
                op_args_str = (" " + ", ".join(op_args)) if len(op_args) >= 1 else ""
                op_name = spec.name + (
                    " " * (6 - len(spec.name)) if len(op_args) >= 1 else ""
                )
                op_name = op_name.lower()
                op_str = f"{op_name}{op_args_str}"
                # print(f"{bank_idx:02X}:{virt_addr:04X}: {op_str}")
                self.rom.op_decodes[phys_addr] = (pc - rel_addr, op_str)

                if not spec.stop:
                    self.rom.tracer_stack.append(bank_phys_addr + pc)

    def set_addr_type(self, addr: int, addr_type: AT) -> None:
        self.rom.set_addr_type(addr, addr_type)

    def ensure_label(
        self, addr: int, *, relative_to: int, allow_relative_labels: bool = False
    ) -> str:
        return self.rom.ensure_label(
            addr,
            relative_to=relative_to,
            allow_relative_labels=allow_relative_labels,
        )
