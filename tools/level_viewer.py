#!/usr/bin/python3

from __future__ import annotations

import logging
import pathlib
import struct
import sys
import zlib

import tkinter
import tkinter.ttk

from typing import (
    MutableSequence,
    Optional,
    Sequence,
)

from edlib.gamedefs import (
    OT,
    obj_sprite_maps,
)


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
    )
    app = TkApp()
    for file_name in sys.argv[1:]:
        app.add_file(file_path=pathlib.Path(file_name))
    app.run()


layout_fname_extn_widths = {
    ".layout8": (1 << 8),
    ".layout7": (1 << 7),
    ".layout6": (1 << 6),
    ".layout5": (1 << 5),
    ".layout4": (1 << 4),
}


class TkApp:
    tm_width = 32
    tm_height = 28

    def __init__(self) -> None:
        self.level_width = 0x40
        self.level_height = 0x1000 // self.level_width
        assert self.level_width * self.level_height == 0x1000

        self.tk = tkinter.Tk(className="level_viewer")
        self.tk.wm_title("Sonic 1 SMS Level Viewer")

        self.vram = bytearray(0x4000)
        self.cram = bytearray(0x20)
        self.layout = bytearray(0x1000)
        # type, x, y
        self.object_defs: list[tuple[int, int, int]] = []

        self.layout_tile_flags = bytearray(0x100)
        self.layout_tile_specials = bytearray(0x100)
        self.layout_tilemap = bytearray(0x1000)

        self.cam_mtx = 0
        self.cam_mty = 9

        # TEST: Pre-set tileset to a cycle
        for i in range(self.tm_width * self.tm_height):
            v = i

            # Skip over tilemap and sprite attribute table
            if v >= (0x3800 >> 5):
                v += 0x0800 >> 5

            # v = (v + 0x200) & ~0x600  # force vflip
            v = (v + 0x600) & ~0x600  # force second palette
            self.vram[0x3800 + (i * 2) + 0] = v & 0xFF
            self.vram[0x3800 + (i * 2) + 1] = v >> 8

        # One variant for each:
        # +1 = hflip
        # +2 = vflip
        # +4 = palette index
        self.vram_tile_images: MutableSequence[Optional[tkinter.PhotoImage]] = [
            None for i in range(512 * 8)
        ]
        self.screen = tkinter.Canvas(
            master=self.tk,
            width=8 * 2 * self.tm_width,
            height=8 * 2 * self.tm_height,
        )
        self.screen.grid()
        self.vram_tilemap_items: MutableSequence[Optional[int]] = [None] * (
            self.tm_width * self.tm_height
        )
        # (x, y, item1, item2)
        self.vram_sprites: list[tuple[int, int, Optional[tuple[int, int]], int]] = [
            (-8, -16, None, 0)
        ] * 64
        self.vram_sprites_used = 0

    def add_file(self, *, file_path: pathlib.Path) -> None:
        if False:
            logging.debug(
                "Determining file type %(file_path)r", {"file_path": str(file_path)}
            )

        if file_path.suffix in {".art0000", ".art2000", ".art3000"}:
            self.load_art_file(
                file_path=file_path,
                vram_addr=int(file_path.suffix[len(".art") :], 16),
            )

        elif file_path.suffix in {".pal1", ".pal2", ".pal3", ".pal1c"}:
            self.load_palette(
                file_path=file_path,
                has_p0=(file_path.suffix not in {".pal2"}),
                has_p1=(file_path.suffix not in {".pal1", ".pal1c"}),
                is_cycling=(file_path.suffix in {".pal1c"}),
            )

        elif file_path.suffix in {".sonicuncart"}:
            self.load_3bpp_art(
                file_path=file_path,
                vram_addr=0x3680,
            )

        elif file_path.suffix in {".objects"}:
            self.load_object_defs(file_path=file_path)

        elif file_path.suffix in {".tilemap"}:
            self.load_tilemap(file_path=file_path)

        elif file_path.suffix in {".tileflags"}:
            self.load_tile_flags(file_path=file_path)

        elif file_path.suffix in {".tilespecials"}:
            self.load_tile_specials(file_path=file_path)

        elif file_path.suffix in layout_fname_extn_widths:
            self.load_layout(
                file_path=file_path,
                level_width=layout_fname_extn_widths[file_path.suffix],
            )

        else:
            logging.warning(
                "Could not determine type of file %(file_path)r",
                {"file_path": str(file_path)},
            )

    def load_art_file(self, *, file_path: pathlib.Path, vram_addr: int) -> None:
        assert 0x0000 <= vram_addr <= 0x3FFF
        logging.info(
            "Loading art into VRAM $%(vram_addr)04X from %(file_path)r",
            {"file_path": str(file_path), "vram_addr": vram_addr},
        )

        art = file_path.open("rb").read()
        magic, offsets_ptr, rows_ptr, row_count = struct.unpack("<HHHH", art[:8])
        assert magic == 0x5948, '"HY" signature missing from compressed art file'
        bitmask_ptr = 8
        assert row_count % 8 == 0, "non-multiple-of-8 tile count"
        assert (
            bitmask_ptr < offsets_ptr < rows_ptr
        ), "weirdly-ordered art file or not a real art file"
        assert offsets_ptr == bitmask_ptr + (row_count // 8), "gap after bit mask"
        bitmask = art[bitmask_ptr:offsets_ptr]
        offsets = art[offsets_ptr:rows_ptr]
        rows = art[rows_ptr:]
        oi = 0  # Offset index (in bytes)
        ri = 0  # Row index (in bytes)
        vi = vram_addr  # VRAM index (in bytes)
        for b in bitmask:
            for i in range(8):
                if (b & (1 << i)) == 0:
                    # Literal tile
                    use_ri = ri
                    ri += 4
                else:
                    # Offset
                    use_ri = offsets[oi]
                    oi += 1
                    if use_ri >= 0xF0:
                        # This is a long offset
                        use_ri = ((use_ri - 0xF0) << 8) + offsets[oi]
                        oi += 1
                    use_ri *= 4
                self.vram[vi : vi + 4] = rows[use_ri : use_ri + 4]
                vi += 4

        assert oi == len(offsets), "extra junk after offsets"
        assert ri == len(rows), "extra junk after rows"

    def load_palette(
        self, *, file_path: pathlib.Path, has_p0: bool, has_p1: bool, is_cycling: bool
    ) -> None:
        palette_idx_list: list[int] = []
        if has_p0:
            palette_idx_list.append(0)
        if has_p1:
            palette_idx_list.append(1)
        logging.info(
            "Loading palette from %(file_path)r, palettes %(palette_idx_list)r, cycling=%(cycling_str)s",
            {
                "file_path": str(file_path),
                "palette_idx_list": palette_idx_list,
                "cycling_str": str(int(is_cycling)),
            },
        )
        assert has_p0 or has_p1
        assert (not is_cycling) or (has_p0 and not has_p1)

        # TODO: Handle cycling palettes properly! --GM
        with file_path.open("rb") as infp:
            for pi in palette_idx_list:
                self.cram[pi * 0x10 : (pi + 1) * 0x10] = infp.read(16)

    def load_3bpp_art(self, *, file_path: pathlib.Path, vram_addr: int) -> None:
        assert 0x0000 <= vram_addr <= 0x3FFF
        logging.info(
            "Loading uncompressed 3bpp Sonic art into VRAM $%(vram_addr)04X from %(file_path)r",
            {"file_path": str(file_path), "vram_addr": vram_addr},
        )
        data = file_path.open("rb").read()
        assert len(data) == 288
        for i in range(288 // 3):
            self.vram[vram_addr + (i * 4) : vram_addr + (i * 4) + 4] = data[
                i * 3 : (i + 1) * 3
            ] + bytes([0])

    def load_layout(self, *, file_path: pathlib.Path, level_width: int) -> None:
        logging.info(
            "Loading level layout from %(file_path)r",
            {"file_path": str(file_path)},
        )

        self.level_width = level_width
        self.level_height = 0x1000 // self.level_width
        assert self.level_width * self.level_height == 0x1000

        prev_literal = -1
        self.layout = bytearray(0x1000)
        out_idx = 0
        with file_path.open("rb") as infp:
            while True:
                bs = infp.read(1)
                if bs == b"":
                    break
                v = bs[0]
                if v != prev_literal:
                    self.layout[out_idx] = v
                    out_idx += 1
                    prev_literal = v
                else:
                    repeats = infp.read(1)[0]
                    # EDGE CASE: 8-bit wraparound.
                    # Unlike ZZT, this case actually gets used!
                    if repeats == 0x00:
                        repeats = 0x100
                    for i in range(repeats):
                        self.layout[out_idx] = v
                        out_idx += 1
                    prev_literal = -1

        logging.debug(f"Layout ended at $%(end_offs)04X", {"end_offs": out_idx})

    def load_object_defs(self, *, file_path: pathlib.Path) -> None:
        logging.info(
            "Loading object defs from %(file_path)r", {"file_path": str(file_path)}
        )

        with file_path.open("rb") as infp:
            count = infp.read(1)[0]
            self.object_defs.clear()
            for i in range(count - 1):
                v, x, y = infp.read(3)
                if v not in obj_sprite_maps:
                    logging.warning(
                        "unhandled object %(v)02X at %(x)02X,%(y)02X",
                        {"x": x, "y": y, "v": v},
                    )
                else:
                    logging.debug(
                        "object %(v)02X at %(x)02X,%(y)02X",
                        {"x": x, "y": y, "v": v},
                    )
                self.object_defs.append((v, x, y))

            assert infp.read() == b""

    def load_tilemap(self, *, file_path: pathlib.Path) -> None:
        logging.info(
            "Loading tilemap from %(file_path)r", {"file_path": str(file_path)}
        )

        data = file_path.open("rb").read()
        self.layout_tilemap[: len(data)] = data

    def load_tile_flags(self, *, file_path: pathlib.Path) -> None:
        logging.info(
            "Loading tile flags from %(file_path)r", {"file_path": str(file_path)}
        )

        data = file_path.open("rb").read()
        self.layout_tile_flags[: len(data)] = data

    def load_tile_specials(self, *, file_path: pathlib.Path) -> None:
        logging.info(
            "Loading tile specials from %(file_path)r", {"file_path": str(file_path)}
        )

        data = file_path.open("rb").read()
        self.layout_tile_specials[: len(data)] = data

    def run(self) -> None:
        # Redraw everything
        self.redraw()

        # Bind buttons for scrolling
        self.tk.bind("<Key-Up>", lambda ev: self.scroll_by(0, -1))
        self.tk.bind("<Key-Down>", lambda ev: self.scroll_by(0, +1))
        self.tk.bind("<Key-Left>", lambda ev: self.scroll_by(-1, 0))
        self.tk.bind("<Key-Right>", lambda ev: self.scroll_by(+1, 0))

        # Run the main loop!
        self.tk.mainloop()

    def scroll_by(self, dx: int, dy: int) -> None:
        ox, oy = self.cam_mtx, self.cam_mty
        self.cam_mtx = max(0, min(self.level_width - (self.tm_width // 4), ox + dx))
        self.cam_mty = max(0, min(self.level_height - (self.tm_height // 4), oy + dy))
        if (ox, oy) != (self.cam_mtx, self.cam_mty):
            self.redraw()

    def redraw(self) -> None:
        # Clear info boxes
        self.screen.delete("info_boxes", "info_text")

        # Set up layout
        for cy in range(self.tm_height // 4):
            for cx in range(self.tm_width // 4):
                # Metatile index
                offs = ((cy + self.cam_mty) * self.level_width) + cx + self.cam_mtx
                mtidx = self.layout[offs]
                hi = (self.layout_tile_flags[mtidx] >> 3) & 0x10
                for ty in range(4):
                    for tx in range(4):
                        vidx = (cx * 4 + tx) + (self.tm_width * (cy * 4 + ty))
                        lo = self.layout_tilemap[tx + (4 * (ty + (4 * mtidx)))]
                        self.vram[0x3800 + (vidx * 2) + 0] = lo
                        self.vram[0x3800 + (vidx * 2) + 1] = hi

                tf = (
                    self.layout_tile_flags[mtidx]
                    if mtidx < len(self.layout_tile_flags)
                    else 0xFF
                )
                ts = (
                    self.layout_tile_specials[mtidx]
                    if mtidx < len(self.layout_tile_specials)
                    else 0xFF
                )
                self.screen.create_text(
                    ((cx * 32) + 2) * 2,
                    ((cy * 32) + 2) * 2,
                    text=f"{mtidx:02X} {offs:03X}\n{tf:02X} {ts:02X}",
                    anchor="nw",
                    fill="#FFFFFF",
                    tags=["info_text"],
                )

        # Set background
        palv = self.cram[0]
        c = 0
        c |= (((palv >> 0) & 0x3) * 0x55) << 16
        c |= (((palv >> 2) & 0x3) * 0x55) << 8
        c |= (((palv >> 4) & 0x3) * 0x55) << 0
        self.screen.configure(background=f"#{c:06X}")

        # Set up sprites
        self.vram_sprites_used = 0
        sonic_x = (((self.tm_width * 8) - 24) // 2) & ~0x1F
        sonic_y = (((self.tm_height * 8) - 32) // 2) & ~0x1F
        sonic_x += self.cam_mtx * 32
        sonic_y += self.cam_mty * 32
        (dx, dy), smaps = obj_sprite_maps[OT.player_sonic.value]
        self.maybe_draw_sprite(sonic_x + dx, sonic_y + dy, smaps[0])

        for v, tx, ty in self.object_defs:
            x = tx * 32
            y = ty * 32
            if v in obj_sprite_maps:
                (dx, dy), smaps = obj_sprite_maps[v]

                sidx = 0
                # Special cases
                if v == OT.platform_horizontal.value:
                    # This is grabbed from the tile flag index.
                    if zlib.crc32(self.layout_tile_flags[:0xB8]) == 0x5B23CE2A:
                        # GHZ (index $00)
                        sidx = 0
                    elif zlib.crc32(self.layout_tile_flags[:0x90]) == 0x753831C5:
                        # BRI (index $01)
                        sidx = 1
                    else:
                        # All other cases (probably just JUN)
                        sidx = 2

                self.maybe_draw_sprite(x + dx, y + dy, smaps[sidx])
            else:
                self.screen.create_rectangle(
                    ((x + 16) - 9 - (self.cam_mtx * 32)) * 2,
                    ((y + 16) - 6 - (self.cam_mty * 32)) * 2,
                    ((x + 16) + 9 - (self.cam_mtx * 32)) * 2,
                    ((y + 16) + 6 - (self.cam_mty * 32)) * 2,
                    fill="#000000",
                    outline="#FFFFFF",
                    width=1,
                    tags=["info_boxes"],
                )
                self.screen.create_text(
                    ((x + 16) - (self.cam_mtx * 32)) * 2,
                    ((y + 16) - (self.cam_mty * 32)) * 2,
                    text=f"{v:02X}",
                    anchor="center",
                    fill="#FFFFFF",
                    tags=["info_text"],
                )

        # Draw a 32x28 display
        for ty in range(self.tm_height):
            for tx in range(self.tm_width):
                tmi = tx + (self.tm_width * ty)
                (tdata,) = struct.unpack(
                    "<H", self.vram[0x3800 + (tmi * 2) : 0x3800 + (tmi * 2) + 2]
                )
                priority = "tile_hi" if (tdata & 0x1000) != 0 else "tile_lo"
                tdata &= 0xFFF
                tm_img = self.ensure_tile_img(tdata)

                opt_tm_lbl = self.vram_tilemap_items[tmi]
                if opt_tm_lbl is None:
                    tm_lbl = self.screen.create_image(
                        8 * 2 * tx, 8 * 2 * ty, image=tm_img, anchor="nw"
                    )
                    self.vram_tilemap_items[tmi] = tm_lbl
                else:
                    tm_lbl = opt_tm_lbl
                self.screen.itemconfigure(tm_lbl, image=tm_img, tags=[priority])

        # Sprites
        # Make sure we render these backwards!
        for si, (x, y, opt_t, tdata) in reversed(
            list(enumerate(self.vram_sprites[0 : self.vram_sprites_used]))
        ):
            if opt_t is not None:
                tag0, tag1 = opt_t
                self.screen.moveto(tag0, x * 2, (y + (8 * 0)) * 2)
                self.screen.moveto(tag1, x * 2, (y + (8 * 1)) * 2)
            else:
                tag0 = self.screen.create_image(x * 2, (y + (8 * 0)) * 2, anchor="nw")
                tag1 = self.screen.create_image(x * 2, (y + (8 * 1)) * 2, anchor="nw")
                self.vram_sprites[si] = (x, y, (tag0, tag1), tdata)

            self.screen.itemconfigure(
                tag0,
                image=self.ensure_tile_img(((tdata & 0xFE) + 0) | 0x900),
                state="normal",
            )
            self.screen.itemconfigure(
                tag1,
                image=self.ensure_tile_img(((tdata & 0xFE) + 1) | 0x900),
                state="normal",
            )
            self.screen.tag_raise(tag0)
            self.screen.tag_raise(tag1)

        # Remove excess
        for x, y, opt_t, tdata in self.vram_sprites[self.vram_sprites_used :]:
            if opt_t is not None:
                tag0, tag1 = opt_t
                self.screen.itemconfigure(
                    tag0,
                    image=None,
                    state="hidden",
                )
                self.screen.itemconfigure(
                    tag1,
                    image=None,
                    state="hidden",
                )

        # Correct ordering
        self.screen.tag_raise("tile_hi")
        self.screen.tag_lower("tile_lo")
        self.screen.tag_raise("info_boxes")
        self.screen.tag_raise("info_text")

    def maybe_draw_sprite(
        self, spr_x: int, spr_y: int, spr_data: Sequence[Sequence[int]]
    ) -> None:
        for dy, row in enumerate(spr_data):
            for dx, tile in enumerate(row):
                if tile == 0xFE:
                    continue

                x = spr_x + (dx * 8) - (self.cam_mtx * 32)
                y = spr_y + (dy * 16) - (self.cam_mty * 32)
                if x >= 8 * self.tm_width:
                    continue
                if x <= -8:
                    continue
                if y >= 8 * self.tm_height:
                    continue
                if y <= -16:
                    continue
                _, _, opt_t, _ = self.vram_sprites[self.vram_sprites_used]
                self.vram_sprites[self.vram_sprites_used] = (x, y, opt_t, tile)
                self.vram_sprites_used += 1

    def ensure_tile_img(self, tdata: int) -> tkinter.PhotoImage:
        opt_tm_img = self.vram_tile_images[tdata]
        if opt_tm_img is None:
            transparent_positions: list[tuple[int, int]] = []
            tm_img = tkinter.PhotoImage(width=8 * 2, height=8 * 2)
            self.vram_tile_images[tdata] = tm_img

            # Draw image
            outdata: list[list[str]] = []
            toffs = (tdata & 0x1FF) * 4 * 8
            xflip = 0x0 if (tdata & 0x200) != 0 else 0x7
            yflip = 0x7 if (tdata & 0x400) != 0 else 0x0
            palsel = (tdata >> 11) & 0x1
            cram = self.cram[palsel * 16 : (palsel + 1) * 16]
            for y in range(8):
                outdata.append([])
                planes = self.vram[
                    toffs + (4 * (yflip ^ y)) : toffs + (4 * ((yflip ^ y) + 1))
                ]
                for x in range(8):
                    p = 0
                    p |= ((planes[0] >> (xflip ^ x)) << 0) & (1 << 0)
                    p |= ((planes[1] >> (xflip ^ x)) << 1) & (1 << 1)
                    p |= ((planes[2] >> (xflip ^ x)) << 2) & (1 << 2)
                    p |= ((planes[3] >> (xflip ^ x)) << 3) & (1 << 3)
                    if p == 0:
                        outdata[-1].append("#000000")
                        transparent_positions.append((x, y))
                    else:
                        palv = cram[p]
                        c = 0
                        c |= (((palv >> 0) & 0x3) * 0x55) << 16
                        c |= (((palv >> 2) & 0x3) * 0x55) << 8
                        c |= (((palv >> 4) & 0x3) * 0x55) << 0
                        outdata[-1].append(f"#{c:06X}")
                    outdata[-1].append(outdata[-1][-1])
                outdata.append(outdata[-1])
            outstr = " ".join("{" + " ".join(row) + "}" for row in outdata)
            tm_img.put(outstr)
            for x, y in transparent_positions:
                for sy in range(y * 2, (y + 1) * 2, 1):
                    for sx in range(x * 2, (x + 1) * 2, 1):
                        tm_img.transparency_set(sx, sy, True)

        else:
            tm_img = opt_tm_img

        return tm_img


if __name__ == "__main__":
    main()
