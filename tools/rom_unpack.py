#!/usr/bin/env python3
from __future__ import annotations

import sys
import zlib

from dislib.rom import Rom


def main() -> None:
    rom_fname, annot_fname, whole_fname = sys.argv[1:]

    rom_data = open(rom_fname, "rb").read()
    assert len(rom_data) == Rom.bank_count * Rom.bank_size
    assert (zlib.crc32(rom_data) & 0xFFFFFFFF) == Rom.rom_crc
    rom = Rom(data=rom_data)
    rom.load_annotations(file_name=annot_fname)
    rom.run_tracer()
    rom.save(file_name=whole_fname)


if __name__ == "__main__":
    main()
