from __future__ import annotations

import struct

from typing import TYPE_CHECKING

from dislib.miscdefs import (
    AT,
    PhysAddress,
    VirtAddress,
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
            op_virt_addr = self.rom.tracer_stack.pop()
            if op_virt_addr[0] >= self.rom.bank_count:
                # Don't attempt to run from RAM
                continue

            op_phys_addr = self.rom.virt_to_phys(op_virt_addr)
            if op_phys_addr in self.rom.addr_types:
                if self.rom.addr_types[op_phys_addr] == AT.Op:
                    continue
            self.set_addr_type(op_phys_addr, AT.Op)

            bank_idx, rel_addr = op_virt_addr
            rel_addr %= self.rom.bank_size
            bank_phys_addr = PhysAddress(bank_idx * self.rom.bank_size)
            bank = self.rom.data[bank_idx * self.rom.bank_size :][: self.rom.bank_size]

            pc = rel_addr
            op1 = bank[pc]
            pc += 1
            ixy_cb_mode = False
            ixy_cb_mem = OA.MemHL
            ixy_cb_displacement = 0
            # print(hex(op1), oct(op1))
            op1_phys_addr = PhysAddress(bank_phys_addr + pc)

            # Handle prefixes
            if op1 == 0xED:
                self.set_addr_type(op1_phys_addr, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_ED
                extragrp = "(ED)"

            elif op1 == 0xCB:
                self.set_addr_type(op1_phys_addr, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_CB
                extragrp = "(CB)"

            elif op1 == 0xDD:
                self.set_addr_type(op1_phys_addr, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_DD_XX
                extragrp = "(DD)"
                if op1 == 0xCB:
                    # DD CB xx op
                    self.set_addr_type(PhysAddress(bank_phys_addr + pc), AT.DataByte)
                    ixy_cb_displacement = bank[pc]
                    pc += 1
                    self.set_addr_type(PhysAddress(bank_phys_addr + pc), AT.DataByte)
                    op1 = bank[pc]
                    pc += 1
                    ixy_cb_mode = True
                    ixy_cb_mem = OA.MemIXdd
                    spec_bank = OP_SPECS_CB
                    extragrp = "(DDCB)"

            elif op1 == 0xFD:
                self.set_addr_type(op1_phys_addr, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_FD_XX
                extragrp = "(FD)"
                if op1 == 0xCB:
                    # FD CB xx op
                    self.set_addr_type(PhysAddress(bank_phys_addr + pc), AT.DataByte)
                    ixy_cb_displacement = bank[pc]
                    pc += 1
                    self.set_addr_type(PhysAddress(bank_phys_addr + pc), AT.DataByte)
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
                    arg_phys_addr = PhysAddress(bank_phys_addr + pc)
                    if a == OA.Byte:
                        self.set_addr_type(arg_phys_addr, AT.DataByte)
                        atype = self.rom.addr_types[arg_phys_addr]
                        (val,) = struct.unpack("<B", bank[pc:][:1])
                        if atype == AT.DataByteLabelLo:
                            refaddr = self.rom.addr_refs[arg_phys_addr]
                            assert (refaddr[1] & 0xFF) == val
                            label = self.rom.labels_from_addr[
                                self.rom.virt_to_phys(refaddr)
                            ][0]
                            op_args.append(f"{label}&$FF")
                        elif atype == AT.DataByteLabelHi:
                            refaddr = self.rom.addr_refs[arg_phys_addr]
                            assert ((refaddr[1] >> 8) & 0xFF) == val
                            label = self.rom.labels_from_addr[
                                self.rom.virt_to_phys(refaddr)
                            ][0]
                            op_args.append(f"{label}>>8")
                        else:
                            op_args.append(f"${val:02X}")
                        pc += 1

                    elif a == OA.Word:
                        self.set_addr_type(arg_phys_addr, AT.DataWord)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        if (
                            0xC000 <= val <= 0xDFFF
                            or (
                                val < 0xE000
                                and val > 0x0038
                                and val in self.rom.labels_from_addr
                            )
                        ) and (arg_phys_addr) not in self.rom.forced_immediates:
                            label = self.ensure_label(
                                val, relative_to=VirtAddress((bank_idx, pc - 2))
                            )
                            op_args.append(f"{label}")
                        else:
                            op_args.append(f"${val:04X}")
                        pc += 2

                    elif a == OA.MemByteImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(arg_phys_addr, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(
                            val, relative_to=VirtAddress((bank_idx, pc - 2))
                        )
                        self.set_addr_type(
                            self.rom.virt_to_phys(
                                self.rom.naive_to_virt(
                                    val, relative_to=VirtAddress((bank_idx, pc - 2))
                                )
                            ),
                            AT.DataByte,
                        )
                        op_args.append(f"({label})")

                    elif a == OA.MemWordImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(arg_phys_addr, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(
                            val, relative_to=VirtAddress((bank_idx, pc - 2))
                        )
                        self.set_addr_type(
                            self.rom.virt_to_phys(
                                self.rom.naive_to_virt(
                                    val, relative_to=VirtAddress((bank_idx, pc - 2))
                                )
                            ),
                            AT.DataWord,
                        )
                        op_args.append(f"({label})")

                    elif a == OA.PortByteImm:
                        self.set_addr_type(arg_phys_addr, AT.DataWordLabel)
                        (val,) = struct.unpack("<B", bank[pc:][:1])
                        pc += 1
                        op_args.append(f"(${val:02X})")

                    elif a == OA.JumpRelByte:
                        self.set_addr_type(arg_phys_addr, AT.DataByteRelLabel)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        val += bank_phys_addr + pc + 1
                        label = self.ensure_label_phys(
                            PhysAddress(val),
                            relative_to=VirtAddress((bank_idx, pc - 1)),
                            allow_relative_labels=True,
                        )
                        self.rom.tracer_stack.append(
                            self.rom.phys_to_virt(
                                PhysAddress(val),
                                relative_to=VirtAddress((bank_idx, pc - 1)),
                            )
                        )
                        # self.rom.tracer_stack.append(self.rom.naive_to_virt(val))
                        pc += 1
                        op_args.append(f"{label}")

                    elif a == OA.JumpWord:
                        self.set_addr_type(arg_phys_addr, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        if val < 0xC000:
                            label = self.ensure_label(
                                val,
                                relative_to=VirtAddress((bank_idx, pc)),
                                allow_relative_labels=True,
                            )
                            self.rom.tracer_stack.append(
                                self.rom.naive_to_virt(
                                    val, relative_to=VirtAddress((bank_idx, pc))
                                )
                            )
                            # self.rom.tracer_stack.append(self.rom.naive_to_virt(val))
                            op_args.append(f"{label}")
                        else:
                            op_args.append(f"${val:04X}")
                        pc += 2

                    elif a in CONST_OAS:
                        op_args.append(CONST_OAS[a])

                    elif a in OA_MAP_CONST_ADDR:
                        val = OA_MAP_CONST_ADDR[a]
                        val_virt_addr = VirtAddress((0x00, val))
                        self.rom.set_label(val_virt_addr, f"ENTRY_RST_{val:02X}")
                        self.rom.tracer_stack.append(val_virt_addr)
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
                                label = self.ensure_label(
                                    val,
                                    relative_to=VirtAddress((bank_idx, pc - 1)),
                                )
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
                        self.set_addr_type(arg_phys_addr, AT.DataByte)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        pc += 1
                        if val >= 0:
                            op_args.append(f"(ix+{val})")
                        else:
                            op_args.append(f"(ix-{-val})")

                    elif a == OA.MemIYdd:
                        # SPECIAL CASE FOR SONIC 1:
                        # IY is, as far as I can tell, always set to D200.
                        self.set_addr_type(arg_phys_addr, AT.DataByte)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        val += 0xD200
                        pc += 1
                        label = self.ensure_label(
                            val,
                            relative_to=VirtAddress((bank_idx, pc - 1)),
                        )
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
                self.rom.op_decodes[op_phys_addr] = (
                    op_virt_addr,
                    pc - rel_addr,
                    op_str,
                )

                if not spec.stop:
                    self.rom.tracer_stack.append(
                        self.rom.phys_to_virt(
                            PhysAddress(bank_phys_addr + pc), relative_to=op_virt_addr
                        )
                    )

    def set_addr_type(self, addr: PhysAddress, addr_type: AT) -> None:
        self.rom.set_addr_type(addr, addr_type)

    def ensure_label(
        self,
        val: int,
        *,
        relative_to: VirtAddress,
        allow_relative_labels: bool = False,
    ) -> str:
        return self.rom.ensure_label(
            self.rom.naive_to_virt(val, relative_to=relative_to),
            relative_to=relative_to,
            allow_relative_labels=allow_relative_labels,
        )

    def ensure_label_phys(
        self,
        val: PhysAddress,
        *,
        relative_to: VirtAddress,
        allow_relative_labels: bool = False,
    ) -> str:
        return self.rom.ensure_label(
            self.rom.phys_to_virt(val, relative_to=relative_to),
            relative_to=relative_to,
            allow_relative_labels=allow_relative_labels,
        )
