from __future__ import annotations

import struct

from dislib.annotator import Annotator
from dislib.miscdefs import (
    AT,
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
        self.addr_types: dict[int, AT] = {}
        self.label_to_addr: dict[str, int] = {}
        self.labels_from_addr: dict[int, list[str]] = {}
        self.addr_refs: dict[int, int] = {}
        self.tracer_stack: list[int] = []
        self.op_decodes: dict[int, tuple[int, str]] = {}
        self.forced_immediates: set[int] = set()

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
            elif other_type in {AT.DataByteLabelLo, AT.DataByteLabelHi} and addr_type == AT.DataByte:
                # Split label reference
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
        tracer = Tracer(rom=self)
        tracer.run()

    def save(self, *, file_name: str) -> None:
        with open(file_name, "w") as outfp:
            saver = Saver(rom=self, outfp=outfp)
            saver.save()
