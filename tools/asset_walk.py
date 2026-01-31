#!/usr/bin/env python3

from __future__ import annotations

import enum
import logging
import struct
import sys

from typing import (
    Optional,
)

import tkinter
import tkinter.ttk


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
    )
    (infname,) = sys.argv[1:]
    data = open(infname, "rb").read()
    rom = Rom(data=data)
    rom.find_everything()

    tkapp = TkApp(rom=rom)
    tkapp.run()


class TkApp:
    def __init__(self, *, rom: Rom) -> None:
        self.rom = rom

    def run(self) -> None:
        self._build_widgets()

        self.tk.mainloop()

    def _build_widgets(self) -> None:
        self.tk = tkinter.Tk(className="s1sms_asset_walk")
        self.tk.wm_title("Sonic 1 SMS Asset Walker")

        region_ordering = list(range(len(self.rom.region_list)))
        region_ordering.sort(
            key=lambda ri: (
                self.rom.region_list[ri][0] if self.rom.region_list[ri][0] else -1,
                self.rom.region_list[ri][2],
                -self.rom.region_list[ri][3],
            )
        )

        self.tv_regions_tags: dict[Optional[int], str] = {
            None: "",
        }
        self.tv_regions = tkinter.ttk.Treeview(
            master=self.tk,
            columns=["Length", "Description"],
            height=40,
        )
        self.tv_regions_y_scroll = tkinter.ttk.Scrollbar(
            master=self.tk,
            orient="vertical",
            command=self.tv_regions.yview,
        )
        self.tv_regions_x_scroll = tkinter.ttk.Scrollbar(
            master=self.tk,
            orient="horizontal",
            command=self.tv_regions.xview,
        )
        self.tv_regions.configure(
            yscrollcommand=self.tv_regions_y_scroll.set,
            xscrollcommand=self.tv_regions_x_scroll.set,
        )
        self.tv_regions.heading("#0", text="At")
        self.tv_regions.heading("Length", text="Len")
        self.tv_regions.heading("Description", text="Description")
        self.tv_regions.column("#0", width=130, stretch=False)
        self.tv_regions.column("Length", width=100, stretch=False)
        self.tv_regions.column("Description", width=600)
        for ri in region_ordering:
            rparent, rt, rstart, rlen, rdesc = self.rom.region_list[ri]
            self.tv_regions_tags[ri] = self.tv_regions.insert(
                self.tv_regions_tags[rparent],
                "end",
                text=f"${rstart:05X}",
                values=[
                    f"${rlen:05X}",
                    rdesc,
                ],
            )

        self.tv_regions.heading("#0", text="At")
        self.tv_regions.grid(sticky="nswe")
        self.tv_regions_y_scroll.grid(sticky="nsw", column=1, row=0)
        self.tv_regions_x_scroll.grid(sticky="nwe", column=0, row=1)
        self.tk.grid_columnconfigure(0, weight=1)
        self.tk.grid_rowconfigure(0, weight=1)


class RegionType(enum.Enum):
    unmapped = enum.auto()
    misc = enum.auto()
    level_header_pointer = enum.auto()
    level_header = enum.auto()
    level_metatile_layout = enum.auto()
    level_object_layout = enum.auto()
    art_tiles = enum.auto()
    art_tilemap = enum.auto()


