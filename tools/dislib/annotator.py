from __future__ import annotations

import struct

from typing import TYPE_CHECKING

from dislib.miscdefs import (
    AT,
    LTYPEMAP,
    LTYPESIZE,
    PhysAddress,
    VirtAddress,
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
        virt_addr = parse_addr(addr_str)
        # print(f"code addr ${addr:05X} label {label!r}")
        phys_addr = self.rom.virt_to_phys(virt_addr)
        if phys_addr not in self.rom.addr_types:
            self.rom.tracer_stack.append(virt_addr)
        self.rom.set_label(virt_addr, label)

    def _annotcmd_label(self, addr_str: str, ltype_str: str, label: str) -> None:
        ltype = LTYPEMAP[ltype_str]
        virt_addr = parse_addr(addr_str)
        # print(f"label addr ${addr:05X} type {ltype} label {label!r}")
        self.rom.set_label(virt_addr, label)
        self.annot_set_addr_type(virt_addr, ltype, ltype_str)

    def _annotcmd_arraylabel(
        self, addr_str: str, ltype_str: str, llen_str: str, label: str
    ) -> None:
        ltype = LTYPEMAP[ltype_str]
        llen = parse_int(llen_str)
        addr = parse_addr(addr_str)
        lsize = LTYPESIZE[ltype]
        self.rom.set_label(addr, label)
        for i in range(llen):
            self.annot_set_addr_type(
                self.rom.add_to_virt(addr, (i * lsize)), ltype, ltype_str
            )

    def _annotcmd_stridearraylabel(
        self, addr_str: str, lstride_str: str, ltype_str: str, llen_str: str, label: str
    ) -> None:
        lstride = parse_int(lstride_str)
        ltype = LTYPEMAP[ltype_str]
        llen = parse_int(llen_str)
        addr = parse_addr(addr_str)
        lsize = LTYPESIZE[ltype]
        self.rom.set_label(addr, label)
        for i in range(llen):
            self.annot_set_addr_type(
                self.rom.add_to_virt(addr, (i * lstride)), ltype, ltype_str
            )

    def _annotcmd_splitaddr(
        self, from_addr_str: str, part: str, to_addr_str: str
    ) -> None:
        from_addr = parse_addr(from_addr_str)
        to_addr = parse_addr(to_addr_str)
        phys_from_addr = self.rom.virt_to_phys(from_addr)
        if part == "lo":
            self.rom.set_addr_type(phys_from_addr, AT.DataByteLabelLo)
            assert phys_from_addr not in self.rom.addr_refs
            self.rom.addr_refs[phys_from_addr] = to_addr
        elif part == "hi":
            self.rom.set_addr_type(phys_from_addr, AT.DataByteLabelHi)
            assert phys_from_addr not in self.rom.addr_refs
            self.rom.addr_refs[phys_from_addr] = to_addr
        else:
            raise Exception(f"invalid splitaddr type {part!r}")

    def _annotcmd_forceimm(self, addr_str: str) -> None:
        addr = parse_addr(addr_str)
        self.rom.forced_immediates.add(self.rom.virt_to_phys(addr))

    def _annotcmd_bankslot(self, bank_idx_str: str, slot_idx_str: str) -> None:
        assert len(bank_idx_str) == 2
        assert len(slot_idx_str) == 1
        bank_idx = int(bank_idx_str, 16)
        slot_idx = int(slot_idx_str)
        assert 0 <= slot_idx <= 3
        for addr in range(
            bank_idx * self.rom.bank_size, (bank_idx + 1) * self.rom.bank_size, 1
        ):
            self.rom.bank_overrides[slot_idx][PhysAddress(addr)] = bank_idx

    def _annotcmd_banksetting(
        self,
        slot_idx_str: str,
        bank_idx_str: str,
        start_addr_str: str,
        end_addr_str: str,
    ) -> None:
        assert len(slot_idx_str) == 1
        assert len(bank_idx_str) == 2
        slot_idx = int(slot_idx_str)
        bank_idx = int(bank_idx_str, 16)
        start_addr = parse_addr(start_addr_str)
        end_addr = parse_addr(end_addr_str)
        assert start_addr[0] == end_addr[0]
        phys_start = self.rom.virt_to_phys(start_addr)
        phys_end = self.rom.virt_to_phys(end_addr)
        assert 0 <= slot_idx <= 3
        for addr in range(phys_start, phys_end, 1):
            self.rom.bank_overrides[slot_idx][PhysAddress(addr)] = bank_idx

    def _annotcmd_binexport(self, addr_str: str, len_str: str, fname: str) -> None:
        assert len(len_str) == 5
        length = int(len_str, 16)
        addr = parse_addr(addr_str)
        assert "\\" not in fname  # We only use forward slashes here.
        phys_addr = self.rom.virt_to_phys(addr)
        blob = self.rom.data[phys_addr : phys_addr + length]
        assert len(blob) == length
        assert phys_addr not in self.rom.binexports
        print(f"bin ${phys_addr:05X} len ${length:05X} {length:6d} file {fname!r}")
        self.rom.binexports[phys_addr] = (length, fname)
        for offs in range(phys_addr, phys_addr + length, 1):
            self.rom.set_addr_type(PhysAddress(offs), AT.File)
        with open(fname, "wb") as outfp:
            outfp.write(blob)

    def annot_set_addr_type(
        self, virt_addr: VirtAddress, ltype: AT, ltype_str: str
    ) -> None:
        phys_addr = self.rom.virt_to_phys(virt_addr)
        self.rom.set_addr_type(phys_addr, ltype)
        if ltype == AT.DataWordLabel:
            # GUARD: Don't try to load from RAM!
            if virt_addr[0] < self.rom.bank_count:
                val = struct.unpack("<H", self.rom.data[phys_addr : phys_addr + 2])[0]
                val_virt = self.rom.naive_to_virt(val, relative_to=virt_addr)
                # if virt_addr[0] == 0x03:
                #     print(hex(virt_addr[0]), hex(virt_addr[1]), hex(val), hex(val_virt[0]), hex(val_virt[1]))
                self.rom.ensure_label(val_virt, relative_to=virt_addr)
                if ltype_str == "codewptr":
                    if self.rom.virt_to_phys(val_virt) not in self.rom.addr_types:
                        self.rom.tracer_stack.append(val_virt)

    ANNOTCMDS = {
        "code": _annotcmd_code,
        "label": _annotcmd_label,
        "arraylabel": _annotcmd_arraylabel,
        "stridearraylabel": _annotcmd_stridearraylabel,
        "splitaddr": _annotcmd_splitaddr,
        "forceimm": _annotcmd_forceimm,
        "bankslot": _annotcmd_bankslot,
        "banksetting": _annotcmd_banksetting,
        "binexport": _annotcmd_binexport,
    }


def parse_int(s: str) -> int:
    if s.startswith("$"):
        return int(s[1:], 16)
    else:
        return int(s)


def parse_addr(s: str) -> VirtAddress:
    if len(s) != 7 or s[2] != ":":
        raise Exception(f"expected bb:pppp for addr, got {s!r} instead")
    bank_idx = int(s[0:][:2], 16)
    offs = int(s[3:][:4], 16)
    return VirtAddress((bank_idx, offs))
