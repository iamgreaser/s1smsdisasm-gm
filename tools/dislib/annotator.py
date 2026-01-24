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

        if line != "":
            # Extract a command
            cmd, sep, line = line.partition(" ")
            self.ANNOTCMDS[cmd](self, *line.split(" "))  # type: ignore

    def _annotcmd_code(self, addr_str: str, label: str) -> None:
        addr = parse_int(addr_str)
        # print(f"code addr ${addr:05X} label {label!r}")
        if addr not in self.rom.addr_types:
            self.rom.tracer_stack.append(addr)
        self.rom.set_label(addr, label)

    def _annotcmd_label(self, addr_str: str, ltype_str: str, label: str) -> None:
        ltype = LTYPEMAP[ltype_str]
        addr = parse_int(addr_str)
        # print(f"label addr ${addr:05X} type {ltype} label {label!r}")
        self.rom.set_label(addr, label)
        self.annot_set_addr_type(addr, ltype, ltype_str)

    def _annotcmd_arraylabel(
        self, addr_str: str, ltype_str: str, llen_str: str, label: str
    ) -> None:
        ltype = LTYPEMAP[ltype_str]
        llen = parse_int(llen_str)
        addr = parse_int(addr_str)
        lsize = LTYPESIZE[ltype]
        self.rom.set_label(addr, label)
        for i in range(llen):
            self.annot_set_addr_type(addr + (i * lsize), ltype, ltype_str)

    def annot_set_addr_type(self, addr: int, ltype: AT, ltype_str: str) -> None:
        self.rom.set_addr_type(addr, ltype)
        if ltype == AT.DataWordLabel:
            val = struct.unpack("<H", self.rom.data[addr : addr + 2])[0]
            self.rom.ensure_label(val, relative_to=addr)
            if ltype_str == "codewptr":
                if val not in self.rom.addr_types:
                    self.rom.tracer_stack.append(val)

    ANNOTCMDS = {
        "code": _annotcmd_code,
        "label": _annotcmd_label,
        "arraylabel": _annotcmd_arraylabel,
    }


def parse_int(s: str) -> int:
    if s.startswith("$"):
        return int(s[1:], 16)
    else:
        return int(s)
