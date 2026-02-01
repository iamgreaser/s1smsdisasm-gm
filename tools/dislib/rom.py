from __future__ import annotations

import struct

from typing import (
    Optional,
)

from dislib.annotator import Annotator
from dislib.miscdefs import (
    AT,
    PhysAddress,
    VirtAddress,
)
from dislib.saver import Saver
from dislib.tracer import Tracer


class Rom:
    bank_size = (
        16 * 1024
    )  # FIXED SIZE FOR THE SEGA MASTER SYSTEM AND GAME GEAR PLATFORMs
    bank_count = 16  # Set to 16 for a 256 KB ROM
    rom_crc = 0xB519E833

    def __init__(self, *, data: bytes) -> None:
        self.data = data
        self.addr_types: dict[PhysAddress, AT] = {}
        self.label_to_addr: dict[str, VirtAddress] = {}
        self.labels_from_addr: dict[PhysAddress, list[str]] = {}
        self.addr_refs: dict[PhysAddress, VirtAddress] = {}
        self.tracer_stack: list[VirtAddress] = []
        self.op_decodes: dict[PhysAddress, tuple[VirtAddress, int, str]] = {}
        self.forced_immediates: set[PhysAddress] = set()
        self.binexports: dict[PhysAddress, tuple[int, str]] = {}

        # Never ever do this unless you like really annoying really subtle Python-esque bugs!
        # self.bank_overrides: list[dict[PhysAddress, int]] = [{}] * 4
        # Do this instead.
        self.bank_overrides: list[dict[PhysAddress, int]] = [{} for i in range(4)]

    def load_annotations(self, *, file_name: str) -> None:
        annotator = Annotator(rom=self)
        with open(file_name, "r") as infp:
            for line in infp.readlines():
                annotator.annotate_line(line)

    def set_addr_type(self, phys_addr: PhysAddress, addr_type: AT) -> None:
        # print(phys_addr, self.addr_types.get(phys_addr, None), addr_type, self.tracer_stack)
        if self.addr_types.get(phys_addr, addr_type) == addr_type:
            if (
                phys_addr >= 1
                and self.addr_types.get(PhysAddress(phys_addr - 0x01), AT.DataByte)
                == AT.DataWord
            ):
                # Downsize for a split
                self.addr_types[PhysAddress(phys_addr - 0x01)] = AT.DataByte
            elif addr_type == AT.File and phys_addr in self.addr_types:
                raise Exception(f"overlapping files at {phys_addr:05X}")
            self.addr_types[phys_addr] = addr_type
        else:
            other_type = self.addr_types[phys_addr]
            if other_type == AT.DataWord and addr_type == AT.DataByte:
                # Downsize for a split
                self.addr_types[PhysAddress(phys_addr + 0x00)] = AT.DataByte
                self.addr_types[PhysAddress(phys_addr + 0x01)] = AT.DataByte
            elif other_type == AT.DataByte and addr_type == AT.DataWord:
                # Block upsize
                pass
            elif other_type == AT.File or addr_type == AT.File:
                # A file is a file is a file
                self.addr_types[phys_addr] = AT.File
            elif (
                other_type in {AT.DataByteLabelLo, AT.DataByteLabelHi}
                and addr_type == AT.DataByte
            ):
                # Split label reference
                pass
            else:
                print("FIXME: Op type derailment!")
                print(
                    phys_addr,
                    self.addr_types.get(phys_addr, None),
                    addr_type,
                    self.tracer_stack,
                )

    def set_label(self, virt_addr: VirtAddress, label: str) -> None:
        if label in self.label_to_addr:
            assert self.label_to_addr[label] == virt_addr
            return
        else:
            # Don't track relative labels here
            if not (
                label.strip("-") == ""
                or label.strip("+") == ""
                or label == "__"
                or label.startswith("@")
            ):
                self.label_to_addr[label] = virt_addr
            phys_addr = self.virt_to_phys(virt_addr)
            if phys_addr not in self.labels_from_addr:
                self.labels_from_addr[phys_addr] = []
            self.labels_from_addr[phys_addr].append(label)

    def ensure_label(
        self,
        virt_addr: VirtAddress,
        *,
        relative_to: VirtAddress,
        allow_relative_labels: bool = False,
    ) -> str:
        phys_addr = self.virt_to_phys(virt_addr)
        if not phys_addr in self.labels_from_addr:
            if virt_addr[0] >= 0xF0:
                self.set_label(virt_addr, f"var_{(phys_addr&0xFFFF)+0xC000:04X}")
            elif phys_addr < 0xC000:
                # This is so I don't have to undo an enormous diff.
                self.set_label(virt_addr, f"addr_{phys_addr:05X}")
            else:
                assert virt_addr[1] < 0xC000 or virt_addr[0] == 0xF0, "fuck you"
                self.set_label(virt_addr, f"addr_{virt_addr[0]:02X}_{virt_addr[1]:04X}")
        label = self.labels_from_addr[phys_addr][0]
        if allow_relative_labels:
            if label == "__":
                if virt_addr[1] > relative_to[1]:
                    return "_f"
                elif virt_addr[1] < relative_to[1]:
                    return "_b"
                else:
                    raise Exception("TODO: Handle this `__` label case")
            else:
                return label
        else:
            if label == "__" or label.strip("+-") == "" or label.startswith("@"):
                # Relative label - use a constant instead.
                return f"${virt_addr[1]:04X}"
            else:
                return label

    def run_tracer(self) -> None:
        tracer = Tracer(rom=self)
        tracer.run()

    def save(self, *, file_name: str) -> None:
        with open(file_name, "w") as outfp:
            saver = Saver(rom=self, outfp=outfp)
            saver.save()

    def virt_to_phys(self, v: VirtAddress) -> PhysAddress:
        return PhysAddress((v[0] * self.bank_size) + (v[1] % self.bank_size))

    _DEFAULT_PHYS_TO_VIRT_MAPPINGS = {
        0x00: 0x0000,
        0x01: 0x4000,
        0xF0: 0xC000,
        # Everything else becomes 0x8000-based.
    }

    def phys_to_virt(self, p: PhysAddress, *, relative_to: VirtAddress) -> VirtAddress:
        bank_idx = p // self.bank_size
        bank_offs = p % self.bank_size
        virt_base = self._DEFAULT_PHYS_TO_VIRT_MAPPINGS.get(bank_idx, 0x8000)
        if p in self.bank_overrides[1] and self.bank_overrides[1][p] == bank_idx:
            virt_base = 0x4000
        elif p in self.bank_overrides[2] and self.bank_overrides[2][p] == bank_idx:
            virt_base = 0x8000
        return VirtAddress(
            (
                bank_idx,
                bank_offs + virt_base,
            )
        )

    _DEFAULT_NAIVE_VIRT_MAPPING = {
        0x0: 0x00,
        0x1: 0x01,
        0x2: 0x02,
        0x3: 0xF0,
    }

    def naive_to_virt(self, val: int, *, relative_to: VirtAddress) -> VirtAddress:
        slot_idx = val // self.bank_size
        phys_relative_to = self.virt_to_phys(relative_to)
        return VirtAddress(
            (
                self.bank_overrides[slot_idx].get(
                    phys_relative_to, self._DEFAULT_NAIVE_VIRT_MAPPING[slot_idx]
                ),
                (val % self.bank_size) + (slot_idx * self.bank_size),
            )
        )

    def add_to_virt(self, base: VirtAddress, offs: int) -> VirtAddress:
        old_offs = base[1]
        new_offs = base[1] + offs
        old_slot = old_offs // self.bank_size
        new_slot = new_offs // self.bank_size
        new_bank = base[0]
        if old_slot != new_slot:
            print(
                f"WARNING: Virtual address {base[0]:02X}:{old_offs:04X} -> :{new_offs:04X} crosses slot boundary!"
            )
            new_bank += new_offs // self.bank_size
        return VirtAddress((new_bank, new_offs))
