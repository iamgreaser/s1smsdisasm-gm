#!/usr/bin/python3
#
# WARNING THIS PROGRAM SUCKS AND ASSUMES THINGS --GM
#
# Requirements:
# - Width divisible by 8
# - Height divisible by 16
#
# Assumptions:
# - 8bpp image, indexed
# - Uncompressed
# - A bunch of other things
# - That I didn't get the width and height around the wrong way

from __future__ import annotations

import io
import struct
import sys


def main() -> None:
    (in_fname,) = sys.argv[1:]
    with open(in_fname, "rb") as infp:
        if infp.read(2) != b"BM":
            raise Exception("not a BMP file")
        infp.seek(0x000A)
        (img_offs,) = struct.unpack("<I", infp.read(4))
        infp.seek(0x0012)
        lx, ly = struct.unpack("<II", infp.read(8))
        assert lx % 8 == 0, "width not 8-byte aligned"
        assert ly % 16 == 0, "height not 8-byte aligned"
        infp.seek(img_offs)
        chunky_data = infp.read(lx * ly)
        assert len(chunky_data) == lx * ly

    # We'll treat these as 8x16 tiles.
    # Also BMP is upside-down because lol Microsoft.
    rawdata: list[int] = []
    for ty in reversed(list(range(0, ly, 16))):
        for tx in range(0, lx, 8):
            for y in reversed(list(range(ty, ty + 16, 1))):
                planes = bytearray(4)
                pixels = chunky_data[tx + (lx * y) :][:8]
                assert len(pixels) == 8
                for x, c in enumerate(pixels):
                    v = pixels[x]
                    assert 0x00 <= v <= 0x0F, "pixel out of range of 4bpp image"
                    for pi in range(4):
                        if (v & (1 << pi)) != 0:
                            planes[pi] |= 0x80 >> x
                (packv,) = struct.unpack("<I", bytes(planes))
                rawdata.append(packv)

    # Now it's time to pack the art!
    # Note that e.g. 8 8x16 tiles is 512 bytes uncompressed.
    # Let's pack that down for the provided decompression algorithm...
    with io.BytesIO() as unctiles_fp:
        with io.BytesIO() as tilerefs_fp:
            with io.BytesIO() as bitstream_fp:
                used_tilerefs: list[int] = []
                mask = 0
                for row_idx, t in enumerate(rawdata):
                    try:
                        prev_idx = used_tilerefs.index(t)
                    except ValueError:
                        # Can't find, write a literal tile
                        used_tilerefs.append(t)
                        unctiles_fp.write(struct.pack("<I", t))
                    else:
                        # Found it, write a backref
                        mask |= 1 << (row_idx & 0x7)
                        if prev_idx < 0xF0:
                            tilerefs_fp.write(bytes([prev_idx]))
                        else:
                            tilerefs_fp.write(
                                bytes([(prev_idx >> 8) + 0xF0, prev_idx & 0xFF])
                            )

                    # Emit a mask byte every 8 rows
                    if ((row_idx + 1) & 0x7) == 0:
                        bitstream_fp.write(bytes([mask]))
                        mask = 0

                unctiles = bytearray(unctiles_fp.getvalue())
                tilerefs = bytearray(tilerefs_fp.getvalue())
                bitstream = bytearray(bitstream_fp.getvalue())

    # Build the actual structure
    outbs = b"HY"
    outbs += struct.pack("<H", 0x0008 + len(bitstream))
    outbs += struct.pack("<H", 0x0008 + len(bitstream) + len(tilerefs))
    outbs += struct.pack("<H", len(rawdata))
    outbs += bitstream
    outbs += tilerefs
    outbs += unctiles
    print(f";; uncmp = {len(rawdata)*4:5d} bytes, cmp = {len(outbs):5d} bytes")
    for i in range(0, len(outbs), 16):
        out_args = [f"${v:02X}" for v in outbs[i : i + 16]]
        print(".db " + ", ".join(out_args))


if __name__ == "__main__":
    main()
