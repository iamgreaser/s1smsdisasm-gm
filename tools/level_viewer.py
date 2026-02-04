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

from edlib.physdefs import (
    push_left,
    push_right,
    push_up,
    push_down,
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
    mtm_width = 8
    mtm_height = 7
    # mtm_width = 16
    # mtm_height = 16

    def __init__(self) -> None:
        self.level_width = 0x40
        self.level_height = 0x1000 // self.level_width
        assert self.level_width * self.level_height == 0x1000

        self.tk = tkinter.Tk(className="level_viewer")
        self.tk.wm_title("Sonic 1 SMS Level Viewer")

        self.vram = bytearray(0x3800)
        self.vram_metatile_map: MutableSequence[MutableSequence[int]] = [
            [0x0000] * self.mtm_width for y in range(self.mtm_height)
        ]
        self.cram = bytearray(0x20)
        self.cram_palettes: MutableSequence[MutableSequence[str]] = [
            ["#000"] * 0x10 for i in range(2)
        ]
        self.layout = bytearray(0x1000)
        # type, x, y
        self.object_defs: list[tuple[int, int, int]] = []

        self.layout_tile_flags = bytearray(0x100)
        self.layout_tile_specials = bytearray(0x100)
        self.layout_tilemap = bytearray(0x1000)

        self.cam_mtx = 0
        self.cam_mty = 16 - self.mtm_height

        # One variant for each:
        # +1 = hflip
        # +2 = vflip
        # +4 = palette index
        self.vram_metatile_images: MutableSequence[Optional[tkinter.PhotoImage]] = [
            None for i in range(256)
        ]
        self.screen = tkinter.Canvas(
            master=self.tk,
            width=32 * 2 * self.mtm_width,
            height=32 * 2 * self.mtm_height,
        )
        self.screen.grid()
        self.vram_metatile_map_items: MutableSequence[
            MutableSequence[Optional[int]]
        ] = [[None] * self.mtm_width for y in range(self.mtm_height)]
        # (x, y, item1, item2)
        self.vram_sprite_images: MutableSequence[Optional[tkinter.PhotoImage]] = [
            None
        ] * 128
        self.vram_sprites: list[tuple[int, int, Optional[int], int]] = [
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

        elif file_path.suffix in {".ringart"}:
            self.load_4bpp_art(
                file_path=file_path,
                vram_addr=0x1F80,
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
                self.set_vram(vi, 4, rows[use_ri : use_ri + 4])
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
                paldata = infp.read(16)
                self.cram[pi * 0x10 : (pi + 1) * 0x10] = paldata
                for subi, palv in enumerate(paldata):
                    c = 0
                    c |= (((palv >> 0) & 0x3) * 0x5) << 8
                    c |= (((palv >> 2) & 0x3) * 0x5) << 4
                    c |= (((palv >> 4) & 0x3) * 0x5) << 0
                    self.cram_palettes[pi][subi] = f"#{c:03X}"

    def load_3bpp_art(self, *, file_path: pathlib.Path, vram_addr: int) -> None:
        assert 0x0000 <= vram_addr <= 0x3FFF
        logging.info(
            "Loading uncompressed 3bpp Sonic art into VRAM $%(vram_addr)04X from %(file_path)r",
            {"file_path": str(file_path), "vram_addr": vram_addr},
        )
        data = file_path.open("rb").read()
        assert len(data) == 288
        for i in range(288 // 3):
            blob = data[i * 3 : (i + 1) * 3] + bytes([0])
            self.set_vram(vram_addr + (i * 4), 4, blob)

    def load_4bpp_art(self, *, file_path: pathlib.Path, vram_addr: int) -> None:
        assert 0x0000 <= vram_addr <= 0x3FFF
        logging.info(
            "Loading uncompressed 4bpp ring art into VRAM $%(vram_addr)04X from %(file_path)r",
            {"file_path": str(file_path), "vram_addr": vram_addr},
        )
        data = file_path.open("rb").read()
        assert len(data) == 128
        for i in range(128 // 4):
            blob = data[i * 4 : (i + 1) * 4]
            self.set_vram(vram_addr + (i * 4), 4, blob)

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
        self.cam_mtx = max(0, min(self.level_width - self.mtm_width, ox + dx))
        self.cam_mty = max(0, min(self.level_height - self.mtm_height, oy + dy))
        if (ox, oy) != (self.cam_mtx, self.cam_mty):
            self.redraw()

    def redraw(self) -> None:
        # Clear info boxes
        self.screen.delete("info_boxes", "info_text", "lines_physics")

        # Set up layout
        for cy in range(self.mtm_height):
            for cx in range(self.mtm_width):
                # Metatile index
                offs = ((cy + self.cam_mty) * self.level_width) + cx + self.cam_mtx
                mtidx = self.layout[offs]
                self.set_vram_metatile_map_cell(cx, cy, mtidx)
                tf = self.layout_tile_flags[mtidx]
                ts = self.layout_tile_specials[mtidx]

                if False:
                    self.screen.create_text(
                        ((cx * 32) + 2) * 2,
                        ((cy * 32) + 2) * 2,
                        text=f"{mtidx:02X} {offs:03X}\n{tf:02X} {ts:02X}",
                        anchor="nw",
                        fill="#FFFFFF",
                        tags=["info_text"],
                    )

                if False:
                    # Draw physics lines!
                    ptlist: list[tuple[int, int]] = []
                    orderlist = [
                        (0, -1, push_up),
                        (0, 1, push_down),
                        (-1, 0, push_left),
                        (1, 0, push_right),
                    ]
                    for dx, dy, basetable in orderlist:
                        for i, vbase in enumerate(basetable[tf & 0x3F]):
                            if vbase != 0x80:
                                # Convert to signed
                                vbase = (vbase ^ 0x80) - 0x80

                                v = vbase
                                x = (i * 2) + 1
                                y = (v * 2) + 1
                                if dx != 0:
                                    x, y = y, x
                                ptlist.append(
                                    (
                                        x + (cx * 8 * 4 * 2),
                                        y + (cy * 8 * 4 * 2),
                                    )
                                )

                            if vbase == 0x80 or i == 0x1F:
                                if len(ptlist) >= 1:
                                    ptlist.insert(
                                        0,
                                        (
                                            ptlist[0][0] - (dx * 4 * 2),
                                            ptlist[0][1] - (dy * 4 * 2),
                                        ),
                                    )
                                    ptlist.append(
                                        (
                                            ptlist[-1][0] - (dx * 4 * 2),
                                            ptlist[-1][1] - (dy * 4 * 2),
                                        )
                                    )
                                    self.screen.create_line(
                                        ptlist,
                                        width=3,
                                        fill="#FF00FF",
                                        tags="lines_physics",
                                    )
                                ptlist.clear()

        # Set background
        palv = self.cram[0]
        c = 0
        c |= (((palv >> 0) & 0x3) * 0x55) << 16
        c |= (((palv >> 2) & 0x3) * 0x55) << 8
        c |= (((palv >> 4) & 0x3) * 0x55) << 0
        self.screen.configure(background=f"#{c:06X}")

        # Set up sprites
        self.vram_sprites_used = 0
        sonic_x = (((self.mtm_width * 32) - 24) // 2) & ~0x1F
        sonic_y = (((self.mtm_height * 32) - 32) // 2) & ~0x1F
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
        for mty in range(self.mtm_height):
            for mtx in range(self.mtm_width):
                mtidx = self.vram_metatile_map[mty][mtx]
                hi = (self.layout_tile_flags[mtidx] >> 3) & 0x10
                priority = "tile_hi" if (hi & 0x10) != 0 else "tile_lo"
                mtm_img = self.ensure_metatile_img(mtidx)

                opt_mtm_lbl = self.vram_metatile_map_items[mty][mtx]
                if opt_mtm_lbl is None:
                    mtm_lbl = self.screen.create_image(
                        32 * 2 * mtx, 32 * 2 * mty, image=mtm_img, anchor="nw"
                    )
                    self.vram_metatile_map_items[mty][mtx] = mtm_lbl
                else:
                    mtm_lbl = opt_mtm_lbl
                self.screen.itemconfigure(mtm_lbl, image=mtm_img, tags=[priority])

        # Sprites
        # Make sure we render these backwards!
        for si, (x, y, opt_t, tdata) in reversed(
            list(enumerate(self.vram_sprites[0 : self.vram_sprites_used]))
        ):
            if opt_t is not None:
                tag0 = opt_t
                self.screen.moveto(tag0, x * 2, (y + (8 * 0)) * 2)
            else:
                tag0 = self.screen.create_image(x * 2, (y + (8 * 0)) * 2, anchor="nw")
                self.vram_sprites[si] = (x, y, tag0, tdata)

            self.screen.itemconfigure(
                tag0,
                image=self.ensure_sprite_img(tdata >> 1),
                state="normal",
            )
            self.screen.tag_raise(tag0)

        # Remove excess
        for x, y, opt_t, tdata in self.vram_sprites[self.vram_sprites_used :]:
            if opt_t is not None:
                tag0 = opt_t
                self.screen.itemconfigure(
                    tag0,
                    image=None,
                    state="hidden",
                )

        # Correct ordering
        self.screen.tag_raise("tile_hi")
        self.screen.tag_lower("tile_lo")
        self.screen.tag_raise("lines_physics")
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
                if x >= 8 * (self.mtm_width * 4):
                    continue
                if x <= -8:
                    continue
                if y >= 8 * (self.mtm_height * 4):
                    continue
                if y <= -16:
                    continue
                _, _, opt_t, _ = self.vram_sprites[self.vram_sprites_used]
                self.vram_sprites[self.vram_sprites_used] = (x, y, opt_t, tile)
                self.vram_sprites_used += 1

    def ensure_metatile_img(self, mtidx: int) -> tkinter.PhotoImage:
        opt_mtm_img = self.vram_metatile_images[mtidx]
        if opt_mtm_img is None:
            mtm_img = tkinter.PhotoImage(width=32 * 2, height=32 * 2)
            self.vram_metatile_images[mtidx] = mtm_img

            # Draw image
            for ty in range(4):
                for tx in range(4):
                    tdata = self.layout_tilemap[tx + (4 * ty) + (16 * mtidx)] & 0x0FFF
                    self.blit_tile_to_img(mtm_img, tx * 8, ty * 8, tdata)

        else:
            mtm_img = opt_mtm_img

        return mtm_img

    def ensure_sprite_img(self, sprite_idx: int) -> tkinter.PhotoImage:
        opt_spr_img = self.vram_sprite_images[sprite_idx]
        if opt_spr_img is None:
            spr_img = tkinter.PhotoImage(width=8 * 2, height=16 * 2)
            self.vram_sprite_images[sprite_idx] = spr_img

            # Draw image
            for ty in range(2):
                # Set background + bank
                tdata = (sprite_idx << 1) + 0x0900 + ty
                self.blit_tile_to_img(spr_img, 0 * 8, ty * 8, tdata)

        else:
            spr_img = opt_spr_img

        return spr_img

    def blit_tile_to_img(
        self, img: tkinter.PhotoImage, px: int, py: int, tdata: int
    ) -> None:
        transparent_positions: list[tuple[int, int]] = []
        outdata: list[list[str]] = []
        toffs = (tdata & 0x1FF) * 4 * 8
        xflip = 0x0 if (tdata & 0x200) != 0 else 0x7
        yflip = 0x7 if (tdata & 0x400) != 0 else 0x0
        palsel = (tdata >> 11) & 0x1
        cram = self.cram_palettes[palsel]
        for y in range(8):
            outdata.append([])
            addr = toffs + (4 * (yflip ^ y))
            planes = self.vram[addr : addr + 4]
            for x in range(8):
                p = 0
                p |= ((planes[0] >> (xflip ^ x)) << 0) & (1 << 0)
                p |= ((planes[1] >> (xflip ^ x)) << 1) & (1 << 1)
                p |= ((planes[2] >> (xflip ^ x)) << 2) & (1 << 2)
                p |= ((planes[3] >> (xflip ^ x)) << 3) & (1 << 3)
                palv = cram[p]
                outdata[-1] += [palv] * 2
                if p == 0:
                    transparent_positions.append((x, y))
            outdata.append(outdata[-1])
        outstr = " ".join("{" + " ".join(row) + "}" for row in outdata)
        img.put(outstr, to=(px * 2, py * 2))
        for x, y in transparent_positions:
            for sy in range(y * 2, (y + 1) * 2, 1):
                for sx in range(x * 2, (x + 1) * 2, 1):
                    img.transparency_set(sx + (px * 2), sy + (py * 2), True)

    def set_vram(self, addr: int, vram_len: int, data: bytes) -> None:
        assert len(data) == vram_len
        assert addr >= 0 and addr + vram_len <= len(self.vram)
        self.vram[addr : addr + vram_len] = data

    def set_vram_metatile_map_cell(self, x: int, y: int, v: int) -> None:
        assert 0x00 <= v <= 0xFF
        self.vram_metatile_map[y][x] = v


if __name__ == "__main__":
    main()
