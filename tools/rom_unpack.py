#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import enum
import struct
import sys
import zlib

from typing import (
    IO,
    Optional,
    Sequence,
)

bank_size = 16 * 1024  # FIXED SIZE FOR THE SEGA MASTER SYSTEM AND GAME GEAR PLATFORMs
bank_count = 16  # Set to 16 for a 256 KB ROM
rom_crc = 0xB519E833


def main() -> None:
    rom_fname, annot_fname, whole_fname = sys.argv[1:]

    rom_data = open(rom_fname, "rb").read()
    assert len(rom_data) == bank_count * bank_size
    assert (zlib.crc32(rom_data) & 0xFFFFFFFF) == rom_crc
    rom = Rom(data=rom_data)
    rom.load_annotations(file_name=annot_fname)
    rom.run_tracer()
    rom.save(file_name=whole_fname)


class AT(enum.Enum):
    DataByte = enum.auto()
    DataWord = enum.auto()
    Op = enum.auto()

    DataByteRelLabel = enum.auto()
    DataWordLabel = enum.auto()


class Rom:
    def __init__(self, *, data: bytes) -> None:
        self.data = data
        self.addr_types: dict[int, AT] = {}
        self.label_to_addr: dict[str, int] = {}
        self.labels_from_addr: dict[int, list[str]] = {}
        self.tracer_stack: list[int] = []
        self.op_decodes: dict[int, tuple[int, str]] = {}

    def load_annotations(self, *, file_name: str) -> None:
        with open(file_name, "r") as infp:
            for line in infp.readlines():
                # Remove trailing newlines and also some whitespace
                # Also, convert tabs to spaces naively
                line = line.strip().replace("\t", " ")

                # Condense multiple whitespace
                while "  " in line:
                    line = line.replace("  ", " ")

                if line != "":
                    # Extract a command
                    cmd, sep, line = line.partition(" ")
                    type(self).ANNOTCMDS[cmd](self, *line.split(" "))  # type: ignore

    def _annotcmd_code(self, addr_str: str, label: str) -> None:
        addr = parse_int(addr_str)
        # print(f"code addr ${addr:05X} label {label!r}")
        if addr not in self.addr_types:
            self.tracer_stack.append(addr)
        self.set_label(addr, label)

    LTYPEMAP = {
        "byte": AT.DataByte,
        "word": AT.DataWord,
        "wptr": AT.DataWordLabel,
    }
    LTYPESIZE = {
        AT.DataByte: 1,
        AT.DataWord: 2,
        AT.DataWordLabel: 2,
    }
    LTYPECMD = {
        AT.DataByte: "db",
        AT.DataWord: "dw",
        AT.DataWordLabel: "dw",
    }

    def _annotcmd_label(self, addr_str: str, ltype_str: str, label: str) -> None:
        ltype = type(self).LTYPEMAP[ltype_str]
        addr = parse_int(addr_str)
        # print(f"label addr ${addr:05X} type {ltype} label {label!r}")
        self.set_label(addr, label)
        self.set_addr_type(addr, ltype)

    ANNOTCMDS = {
        "code": _annotcmd_code,
        "label": _annotcmd_label,
    }

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
            self.label_to_addr[label] = addr
            if addr not in self.labels_from_addr:
                self.labels_from_addr[addr] = []
            self.labels_from_addr[addr].append(label)

    def ensure_label(self, addr: int) -> str:
        if not addr in self.labels_from_addr:
            self.set_label(addr, f"addr_{addr:05X}")
        return self.labels_from_addr[addr][0]

    def run_tracer(self) -> None:
        while len(self.tracer_stack) >= 1:
            phys_addr = self.tracer_stack.pop()
            if phys_addr in self.addr_types:
                if self.addr_types[phys_addr] == AT.Op:
                    continue
            self.set_addr_type(phys_addr, AT.Op)

            bank_idx = phys_addr // bank_size
            bank_phys_addr = bank_idx * bank_size
            rel_addr = phys_addr - bank_phys_addr
            bank_virt_addr = min(2, bank_idx)
            virt_addr = bank_virt_addr + rel_addr
            bank = self.data[bank_idx * bank_size :][:bank_size]

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
                        op_args.append(f"${val:04X}")

                    elif a == OA.MemByteImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(val)
                        self.set_addr_type(val, AT.DataByte)
                        op_args.append(f"({label})")

                    elif a == OA.MemWordImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2
                        label = self.ensure_label(val)
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
                        val += pc + 1
                        assert val < bank_size * 2
                        label = self.ensure_label(val)
                        self.tracer_stack.append(val)
                        pc += 1
                        op_args.append(f"{label}")

                    elif a == OA.JumpWord:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        if val < bank_size * 1:
                            # TODO: Better overlay handling --GM
                            label = self.ensure_label(val)
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
                            if val >= 0:
                                op_args.append(f"({reg}+{val})")
                            else:
                                op_args.append(f"({reg}-{-val})")
                        else:
                            # Normal case
                            op_args.append("(hl)")

                    elif a in {OA.MemIXdd, OA.MemIYdd}:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        pc += 1
                        reg = CONST_OAS[OA.RegIX if a == OA.MemIXdd else OA.RegIY]
                        if val >= 0:
                            op_args.append(f"({reg}+{val})")
                        else:
                            op_args.append(f"({reg}-{-val})")

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
            outfp.write(f";; Autogenerated with the following command:\n")
            outfp.write(f";;    python3 {' '.join(map(repr, sys.argv[:]))}\n")
            outfp.write(f";; Do NOT hand-edit!\n")

            # Write memory map
            outfp.write(f"\n.MEMORYMAP\n")
            outfp.write(f"SLOT 0 START $0000 SIZE $4000\n")
            outfp.write(f"SLOT 1 START $4000 SIZE $4000\n")
            outfp.write(f"SLOT 2 START $8000 SIZE $4000\n")
            outfp.write(f"SLOT 3 START $C000 SIZE $2000\n")
            outfp.write(f"DEFAULTSLOT 2\n")
            outfp.write(f"DEFAULTRAMSECTIONSLOT 3\n")
            outfp.write(f".ENDME\n")

            # Write ROMBANKMAP
            outfp.write(f"\n.ROMBANKMAP\n")
            outfp.write(f"BANKSTOTAL 16\n")
            outfp.write(f"BANKSIZE $4000\n")
            outfp.write(f"BANKS 16\n")
            outfp.write(f".ENDRO\n")

            # Write RAM addresses
            outfp.write(f'\n.RAMSECTION "RAMSection" SLOT 3 FORCE ORGA $C000\n')
            extra_ram_labels: list[str] = []
            prev_addr = 0xC000
            for addr in range(0xC000, 0xE000, 1):
                if addr in self.labels_from_addr:
                    base_label = self.labels_from_addr[addr][0]
                    if prev_addr != addr:
                        assert prev_addr < addr
                        outfp.write(f".  dsb {addr - prev_addr}\n")
                        prev_addr = addr
                    if addr in self.addr_types:
                        vartype = self.addr_types[addr]
                        varsize = self.LTYPESIZE[vartype]
                        varcmd = self.LTYPECMD[vartype]
                        # Look for any labels in the middle of this.
                        need_split = False
                        for split_offs in range(1, varsize, 1):
                            if addr + split_offs in self.labels_from_addr:
                                need_split = True
                                break
                        if need_split:
                            outfp.write(f"{base_label} db   ; {addr:04X} (split)\n")
                            prev_addr = addr + 1
                        else:
                            outfp.write(f"{base_label} {varcmd}   ; {addr:04X}\n")
                            prev_addr = addr + varsize
                    else:
                        outfp.write(f"{base_label} db   ; {addr:04X} (auto)\n")
                        prev_addr = addr + 1
                    for label in self.labels_from_addr[addr][1:]:
                        extra_ram_labels.append(f".DEF {label} {base_label}\n")
            outfp.write(f".ENDS\n")
            for s in extra_ram_labels:
                outfp.write(s)

            # Write extra addresses
            outfp.write(f"\n")
            for addr in range(0xE000, 0x10000, 1):
                for label in self.labels_from_addr.get(addr, []):
                    outfp.write(f".DEF {label} ${addr:04X}\n")

            # Write ROM
            for bank_idx in range(16):
                # Assume all banks past the first 2 want to be in slot 2
                slot_idx = min(2, bank_idx)
                outfp.write(
                    f'\n.SECTION "Bank{bank_idx:02d}" SLOT {slot_idx} BANK {bank_idx} FORCE ORG $0000\n'
                )
                bank = self.data[bank_idx * bank_size :][:bank_size]

                prev_rel_addr = 0
                for rel_addr in range(bank_size):
                    phys_addr = rel_addr + (bank_idx * bank_size)
                    virt_addr = rel_addr + (slot_idx * bank_size)
                    if phys_addr < 0xC000 and phys_addr in self.labels_from_addr:
                        if prev_rel_addr != rel_addr:
                            self.save_bytes(
                                outfp=outfp,
                                bank_idx=bank_idx,
                                virt_addr=(slot_idx * bank_size) + prev_rel_addr,
                                data=bank[prev_rel_addr:rel_addr],
                            )
                            prev_rel_addr = rel_addr
                        for label in self.labels_from_addr[phys_addr]:
                            outfp.write(f"{label}:\n")

                self.save_bytes(
                    outfp=outfp,
                    bank_idx=bank_idx,
                    virt_addr=(slot_idx * bank_size) + prev_rel_addr,
                    data=bank[prev_rel_addr:],
                )

                outfp.write(f".ENDS\n")

    def save_bytes(
        self, *, outfp: IO[str], bank_idx: int, virt_addr: int, data: bytes
    ) -> None:
        offs = 0
        prev_hexdump_offs = 0
        while offs < len(data):
            op_phys_addr = virt_addr + offs
            if op_phys_addr in self.op_decodes:
                op_len, op_str = self.op_decodes[op_phys_addr]
                if offs + op_len > len(data):
                    # Decode as if it wasn't an op
                    outfp.write(f"   ;; FIXME: Label appears mid-op!\n")
                    offs += 1
                else:
                    if offs != prev_hexdump_offs:
                        self.save_hexdump(
                            outfp=outfp,
                            bank_idx=bank_idx,
                            virt_addr=virt_addr + prev_hexdump_offs,
                            data=data[prev_hexdump_offs:offs],
                        )
                    outfp.write(
                        f"   {op_str}{' '*max(0, 34-len(op_str))}  ; {op_phys_addr:05X}\n"
                    )
                    offs += op_len
                    prev_hexdump_offs = offs
            else:
                offs += 1

        if offs != prev_hexdump_offs:
            self.save_hexdump(
                outfp=outfp,
                bank_idx=bank_idx,
                virt_addr=virt_addr + prev_hexdump_offs,
                data=data[prev_hexdump_offs:offs],
            )
            prev_hexdump_offs = offs

    def save_hexdump(
        self, *, outfp: IO[str], bank_idx: int, virt_addr: int, data: bytes
    ) -> None:
        for row_idx in range((len(data) + 16 - 1) // 16):
            row_addr = row_idx * 16
            row_data = data[row_addr : row_addr + 16]
            row = ", ".join(f"${v:02X}" for v in row_data)
            row += " " * ((len(", $xx") * 16 - len(", ")) - len(row))
            outfp.write(f".db {row}  ; {bank_idx:02d}:{virt_addr+row_addr:04X}\n")


# Op Arg types
class OA(enum.Enum):
    Byte = enum.auto()
    Word = enum.auto()
    JumpRelByte = enum.auto()
    JumpWord = enum.auto()

    RegAF = enum.auto()
    RegBC = enum.auto()
    RegDE = enum.auto()
    RegHL = enum.auto()
    RegSP = enum.auto()
    RegIX = enum.auto()
    RegIY = enum.auto()
    RegAFShadow = enum.auto()

    RegA = enum.auto()
    RegB = enum.auto()
    RegC = enum.auto()
    RegD = enum.auto()
    RegE = enum.auto()
    RegH = enum.auto()
    RegL = enum.auto()

    MemBC = enum.auto()
    MemDE = enum.auto()
    MemHL = enum.auto()
    MemIXdd = enum.auto()
    MemIYdd = enum.auto()
    MemByteImmWord = enum.auto()
    MemWordImmWord = enum.auto()

    PortByteImm = enum.auto()

    Const0 = enum.auto()
    Const1 = enum.auto()
    Const2 = enum.auto()
    Const3 = enum.auto()
    Const4 = enum.auto()
    Const5 = enum.auto()
    Const6 = enum.auto()
    Const7 = enum.auto()

    ConstAddr00 = enum.auto()
    ConstAddr08 = enum.auto()
    ConstAddr10 = enum.auto()
    ConstAddr18 = enum.auto()
    ConstAddr20 = enum.auto()
    ConstAddr28 = enum.auto()
    ConstAddr30 = enum.auto()
    ConstAddr38 = enum.auto()

    CondNZ = enum.auto()
    CondZ = enum.auto()
    CondNC = enum.auto()
    CondC = enum.auto()
    CondPO = enum.auto()
    CondPE = enum.auto()
    CondP = enum.auto()
    CondM = enum.auto()


OA_CONST_0_7 = [
    OA.Const0,
    OA.Const1,
    OA.Const2,
    OA.Const3,
    OA.Const4,
    OA.Const5,
    OA.Const6,
    OA.Const7,
]

OA_MAP_CONST_ADDR = {
    OA.ConstAddr00: 0x00,
    OA.ConstAddr08: 0x08,
    OA.ConstAddr10: 0x10,
    OA.ConstAddr18: 0x18,
    OA.ConstAddr20: 0x20,
    OA.ConstAddr28: 0x28,
    OA.ConstAddr30: 0x30,
    OA.ConstAddr38: 0x38,
}

CONST_OAS = {
    OA.RegAF: "af",
    OA.RegBC: "bc",
    OA.RegDE: "de",
    OA.RegHL: "hl",
    OA.RegSP: "sp",
    OA.RegIX: "ix",
    OA.RegIY: "iy",
    OA.RegAFShadow: "af'",
    OA.RegA: "a",
    OA.RegB: "b",
    OA.RegC: "c",
    OA.RegD: "d",
    OA.RegE: "e",
    OA.RegH: "h",
    OA.RegL: "l",
    OA.MemBC: "(bc)",
    OA.MemDE: "(de)",
    OA.Const0: "0",
    OA.Const1: "1",
    OA.Const2: "2",
    OA.Const3: "3",
    OA.Const4: "4",
    OA.Const5: "5",
    OA.Const6: "6",
    OA.Const7: "7",
    OA.CondNZ: "nz",
    OA.CondZ: "z",
    OA.CondNC: "nc",
    OA.CondC: "c",
    OA.CondPO: "po",
    OA.CondPE: "pe",
    OA.CondP: "p",
    OA.CondM: "m",
}


# Op Specs
@dataclasses.dataclass
class OS:
    name: str
    args: Sequence[OA]
    stop: bool = False


# 0oXYZ, sort by X then Z then Y.
OP_SPECS_XX: dict[int, OS] = {
    #
    0o000: OS(name="NOP", args=[]),
    0o010: OS(name="EX", args=[OA.RegAF, OA.RegAFShadow]),
    0o020: OS(name="DJNZ", args=[OA.JumpRelByte]),
    0o030: OS(name="JR", args=[OA.JumpRelByte], stop=True),
    0o040: OS(name="JR", args=[OA.CondNZ, OA.JumpRelByte]),
    0o050: OS(name="JR", args=[OA.CondZ, OA.JumpRelByte]),
    0o060: OS(name="JR", args=[OA.CondNC, OA.JumpRelByte]),
    0o070: OS(name="JR", args=[OA.CondC, OA.JumpRelByte]),
    #
    0o001: OS(name="LD", args=[OA.RegBC, OA.Word]),
    0o011: OS(name="ADD", args=[OA.RegHL, OA.RegBC]),
    0o021: OS(name="LD", args=[OA.RegDE, OA.Word]),
    0o031: OS(name="ADD", args=[OA.RegHL, OA.RegDE]),
    0o041: OS(name="LD", args=[OA.RegHL, OA.Word]),
    0o051: OS(name="ADD", args=[OA.RegHL, OA.RegHL]),
    0o061: OS(name="LD", args=[OA.RegSP, OA.Word]),
    0o071: OS(name="ADD", args=[OA.RegHL, OA.RegSP]),
    #
    0o002: OS(name="LD", args=[OA.MemBC, OA.RegA]),
    0o012: OS(name="LD", args=[OA.RegA, OA.MemBC]),
    0o022: OS(name="LD", args=[OA.MemDE, OA.RegA]),
    0o032: OS(name="LD", args=[OA.RegA, OA.MemDE]),
    0o042: OS(name="LD", args=[OA.MemWordImmWord, OA.RegHL]),
    0o052: OS(name="LD", args=[OA.RegHL, OA.MemWordImmWord]),
    0o062: OS(name="LD", args=[OA.MemByteImmWord, OA.RegA]),
    0o072: OS(name="LD", args=[OA.RegA, OA.MemByteImmWord]),
    #
    0o003: OS(name="INC", args=[OA.RegBC]),
    0o013: OS(name="DEC", args=[OA.RegBC]),
    0o023: OS(name="INC", args=[OA.RegDE]),
    0o033: OS(name="DEC", args=[OA.RegDE]),
    0o043: OS(name="INC", args=[OA.RegHL]),
    0o053: OS(name="DEC", args=[OA.RegHL]),
    #
    0o066: OS(name="LD", args=[OA.MemHL, OA.Byte]),
    #
    0o007: OS(name="RLCA", args=[]),
    0o017: OS(name="RRCA", args=[]),
    0o027: OS(name="RLA", args=[]),
    0o037: OS(name="RRA", args=[]),
    0o047: OS(name="DAA", args=[]),
    0o057: OS(name="CPL", args=[]),
    0o067: OS(name="SCF", args=[]),
    0o077: OS(name="CCF", args=[]),
    #
    0o300: OS(name="RET", args=[OA.CondNZ]),
    0o310: OS(name="RET", args=[OA.CondZ]),
    0o320: OS(name="RET", args=[OA.CondNC]),
    0o330: OS(name="RET", args=[OA.CondC]),
    0o340: OS(name="RET", args=[OA.CondPO]),
    0o350: OS(name="RET", args=[OA.CondPE]),
    0o360: OS(name="RET", args=[OA.CondP]),
    0o370: OS(name="RET", args=[OA.CondM]),
    #
    0o301: OS(name="POP", args=[OA.RegBC]),
    0o311: OS(name="RET", args=[], stop=True),
    0o321: OS(name="POP", args=[OA.RegDE]),
    0o331: OS(name="EXX", args=[]),
    0o341: OS(name="POP", args=[OA.RegHL]),
    0o351: OS(name="JP", args=[OA.MemHL], stop=True),
    0o361: OS(name="POP", args=[OA.RegAF]),
    0o371: OS(name="LD", args=[OA.RegSP, OA.RegHL]),
    #
    0o302: OS(name="JP", args=[OA.CondNZ, OA.JumpWord]),
    0o312: OS(name="JP", args=[OA.CondZ, OA.JumpWord]),
    0o322: OS(name="JP", args=[OA.CondNC, OA.JumpWord]),
    0o332: OS(name="JP", args=[OA.CondC, OA.JumpWord]),
    0o342: OS(name="JP", args=[OA.CondPO, OA.JumpWord]),
    0o352: OS(name="JP", args=[OA.CondPE, OA.JumpWord]),
    0o362: OS(name="JP", args=[OA.CondP, OA.JumpWord]),
    0o372: OS(name="JP", args=[OA.CondM, OA.JumpWord]),
    #
    0o303: OS(name="JP", args=[OA.JumpWord], stop=True),
    0o323: OS(name="OUT", args=[OA.PortByteImm, OA.RegA]),
    0o333: OS(name="IN", args=[OA.RegA, OA.PortByteImm]),
    # 0o343 = CB prefix
    0o353: OS(name="EX", args=[OA.RegDE, OA.RegHL]),
    0o363: OS(name="DI", args=[]),
    0o373: OS(name="EI", args=[]),
    #
    0o304: OS(name="CALL", args=[OA.CondNZ, OA.JumpWord]),
    0o314: OS(name="CALL", args=[OA.CondZ, OA.JumpWord]),
    0o324: OS(name="CALL", args=[OA.CondNC, OA.JumpWord]),
    0o334: OS(name="CALL", args=[OA.CondC, OA.JumpWord]),
    0o344: OS(name="CALL", args=[OA.CondPO, OA.JumpWord]),
    0o354: OS(name="CALL", args=[OA.CondPE, OA.JumpWord]),
    0o364: OS(name="CALL", args=[OA.CondP, OA.JumpWord]),
    0o374: OS(name="CALL", args=[OA.CondM, OA.JumpWord]),
    #
    0o305: OS(name="PUSH", args=[OA.RegBC]),
    0o315: OS(name="CALL", args=[OA.JumpWord]),
    0o325: OS(name="PUSH", args=[OA.RegDE]),
    # 0o335 = DD prefix
    0o345: OS(name="PUSH", args=[OA.RegHL]),
    # 0o355 = ED prefix
    0o365: OS(name="PUSH", args=[OA.RegAF]),
    # 0o375 = FD prefix
    #
    0o306: OS(name="ADD", args=[OA.RegA, OA.Byte]),
    0o316: OS(name="ADC", args=[OA.RegA, OA.Byte]),
    0o326: OS(name="SUB", args=[OA.Byte]),
    0o336: OS(name="SBC", args=[OA.RegA, OA.Byte]),
    0o346: OS(name="AND", args=[OA.Byte]),
    0o356: OS(name="XOR", args=[OA.Byte]),
    0o366: OS(name="OR", args=[OA.Byte]),
    0o376: OS(name="CP", args=[OA.Byte]),
    0o307: OS(name="RST", args=[OA.ConstAddr00]),
    0o317: OS(name="RST", args=[OA.ConstAddr08]),
    0o327: OS(name="RST", args=[OA.ConstAddr10]),
    0o337: OS(name="RST", args=[OA.ConstAddr18]),
    0o347: OS(name="RST", args=[OA.ConstAddr20]),
    0o357: OS(name="RST", args=[OA.ConstAddr28]),
    0o367: OS(name="RST", args=[OA.ConstAddr30]),
    0o377: OS(name="RST", args=[OA.ConstAddr38]),
}

for ry, vy in enumerate(
    [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
):
    OP_SPECS_XX[0o004 + ry * 8] = OS(name="INC", args=[vy])
    OP_SPECS_XX[0o005 + ry * 8] = OS(name="DEC", args=[vy])
    OP_SPECS_XX[0o006 + ry * 8] = OS(name="LD", args=[vy, OA.Byte])

for rz, vz in enumerate(
    [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
):
    OP_SPECS_XX[0o200 + rz] = OS(name="ADD", args=[OA.RegA, vz])
    OP_SPECS_XX[0o210 + rz] = OS(name="ADC", args=[OA.RegA, vz])
    OP_SPECS_XX[0o220 + rz] = OS(name="SUB", args=[vz])
    OP_SPECS_XX[0o230 + rz] = OS(name="SBC", args=[OA.RegA, vz])
    OP_SPECS_XX[0o240 + rz] = OS(name="AND", args=[vz])
    OP_SPECS_XX[0o250 + rz] = OS(name="XOR", args=[vz])
    OP_SPECS_XX[0o260 + rz] = OS(name="OR", args=[vz])
    OP_SPECS_XX[0o270 + rz] = OS(name="CP", args=[vz])

    for ry, vy in enumerate(
        [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
    ):
        if vy == OA.MemHL and vz == OA.MemHL:
            OP_SPECS_XX[0o100 + ry * 8 + rz] = OS(name="HALT", args=[])
        else:
            OP_SPECS_XX[0o100 + ry * 8 + rz] = OS(name="LD", args=[vy, vz])

# 0oXYZ, sort by X then Z then Y.
OP_SPECS_DD_XX: dict[int, OS] = {
    0o011: OS(name="ADD", args=[OA.RegIX, OA.RegBC]),
    0o031: OS(name="ADD", args=[OA.RegIX, OA.RegDE]),
    0o041: OS(name="LD", args=[OA.RegIX, OA.Word]),
    0o051: OS(name="ADD", args=[OA.RegIX, OA.RegHL]),
    0o071: OS(name="ADD", args=[OA.RegIX, OA.RegSP]),
    #
    0o064: OS(name="INC", args=[OA.MemIXdd]),
    #
    0o066: OS(name="LD", args=[OA.MemIXdd, OA.Byte]),
    #
    0o216: OS(name="ADC", args=[OA.RegA, OA.MemIXdd]),
    0o276: OS(name="CP", args=[OA.MemIXdd]),
    #
    0o341: OS(name="POP", args=[OA.RegIX]),
    #
    0o345: OS(name="PUSH", args=[OA.RegIX]),
}
OP_SPECS_FD_XX: dict[int, OS] = {
    0o011: OS(name="ADD", args=[OA.RegIY, OA.RegBC]),
    0o031: OS(name="ADD", args=[OA.RegIY, OA.RegDE]),
    0o041: OS(name="LD", args=[OA.RegIY, OA.Word]),
    0o051: OS(name="ADD", args=[OA.RegIY, OA.RegHL]),
    0o071: OS(name="ADD", args=[OA.RegIY, OA.RegSP]),
    #
    0o064: OS(name="INC", args=[OA.MemIYdd]),
    #
    0o066: OS(name="LD", args=[OA.MemIYdd, OA.Byte]),
    #
    0o216: OS(name="ADC", args=[OA.RegA, OA.MemIYdd]),
    0o276: OS(name="CP", args=[OA.MemIYdd]),
    #
    0o341: OS(name="POP", args=[OA.RegIY]),
    #
    0o345: OS(name="PUSH", args=[OA.RegIY]),
}
for rz, vz in enumerate(
    [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
):
    for ry, vy in enumerate(
        [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
    ):
        if vy == OA.MemHL and vz != OA.MemHL:
            OP_SPECS_DD_XX[0o100 + ry * 8 + rz] = OS(name="LD", args=[OA.MemIXdd, vz])
            OP_SPECS_FD_XX[0o100 + ry * 8 + rz] = OS(name="LD", args=[OA.MemIYdd, vz])
        elif vy != OA.MemHL and vz == OA.MemHL:
            OP_SPECS_DD_XX[0o100 + ry * 8 + rz] = OS(name="LD", args=[vy, OA.MemIXdd])
            OP_SPECS_FD_XX[0o100 + ry * 8 + rz] = OS(name="LD", args=[vy, OA.MemIYdd])

# 0oXYZ, sort by X then Z then Y.
OP_SPECS_ED: dict[int, OS] = {
    0o102: OS(name="SBC", args=[OA.RegHL, OA.RegBC]),
    0o122: OS(name="SBC", args=[OA.RegHL, OA.RegDE]),
    0o142: OS(name="SBC", args=[OA.RegHL, OA.RegHL]),
    0o162: OS(name="SBC", args=[OA.RegHL, OA.RegSP]),
    #
    0o103: OS(name="LD", args=[OA.MemWordImmWord, OA.RegBC]),
    0o113: OS(name="LD", args=[OA.RegBC, OA.MemWordImmWord]),
    0o123: OS(name="LD", args=[OA.MemWordImmWord, OA.RegDE]),
    0o133: OS(name="LD", args=[OA.RegDE, OA.MemWordImmWord]),
    #
    0o104: OS(name="NEG", args=[]),
    #
    0o126: OS(name="IM", args=[OA.Const1]),
    #
    0o240: OS(name="LDI", args=[]),
    0o260: OS(name="LDIR", args=[]),
    #
    0o243: OS(name="OUTI", args=[]),
    0o263: OS(name="OTIR", args=[]),
}

# 0oXYZ, sort by X then Z then Y.
OP_SPECS_CB: dict[int, OS] = {
    #
}
for rz, vz in enumerate(
    [OA.RegB, OA.RegC, OA.RegD, OA.RegE, OA.RegH, OA.RegL, OA.MemHL, OA.RegA]
):
    OP_SPECS_CB[0o000 + rz] = OS(name="RLC", args=[vz])
    OP_SPECS_CB[0o010 + rz] = OS(name="RRC", args=[vz])
    OP_SPECS_CB[0o020 + rz] = OS(name="RL", args=[vz])
    OP_SPECS_CB[0o030 + rz] = OS(name="RR", args=[vz])
    OP_SPECS_CB[0o040 + rz] = OS(name="SLA", args=[vz])
    OP_SPECS_CB[0o050 + rz] = OS(name="SRA", args=[vz])
    # 0o060 is the undocumented SLL which shifts in a 1 bit into the LSbit.
    OP_SPECS_CB[0o070 + rz] = OS(name="SRL", args=[vz])

    for ry in range(8):
        OP_SPECS_CB[0o100 + (ry * 8) + rz] = OS(name="BIT", args=[OA_CONST_0_7[ry], vz])
        OP_SPECS_CB[0o200 + (ry * 8) + rz] = OS(name="RES", args=[OA_CONST_0_7[ry], vz])
        OP_SPECS_CB[0o300 + (ry * 8) + rz] = OS(name="SET", args=[OA_CONST_0_7[ry], vz])


def parse_int(s: str) -> int:
    if s.startswith("$"):
        return int(s[1:], 16)
    else:
        return int(s)


if __name__ == "__main__":
    main()
