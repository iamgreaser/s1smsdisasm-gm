from __future__ import annotations

import struct

from typing import TYPE_CHECKING

from dislib.miscdefs import (
    AT,
    LTYPEMAP,
    LTYPESIZE,
)

if TYPE_CHECKING:
    from dislib.rom import Rom


class Annotator:
    def __init__(self, *, rom: Rom) -> None:
        self.rom = rom

    def annotate_line(self, /, line: str) -> None:
        # Remove trailing newlines and also some whitespace
        # Also, convert tabs to spaces naively
        line = line.strip().replace("\t", " ")

        # Condense multiple whitespace
        while "  " in line:
            line = line.replace("  ", " ")

        # Remove comments
        line = line.partition("#")[0]

        if line != "":
            # Extract a command
            cmd, sep, line = line.partition(" ")
            self.ANNOTCMDS[cmd](self, *line.split(" "))  # type: ignore

    def _annotcmd_code(self, addr_str: str, label: str) -> None:
        addr = parse_addr(addr_str)
        # print(f"code addr ${addr:05X} label {label!r}")
        if addr not in self.rom.addr_types:
            self.rom.tracer_stack.append(addr)
        self.rom.set_label(addr, label)

    def _annotcmd_label(self, addr_str: str, ltype_str: str, label: str) -> None:
        ltype = LTYPEMAP[ltype_str]
        addr = parse_addr(addr_str)
        # print(f"label addr ${addr:05X} type {ltype} label {label!r}")
        self.rom.set_label(addr, label)
        self.annot_set_addr_type(addr, ltype, ltype_str)

    def _annotcmd_arraylabel(
        self, addr_str: str, ltype_str: str, llen_str: str, label: str
    ) -> None:
        ltype = LTYPEMAP[ltype_str]
        llen = parse_int(llen_str)
        addr = parse_addr(addr_str)
        lsize = LTYPESIZE[ltype]
        self.rom.set_label(addr, label)
        for i in range(llen):
            self.annot_set_addr_type(addr + (i * lsize), ltype, ltype_str)

    # splitaddr 00:26F9 hi 00:2872
    def _annotcmd_splitaddr(
        self, from_addr_str: str, part: str, to_addr_str: str
    ) -> None:
        from_addr = parse_addr(from_addr_str)
        to_addr = parse_addr(to_addr_str)
        if part == "lo":
            self.rom.set_addr_type(from_addr, AT.DataByteLabelLo)
            assert from_addr not in self.rom.addr_refs
            self.rom.addr_refs[from_addr] = to_addr
        elif part == "hi":
            self.rom.set_addr_type(from_addr, AT.DataByteLabelHi)
            assert from_addr not in self.rom.addr_refs
            self.rom.addr_refs[from_addr] = to_addr
        else:
            raise Exception(f"invalid splitaddr type {part!r}")

    def annot_set_addr_type(self, addr: int, ltype: AT, ltype_str: str) -> None:
        self.rom.set_addr_type(addr, ltype)
        if ltype == AT.DataWordLabel:
            if (
                addr < 0xC000
            ):  # Don't try to load from RAM and accidentally load from bank 03!
                val = struct.unpack("<H", self.rom.data[addr : addr + 2])[0]
                self.rom.ensure_label(val, relative_to=addr)
                if ltype_str == "codewptr":
                    if val not in self.rom.addr_types:
                        self.rom.tracer_stack.append(val)

    ANNOTCMDS = {
        "code": _annotcmd_code,
        "label": _annotcmd_label,
        "arraylabel": _annotcmd_arraylabel,
        "splitaddr": _annotcmd_splitaddr,
    }


def parse_int(s: str) -> int:
    if s.startswith("$"):
        return int(s[1:], 16)
    else:
        return int(s)


def parse_addr(s: str) -> int:
    if len(s) != 7 or s[2] != ":":
        raise Exception(f"expected bb:pppp for addr, got {s!r} instead")
    bank_idx = int(s[0:][:2], 16)
    virt_addr = int(s[3:][:4], 16)
    if bank_idx == 0x00:
        if not (0x0000 <= virt_addr <= 0x3FFF):
            raise Exception(f"TODO: support 00 bank for slot for {s!r}")
    elif bank_idx == 0x01:
        if not (0x4000 <= virt_addr <= 0x7FFF):
            raise Exception(f"TODO: support 01 bank for slot for {s!r}")
    elif bank_idx == 0x02:
        if not (0x8000 <= virt_addr <= 0xBFFF):
            raise Exception(f"TODO: support 02 bank for slot for {s!r}")
    elif bank_idx == 0xF0:
        if not (0xC000 <= virt_addr <= 0xFFFF):
            raise Exception(f"TODO: support F0 bank for slot for {s!r}")
    else:
        raise Exception(f"TODO: support bank for {s!r}")

    return virt_addr