class Rom:
    def __init__(self, *, data: bytes) -> None:
        self.log = logging.getLogger(self.__class__.__name__)
        self.data = data
        self.region_list: list[tuple[Optional[int], RegionType, int, int, str]] = []
        self.unmapped_regions: dict[Optional[int], list[tuple[int, int]]] = {}

    def find_everything(self) -> None:
        regions = [
            (0x00000, 0x0C000, "code and stuff"),
            (0x0C000, 0x04000, "sound driver"),
            (0x10000, 0x05580, "4x4 tile layouts"),
            (0x15580, 0x0004A, "level header pointers relative to $15580"),
            (0x155CA, 0x004EA, "level headers"),
            (0x15AB4, 0x00510, "level object layouts"),
            (0x15FC4, 0x00E26, "compressed transparent tilemaps"),
            (0x16DEA, 0x09216, "level block layouts"),
            (0x20000, 0x06000, "uncompressed art?"),
            (0x26000, 0x0A000, "compressed art, part 1"),
            (0x30000, 0x0F9ED, "compressed art, part 2"),
            (0x3F9ED, 0x00010, "tile physics type LUT? pointers relative to $3B9ED"),
            (0x3F9FD, 0x00603, "tile physics type LUTs?"),
        ]
        prev_addr = 0x00000
        for rstart, rlen, rdesc in regions:
            self.add_region(rt=RegionType.misc, start=rstart, length=rlen, desc=rdesc)
            assert (
                rstart == prev_addr
            ), f"gap, expected start at ${prev_addr:05X}, got ${rstart:05X} instead"
            prev_addr += rlen
        assert prev_addr == 0x40000, f"gap at end from ${prev_addr:05X}"

        # Handle miscellaneous art
        misc_art = [
            (0x0C, 0x0000, "World Map 1, VRAM $0000"),
            (0x09, 0x526B, "World Map 1, VRAM $2000"),
            (0x09, 0xB92E, "World Map 1, VRAM $3000"),
            (0x0C, 0x1801, "World Map 2, VRAM $0000"),
            (0x09, 0x5942, "World Map 2, VRAM $2000"),
            (0x09, 0xB92E, "World Map 2, VRAM $3000"),
            (0x09, 0x2000, "00:1296 UNKNOWN, VRAM $0000"),
            (0x09, 0x4B0A, "00:1296 UNKNOWN, VRAM $2000"),
            (0x09, 0x351F, "00:1411 UNKNOWN, VRAM $0000"),
            (0x09, 0xB92E, "Score Tally Screen, VRAM $3000"),
            (0x09, 0x351F, "Score Tally Screen, VRAM $0000"),
            (0x09, 0xB92E, "00:2172 UNKNOWN, VRAM $3000"),
            (0x0C, 0x0000, "00:25A9 UNKNOWN, VRAM $0000"),
            (0x0C, 0x1801, "00:26AB UNKNOWN, VRAM $0000"),
            (0x09, 0x4B0A, "00:26AB UNKNOWN, VRAM $2000"),
            (0x09, 0x4294, "Signpost, VRAM $2000"),
            (0x09, 0xAEB1, "GHZ3 Boss, VRAM $2000"),
            (0x0C, 0xDA28, "01:7916 UNKNOWN, VRAM $2000"),
            (0x09, 0xAEB1, "JUN3 Boss, VRAM $2000"),
            (0x0C, 0xE508, "BRI3 Boss, VRAM $2000"),
            (0x0C, 0xE508, "LAB3 Boss, VRAM $2000"),
            (0x0C, 0xEF3F, "SCR3 Boss, VRAM $2000"),
            (0x0C, 0xEF3F, "SKY3 Boss (zapper), VRAM $2000"),
        ]
        for abank, aoffs, adesc in misc_art:
            astart = (abank * 0x4000) + aoffs
            self.add_compressed_art_tiles(
                start=astart,
                desc=adesc,
            )

        # Handle artmaps in bank $05 slot 1
        artmaps = [
            (0x627E, 0x0178, "World Map 1, high byte $10"),
            (0x63F6, 0x0145, "World Map 1, high byte $00"),
            (0x653B, 0x0170, "World Map 2, high byte $10"),
            (0x66AB, 0x0153, "World Map 2, high byte $00"),
            (0x6000, 0x012E, "00:1296 UNKNOWN, high byte $00"),
            (0x67FE, 0x0032, "00:1411 UNKNOWN, high byte $00"),
            (0x612E, 0x00BB, "Score Tally, Normal, high byte $00"),
            (0x61E9, 0x0095, "Score Tally, Special, high byte $00"),
            (0x6830, 0x0179, "00:25A9 UNKNOWN, high byte $00"),
            (0x69A9, 0x0145, "00:267D UNKNOWN, high byte $00"),
            (0x6C61, 0x0189, "00:26AB UNKNOWN, high byte $00"),
        ]
        for aoffs, alen, adesc in artmaps:
            self.add_region(
                rt=RegionType.art_tilemap,
                start=aoffs + 0x10000,
                length=alen,
                desc=adesc,
            )

        self.walk_level_headers(headers_ptr=0x15580, base_ptr=0x14000)

        # Now add all unmapped regions.
        for rparent, rlist in self.unmapped_regions.items():
            for rstart, rlen in rlist:
                self.log.warning(
                    f"Found unmapped region {rstart:05X}/{rlen:05X} (last byte {rstart+rlen-1:05X})"
                )
                self.region_list.append(
                    (rparent, RegionType.unmapped, rstart, rlen, "### UNMAPPED ###")
                )

    def add_region(self, *, rt: RegionType, start: int, length: int, desc: str) -> None:
        # Check if we have a parent, be as specific as we can
        parent: Optional[int] = None
        new_idx = len(self.region_list)
        for other_idx, (oparent, ort, ostart, olen, odesc) in enumerate(
            self.region_list
        ):
            if start >= ostart and start + length <= ostart + olen:
                # If this is an alias, treat it as such
                if start == ostart and length == olen:
                    # It is.
                    assert (
                        rt == ort
                    ), f"region alias type mismatch, tried to turn {ort!r} into {rt!r}"
                    parent = oparent
                    break
                else:
                    parent = other_idx
            else:
                assert (
                    start >= ostart + olen or start + length <= ostart
                ), f"New region {start:05X}/{length:05X} partially overlaps region at {ostart:05X}:{olen:05X}"

        # Mark unmapped regions as mapped.
        if parent not in self.unmapped_regions:
            if parent is None:
                self.unmapped_regions[parent] = [(0x00000, 0x40000)]
            else:
                oparent, ort, ostart, olen, odesc = self.region_list[parent]
                self.unmapped_regions[parent] = [(ostart, olen)]

        end = start + length
        ui = 0
        while ui < len(self.unmapped_regions[parent]):
            ustart, ulen = self.unmapped_regions[parent][ui]
            uend = ustart + ulen

            if end <= ustart or uend <= start:
                # No overlap! Leave this alone.
                ui += 1
            else:
                # There is an overlap.
                del self.unmapped_regions[parent][ui]
                if end < uend:
                    # Got unmapped space after the new mapping.
                    self.unmapped_regions[parent].insert(ui, (end, (uend - end)))
                    ui += 1
                if ustart < start:
                    # Got unmapped space before the new mapping.
                    self.unmapped_regions[parent].insert(ui, (ustart, (start - ustart)))
                    ui += 1

        # Add region
        self.region_list.append((parent, rt, start, length, desc))

        # Some debug text!
        parent_str = "-----"
        if parent is not None:
            parent_str = f"{parent:5d}"
        self.log.debug(
            f"Region {new_idx:5d}: ${start:05X}/${length:05X} parent {parent_str}: {self.region_list[new_idx][4]!r}"
        )

    def walk_level_headers(self, *, headers_ptr: int, base_ptr: int) -> None:
        # Compute the header range
        headers_start, headers_final = base_ptr + 0x4000, 0
        hptr = headers_ptr
        level_count = 0

        while hptr < headers_start:
            li = level_count
            level_count += 1
            self.add_region(
                rt=RegionType.level_header_pointer,
                start=hptr,
                length=2,
                desc=f"Level ${li:02X} header pointer",
            )
            (hoffs,) = struct.unpack("<H", self.data[hptr : hptr + 2])
            hptr += 2
            if hoffs != 0:
                hoffs += headers_ptr
                self.add_region(
                    rt=RegionType.level_header,
                    start=hoffs,
                    length=37,
                    desc=f"Level ${li:02X} header",
                )
                headers_start = min(headers_start, hoffs)
                headers_final = max(headers_final, hoffs)
            # self.log.debug(f"header ${li:02X} ${hoffs:05X}")

        self.log.info(f"level header pointers found: {level_count:3d}")
        headers_count = ((headers_final + 37) - headers_start) // 37
        self.log.info(f"level headers found: {headers_count:3d}")

        for hi, hoffs in enumerate(range(headers_start, headers_final + 37, 37)):
            header = self.data[hoffs : hoffs + 37]
            self.add_region(
                rt=RegionType.level_header,
                start=hoffs,
                length=37,
                desc=f"Level header index ${hi:02X}",
            )
            # header_str = " ".join(f"{v:02X}" for v in header)
            (
                h00,
                hlx,
                hly,
                hx0,
                hx1,
                hy0,
                hy1,
                hstartx,
                hstarty,
                hlayoutoffs_14000,
                hlayoutcmpsize,
                hwordB,
                hart0offs_30000_V0000,
                hart1bank,
                hart1offs_V2000,
                hbyteC,
                hbyteD,
                hpalcyclen,
                hbyteF,
                hobjoffs_15580,
                hbyteG,
                hbyteH,
                hbyteI,
                hbyteJ,
                hmusicidx,
            ) = struct.unpack("<B HH HHHH BB HH H HBH BBBB H BBBB B", header[:37])
            header_str = f"{h00:02X}"
            header_str += f" ({hlx:04X} {hly:04X})"
            header_str += f" ([{hx0:04X} {hx1:04X}], [{hy0:04X} {hy1:04X}])"
            header_str += f" ({hstartx:02X} {hstarty:02X})"
            header_str += f" {hlayoutoffs_14000:04X}"
            header_str += f" {hlayoutcmpsize:04X}"
            header_str += f" {hwordB:04X}"
            header_str += f" {hart0offs_30000_V0000:04X}"
            header_str += f" {hart1bank:02X}"
            header_str += f" {hart1offs_V2000:04X}"
            header_str += f" {hbyteC:02X}"
            header_str += f" ({hbyteD:02X}"
            header_str += f" {hpalcyclen:02X})"
            header_str += f" {hbyteF:02X}"
            header_str += f" {hobjoffs_15580:04X}"
            header_str += f" {hbyteG:02X}"
            header_str += f" {hbyteH:02X}"
            header_str += f" {hbyteI:02X}"
            header_str += f" {hbyteJ:02X}"
            header_str += f" {hmusicidx:02X}"
            self.add_region(
                rt=RegionType.level_metatile_layout,
                start=hlayoutoffs_14000 + 0x14000,
                length=hlayoutcmpsize,
                desc=f"Level metatile layout for header ${hi:02X}",
            )
            obj_count = self.data[hobjoffs_15580 + 0x15580] - 1
            obj_len = 1 + (3 * obj_count)
            self.add_region(
                rt=RegionType.level_object_layout,
                start=hobjoffs_15580 + 0x15580,
                length=obj_len,
                desc=f"Level object layout for header ${hi:02X}",
            )

            self.add_compressed_art_tiles(
                start=hart0offs_30000_V0000 + 0x30000,
                desc=f"Art for level header ${hi:02X}, VRAM $0000",
            )
            self.add_compressed_art_tiles(
                start=hart1offs_V2000 + (0x4000 * hart1bank),
                desc=f"Art for level header ${hi:02X}, VRAM $2000",
            )

            self.log.debug(f"header ${hoffs:05X} {header_str}")

    def add_compressed_art_tiles(self, *, start: int, desc: str) -> None:
        # Walk the art somehow!
        body_offs = start
        magic = self.data[body_offs : body_offs + 2]
        assert magic == b"HY", f"Invalid header ID for art at {start:05X}"
        body_offs += 2
        backrefs_offs, rows_offs, row_count = struct.unpack(
            "<HHH", self.data[body_offs : body_offs + 6]
        )
        body_offs += 6
        backrefs_offs += start
        rows_offs += start
        bitmask_offs = body_offs
        # If the bit mask was the final pointer, this would be a lot easier to calculate.
        # It's not, so we actually have to walk the bitmask table and count bits.
        #
        # But it could be worse. If the final pointer was the backrefs,
        # we'd have to walk that and find out how many offsets are 16-bit and how many are 8-bit.
        #
        # ... actually, I'm not sure if that would actually be worse.
        assert bitmask_offs < backrefs_offs < rows_offs

        full_row_count = 0
        assert row_count % 8 == 0
        for byte_idx in range(row_count // 8):
            v = self.data[bitmask_offs + byte_idx]
            # Get the population count
            v = (v & 0x55) + ((v >> 1) & 0x55)
            v = (v & 0x33) + ((v >> 2) & 0x33)
            v = (v & 0x0F) + ((v >> 4) & 0x0F)
            assert 0 <= v <= 8
            full_row_count += 8 - v

        end_offs = rows_offs + (full_row_count * 4)
        self.add_region(
            rt=RegionType.art_tiles,
            start=start,
            length=end_offs - start,
            desc=desc,
        )


if __name__ == "__main__":
    main()
