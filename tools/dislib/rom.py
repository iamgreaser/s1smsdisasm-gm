from __future__ import annotations

import struct

from dislib.annotator import Annotator
from dislib.miscdefs import (
    AT,
)
from dislib.saver import Saver
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


class Rom:
    bank_size = (
        16 * 1024
    )  # FIXED SIZE FOR THE SEGA MASTER SYSTEM AND GAME GEAR PLATFORMs
    bank_count = 16  # Set to 16 for a 256 KB ROM
    rom_crc = 0xB519E833

    def __init__(self, *, data: bytes) -> None:
        self.data = data
        self.addr_types: dict[int, AT] = {}
        self.label_to_addr: dict[str, int] = {}
        self.labels_from_addr: dict[int, list[str]] = {}
        self.tracer_stack: list[int] = []
        self.op_decodes: dict[int, tuple[int, str]] = {}

    def load_annotations(self, *, file_name: str) -> None:
        annotator = Annotator(rom=self)
        with open(file_name, "r") as infp:
            for line in infp.readlines():
                annotator.annotate_line(line)

    def set_addr_type(self, addr: int, addr_type: AT) -> None:
        # print(addr, self.addr_types.get(addr, None), addr_type, self.tracer_stack)
        if self.addr_types.get(addr, addr_type) == addr_type:
            if (
                addr >= 1
                and self.addr_types.get(addr - 0x01, AT.DataByte) == AT.DataWord
            ):
                # Downsize for a split
                self.addr_types[addr - 0x01] = AT.DataByte
            self.addr_types[addr] = addr_type
        else:
            other_type = self.addr_types[addr]
            if other_type == AT.DataWord and addr_type == AT.DataByte:
                # Downsize for a split
                self.addr_types[addr + 0x00] = AT.DataByte
                self.addr_types[addr + 0x01] = AT.DataByte
            elif other_type == AT.DataByte and addr_type == AT.DataWord:
                # Block upsize
                pass
            else:
                print("FIXME: Op type derailment!")
                print(
                    addr, self.addr_types.get(addr, None), addr_type, self.tracer_stack
                )

    def set_label(self, addr: int, label: str) -> None:
        if label in self.label_to_addr:
            assert self.label_to_addr[label] == addr
            return
        else:
            # Don't track relative labels here
            if not (label.strip("-") == "" or label.strip("+") == "" or label == "__"):
                self.label_to_addr[label] = addr
            if addr not in self.labels_from_addr:
                self.labels_from_addr[addr] = []
            self.labels_from_addr[addr].append(label)

    def ensure_label(
        self, addr: int, *, relative_to: int, allow_relative_labels: bool = False
    ) -> str:
        if not addr in self.labels_from_addr:
            if addr >= 0xC000 and addr <= 0xDFFF:
                self.set_label(addr, f"var_{addr:04X}")
            else:
                self.set_label(addr, f"addr_{addr:05X}")
        label = self.labels_from_addr[addr][0]
        if allow_relative_labels:
            if label == "__":
                if addr > relative_to:
                    return "_f"
                elif addr < relative_to:
                    return "_b"
                else:
                    raise Exception("TODO: Handle this `__` label case")
            else:
                return label
        else:
            if label == "__" or label.strip("+-") == "":
                # Relative label - use a constant instead.
                return f"${addr:04X}"
            else:
                return label

    def run_tracer(self) -> None:
        while len(self.tracer_stack) >= 1:
            phys_addr = self.tracer_stack.pop()
            if phys_addr in self.addr_types:
                if self.addr_types[phys_addr] == AT.Op:
                    continue
            self.set_addr_type(phys_addr, AT.Op)

            bank_idx = phys_addr // self.bank_size
            bank_phys_addr = bank_idx * self.bank_size
            rel_addr = phys_addr - bank_phys_addr
            bank_virt_addr = min(2, bank_idx)
            virt_addr = bank_virt_addr + rel_addr
            bank = self.data[bank_idx * self.bank_size :][: self.bank_size]

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
                            and val in self.labels_from_addr
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
                        assert val < self.bank_size * 3
                        label = self.ensure_label(
                            val, relative_to=pc - 1, allow_relative_labels=True
                        )
                        self.tracer_stack.append(val)
                        pc += 1
                        op_args.append(f"{label}")

                    elif a == OA.JumpWord:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        upper_bound = self.bank_size * 1
                        # TODO: Better overlay handling --GM
                        if bank_phys_addr + pc >= upper_bound:
                            upper_bound += self.bank_size
                        if bank_phys_addr + pc >= upper_bound:
                            upper_bound += self.bank_size
                        if val < upper_bound:
                            label = self.ensure_label(
                                val, relative_to=pc, allow_relative_labels=True
                            )
                            self.tracer_stack.append(val)
                            op_args.append(f"{label}")
                        else:
                            op_args.append(f"${val:04X}")
                        pc += 2

                    elif a in CONST_OAS:
                        op_args.append(CONST_OAS[a])

                    elif a in OA_MAP_CONST_ADDR:
                        val = OA_MAP_CONST_ADDR[a]
                        self.set_label(val, f"ENTRY_RST_{val:02X}")
                        self.tracer_stack.append(val)
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
                self.op_decodes[phys_addr] = (pc - rel_addr, op_str)

                if not spec.stop:
                    self.tracer_stack.append(bank_phys_addr + pc)

    def save(self, *, file_name: str) -> None:
        with open(file_name, "w") as outfp:
            saver = Saver(rom=self, outfp=outfp)
            saver.save()
