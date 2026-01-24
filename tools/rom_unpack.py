#!/usr/bin/env python3
import dataclasses
import enum
import struct
import sys
import zlib

from typing import (
    IO,
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
                    type(self).ANNOTCMDS[cmd](self, *line.split(" "))

    def _annotcmd_code(self, addr_str: str, label: str) -> None:
        addr = parse_int(addr_str)
        print(f"code ${addr:05X} label {label!r}")
        if addr not in self.addr_types:
            self.tracer_stack.append(addr)
        self.set_label(addr, label)

    ANNOTCMDS = {
        "code": _annotcmd_code,
    }

    def set_addr_type(self, addr: int, addr_type: AT) -> None:
        # print(addr, self.addr_types.get(addr, None), addr_type, self.tracer_stack)
        assert self.addr_types.get(addr, addr_type) == addr_type
        self.addr_types[addr] = addr_type

    def set_label(self, addr: int, label: str) -> None:
        if label in self.label_to_addr:
            assert self.label_to_addr[label] == addr
            return
        else:
            self.label_to_addr[label] = addr
            if addr not in self.labels_from_addr:
                self.labels_from_addr[addr] = []
            self.labels_from_addr[addr].append(label)

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
            # print(hex(op1), oct(op1))

            # Handle prefixes
            if op1 == 0xED:
                self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                op1 = bank[pc]
                pc += 1
                spec_bank = OP_SPECS_ED
                extragrp = "(ED)"

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
                for a in spec.args:
                    if a == OA.Byte:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByte)
                        (val,) = struct.unpack("<B", bank[pc:][:1])
                        pc += 1

                    elif a == OA.Word:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWord)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        pc += 2

                    elif a == OA.MemByteImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        self.set_label(val, f"addr_{val:05X}")
                        pc += 2

                    elif a == OA.MemWordImmWord:
                        # TODO: Handle the diff between virtual and physical labels --GM
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        self.set_label(val, f"addr_{val:05X}")
                        pc += 2

                    elif a == OA.JumpRelByte:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataByteRelLabel)
                        (val,) = struct.unpack("<b", bank[pc:][:1])
                        val += pc + 1
                        assert val < bank_size * 2
                        self.set_label(val, f"addr_{val:05X}")
                        self.tracer_stack.append(val)
                        pc += 1

                    elif a == OA.JumpWord:
                        self.set_addr_type(bank_phys_addr + pc, AT.DataWordLabel)
                        (val,) = struct.unpack("<H", bank[pc:][:2])
                        if val < bank_size * 2:
                            # TODO: Better overlay handling --GM
                            self.set_label(val, f"addr_{val:05X}")
                            self.tracer_stack.append(val)
                        pc += 2

                    elif a in {OA.RegAF, OA.RegBC, OA.RegDE, OA.RegHL, OA.RegSP}:
                        pass

                    elif a in {
                        OA.RegA,
                        OA.RegB,
                        OA.RegC,
                        OA.RegD,
                        OA.RegE,
                        OA.RegH,
                        OA.RegL,
                    }:
                        pass

                    elif a in {OA.MemHL, OA.MemBC, OA.MemDE}:
                        pass

                    elif a in {OA.Const0, OA.Const1, OA.Const2}:
                        pass

                    elif a in {
                        OA.CondNZ,
                        OA.CondZ,
                        OA.CondNC,
                        OA.CondC,
                        OA.CondPO,
                        OA.CondPE,
                        OA.CondP,
                        OA.CondM,
                    }:
                        pass

                    else:
                        raise Exception(
                            f"TODO: Basic-decode op{extragrp} {op1:02X} {op1:03o} arg type {a!r}"
                        )

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
            outfp.write(f".ENDME\n")

            # Write ROMBANKMAP
            outfp.write(f"\n.ROMBANKMAP\n")
            outfp.write(f"BANKSTOTAL 16\n")
            outfp.write(f"BANKSIZE $4000\n")
            outfp.write(f"BANKS 16\n")
            outfp.write(f".ENDRO\n")

            # Write RAM addresses
            outfp.write(f"\n")
            for addr in range(0xC000, 0x10000, 1):
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

                # Do a hexdump
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
        self.save_hexdump(
            outfp=outfp,
            bank_idx=bank_idx,
            virt_addr=virt_addr,
            data=data,
        )

    def save_hexdump(
        self, *, outfp: IO[str], bank_idx: int, virt_addr: int, data: bytes
    ) -> None:
        for row_idx in range((len(data) + 16 - 1) // 16):
            row_addr = row_idx * 16
            row = ", ".join(f"${v:02X}" for v in data[row_idx * 16 :][:16])
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

    RegA = enum.auto()
    RegB = enum.auto()
    RegC = enum.auto()
    RegD = enum.auto()
    RegE = enum.auto()
    RegH = enum.auto()
    RegL = enum.auto()

    MemHL = enum.auto()
    MemBC = enum.auto()
    MemDE = enum.auto()
    MemByteImmWord = enum.auto()
    MemWordImmWord = enum.auto()

    Const0 = enum.auto()
    Const1 = enum.auto()
    Const2 = enum.auto()

    CondNZ = enum.auto()
    CondZ = enum.auto()
    CondNC = enum.auto()
    CondC = enum.auto()
    CondPO = enum.auto()
    CondPE = enum.auto()
    CondP = enum.auto()
    CondM = enum.auto()


# Op Specs
@dataclasses.dataclass
class OS:
    name: str
    args: Sequence[OA]
    stop: bool = False


# 0oXYZ, sort by X then Z then Y.
OP_SPECS_XX = {
    #
    0o000: OS(name="NOP", args=[]),
    0o020: OS(name="DJNZ", args=[OA.JumpRelByte]),
    0o030: OS(name="JR", args=[OA.JumpRelByte], stop=True),
    0o040: OS(name="JR", args=[OA.CondNZ, OA.JumpRelByte]),
    0o050: OS(name="JR", args=[OA.CondZ, OA.JumpRelByte]),
    0o060: OS(name="JR", args=[OA.CondNC, OA.JumpRelByte]),
    0o070: OS(name="JR", args=[OA.CondC, OA.JumpRelByte]),
    #
    0o001: OS(name="LD", args=[OA.RegBC, OA.Word]),
    0o021: OS(name="LD", args=[OA.RegDE, OA.Word]),
    0o041: OS(name="LD", args=[OA.RegHL, OA.Word]),
    #
    0o012: OS(name="LD", args=[OA.RegA, OA.MemBC]),
    0o022: OS(name="LD", args=[OA.MemDE, OA.RegA]),
    0o052: OS(name="LD", args=[OA.RegHL, OA.MemWordImmWord]),
    0o062: OS(name="LD", args=[OA.MemByteImmWord, OA.RegA]),
    0o072: OS(name="LD", args=[OA.RegA, OA.MemByteImmWord]),
    #
    0o003: OS(name="INC", args=[OA.RegBC]),
    0o013: OS(name="DEC", args=[OA.RegBC]),
    0o023: OS(name="INC", args=[OA.RegDE]),
    0o043: OS(name="INC", args=[OA.RegHL]),
    #
    0o027: OS(name="RLA", args=[]),
    0o037: OS(name="RRA", args=[]),
    #
    0o311: OS(name="RET", args=[], stop=True),
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
    0o323: OS(name="OUT", args=[OA.Byte, OA.RegA]),
    0o333: OS(name="IN", args=[OA.RegA, OA.Byte]),
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
    0o345: OS(name="PUSH", args=[OA.RegHL]),
    0o365: OS(name="PUSH", args=[OA.RegAF]),
    #
    0o336: OS(name="SBC", args=[OA.RegA, OA.Byte]),
    0o366: OS(name="OR", args=[OA.Byte]),
    0o376: OS(name="CP", args=[OA.Byte]),
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
OP_SPECS_ED: dict[int, OS] = {
    0o126: OS(name="IM", args=[OA.Const1]),
    #
    0o260: OS(name="LDIR", args=[]),
}


def parse_int(s: str) -> int:
    if s.startswith("$"):
        return int(s[1:], 16)
    else:
        return int(s)


if __name__ == "__main__":
    main()
