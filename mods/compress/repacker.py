#!/usr/bin/env python3

import io
import struct
import sys

level_rle_offs = 0x14000
level_header_ptr_array_offs = 0x15580
level_header_count = 37


def main() -> None:
    infname, outfname = sys.argv[1:]
    data = bytearray(open(infname, "rb").read())
    level_header_ptrs_direct = [
        struct.unpack("<H", data[level_header_ptr_array_offs + i * 2 :][:2])[0]
        for i in range(level_header_count)
    ]
    level_header_ptrs_ordered = sorted(set(level_header_ptrs_direct))
    level_chunks_direct = [
        struct.unpack("<HH", data[level_header_ptr_array_offs + offs + 15 :][:4])
        for offs in level_header_ptrs_direct
        if offs != 0
    ]
    print(level_chunks_direct)
    level_chunks_ordered = sorted(set(level_chunks_direct))
    level_offs_remap: dict[tuple[int, int], tuple[int, int]] = {}

    packed_accum = b""
    new_output_offs = level_chunks_ordered[0][0] + level_rle_offs
    for rle_subhdr in level_chunks_ordered:
        rle_offs, rle_sz = rle_subhdr
        if rle_sz > 0x2000:
            # There's one junk header here, might actually be marked as 0
            print("junk header skipped")
            continue
        rle_offs += level_rle_offs
        print(f"{rle_offs:05X} = {rle_sz:04X} bytes")

        # Unpack RLE data
        rle_data = data[rle_offs:][:rle_sz]
        assert len(rle_data) == rle_sz
        unpackbuf = bytearray(0x1000)
        unpackidx = 0
        try:
            with io.BytesIO(rle_data) as infp:
                prev_val = 0x100
                while unpackidx < len(unpackbuf):
                    bs = infp.read(1)
                    if bs == b"":
                        print(f"early exit @ {unpackidx:04X}")
                        break
                    val = bs[0]
                    if val != prev_val:
                        unpackbuf[unpackidx] = val
                        unpackidx += 1
                        prev_val = val
                    else:
                        reps = infp.read(1)[0]
                        if reps == 0x00:
                            reps = 0x100
                        for i in range(reps):
                            unpackbuf[unpackidx] = val
                            unpackidx += 1
                        prev_val = 0x100

                assert infp.read(1) == b""
        except Exception as e:
            print(f"out offset: {unpackidx:04X}")
            raise

        # Pack LZ data
        with io.BytesIO() as outfp:
            unpackdata = bytes(unpackbuf)[:unpackidx]
            ri = 0
            accum: bytes = b""
            mask = 0x00
            mask_bitmask = 0x80
            while ri < len(unpackdata):
                # Ensure we can write another bit
                if mask_bitmask == 0:
                    outfp.write(bytes([mask]) + accum)
                    mask = 0x00
                    mask_bitmask = 0x80
                    accum = b""

                # Check if we should do a copy
                best_len = 0
                best_offs = 0
                for cmp_offs in range(ri-1, 0-1, -1):
                    cmp_len = 0
                    for i in range(0xFE+1):
                        if ri+i < len(unpackdata) and unpackdata[cmp_offs+i] == unpackdata[ri+i]:
                            cmp_len += 1
                        else:
                            break
                    if cmp_len > best_len:
                        best_len = cmp_len
                        best_offs = cmp_offs

                do_copy = (best_len >= 3)
                if do_copy:
                    # Write a copy!
                    mask |= mask_bitmask
                    assert (0x00+1) <= best_len <= (0xFE+1)
                    accum += struct.pack("<BH", best_len - 0x01, 0x10000+(best_offs-ri))
                    ri += best_len
                else:
                    # Write a literal!
                    accum += bytes([unpackdata[ri]])
                    ri += 1

                # Advance the mask
                mask_bitmask >>= 1

            # Append a final write
            if mask_bitmask == 0:
                outfp.write(bytes([mask]) + accum)
                mask = 0x00
                mask_bitmask = 0x80
                accum = b""
            mask |= mask_bitmask
            mask_bitmask >>= 1
            accum += b"\xFF" # End of stream

            # Flush what we have
            if mask_bitmask != 0x80:
                outfp.write(bytes([mask]) + accum)

            lzpackdata = outfp.getvalue()
            print(f"recompress {new_output_offs+len(packed_accum):05X}: {len(rle_data):04X} -> {len(lzpackdata):04X}")
            level_offs_remap[rle_subhdr] = (new_output_offs-level_rle_offs+len(packed_accum), len(lzpackdata))
            packed_accum += lzpackdata

            # SANITY CHECK: Can we unpack the data?
            reexpanddata = b""
            with io.BytesIO(lzpackdata) as infp:
                mask = 0x10000
                while True:
                    if mask >= 0x10000:
                        mask = 0x100 | infp.read(1)[0]
                    is_copy = (mask & 0x80) != 0
                    mask <<= 1
                    if is_copy:
                        blk_len = infp.read(1)[0]
                        if blk_len == 0xFF:
                            break
                        blk_len += 1
                        blk_offs, = struct.unpack("<H", infp.read(2))
                        for i in range(blk_len):
                            reexpanddata += bytes([reexpanddata[len(reexpanddata)+blk_offs-0x10000]])
                    else:
                        reexpanddata += bytes([infp.read(1)[0]])

                assert infp.read(1) == b""

            if reexpanddata != unpackdata:
                for i in range(min(len(unpackdata), len(reexpanddata))):
                    if unpackdata[i] != reexpanddata[i]:
                        print(f"mismatch {i:04X}: {unpackdata[i]:02X} became {reexpanddata[i]:02X}")
                        break
                raise Exception(f"repacked data mismatch old={len(unpackdata):04X} new={len(reexpanddata):04X}")

    # Finish the repack
    print(f"output = {new_output_offs:05X}")
    data[new_output_offs:new_output_offs+len(packed_accum)] = packed_accum
    for offs in level_header_ptrs_ordered:
        if offs == 0:
            continue
        o = level_header_ptr_array_offs + offs + 15
        hdr_key = struct.unpack("<HH", data[o:o+4])
        remapped = level_offs_remap[hdr_key]
        print(f"remap {hdr_key[0]:04X} -> {remapped[0]:04X}")
        data[o:o+4] = struct.pack("<HH", remapped[0], remapped[1])

    with open(outfname, "wb") as outfp:
        outfp.write(data)


if __name__ == "__main__":
    main()
