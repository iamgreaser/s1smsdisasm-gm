Disassembly of Sonic The Hedgehog for the Sega Master System
2026, GreaseMonkey
Work in progress.

You will need the following to build this (versions can be earlier or later but no guarantees):

- WLA-DX 10.7a
- Python 3.14 (at the bare minimum 3.6)
- GNU Make (if it needs fixing for BSD Make let me know)

You will also need the following unless you really hate it and want to comment it out of your Makefile, but if you're working on this code then you will definitely need to use these:

- mypy (type checker for Python, either check your package manager or get it via pip - you may need to create a venv for this)

These tools are also used, but not needed for building things:

- Black (autoformatter for Python, get it via your package manager or pip)

You will need your own correct ROM of Sonic The Hedgehog for the Sega Master System - NOT one of the two (!) Game Gear versions.

Copy this rom with the filename "baserom/sonic1.sms" relative to this readme file - you may need to create the baserom/ directory yourself:

   baserom/sonic1.sms
   Size: 262,144 bytes (256 KB)
   CRC-32: b519e833
   MD5: dc13a61eafe75c13c15b5ece419ac57b
   SHA-1: 6b9677e4a9abb37765d6db4658f4324251807e07
   SHA-256: 6ad738965ece231427ee046b9905cfee470d5c01220afdd934da4673e4a2458b

Then run:

   make

------------------------------

EXTRA STUFF:

mods/compress/:
   A patch mod which compresses a bunch of the data harder. Also adds a level select screen.

src/diet.asm:
   A source mod which frees up a bunch of space, optimises the code (mostly for size, sometimes for speed), and fixes some of the bugs.

tools/asset_walk.py:
   A Tk GUI program to show the locations of the assets in an UNMODIFIED (!) Sonic 1 SMS ROM.
   NOTE: This is currently out of date, I do need to get more info into it.

tools/level_viewer.py:
   A Tk GUI program to show a level. Feed it a bunch of appropriately-suffixed assets and it'll load them up.

   Currently quite crude, and missing a lot of object definitions. But it does render things quite nicely at the moment as long as you aren't expecting functioning water in Labyrinth.

   Try something like this:

      python3 tools/level_viewer.py src/data/lv_ghz{_2{.objects,*.layout*},{.pal3,.pal1c,.art{0000,2000},.tile{flags,map,specials}}} src/data/common_level_art.art3000 src/data/sonic_06_r.sonicuncart src/data/ringart_00.ringart

