.PHONY: all
all: out/s1.sms

out/s1.sms: src/whole.lnk build/whole.o | out/
	wlalink -r -s -v $< $@

build/whole.o: src/whole.asm | build/
	wla-z80 -v -w -o $@ $<

src/whole.asm: baserom/sonic1.sms annot/sonic1.cfg tools/rom_unpack.py
	python3 ./tools/rom_unpack.py baserom/sonic1.sms annot/sonic1.cfg src/whole.asm

out/ build/:
	install -D -d $@

