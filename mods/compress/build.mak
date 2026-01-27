BUILD_ALL_TARGETS::=$(BUILD_ALL_TARGETS) out/compress/s1compr.sms
out/compress/s1compr.sms: mods/compress/patch.lnk build/compress/patch.o | out/compress/
	wlalink -r -s $< $@

build/compress/repacked.sms: out/s1.sms mods/compress/repacker.py | build/compress/
	mypy --strict mods/compress/repacker.py
	python3 mods/compress/repacker.py $< $@

# WLA-DX has some non-silenceable spam to filter out, hence the weird grep.
#| (grep -v '^MEM_INSERT:\|^   \^ .*:.*: Writing' || true)
build/compress/patch.o: mods/compress/patch.asm build/compress/repacked.sms | build/compress/
	wla-z80 -w -o $@ $< 2>&1

out/compress/ build/compress/:
	install -D -d $@

