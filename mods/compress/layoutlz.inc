;;
;; Making room for level decompressor - part 1
;;
.IF 1
.BANK $00 SLOT 0
.ORGA $2212
   derp_beg:
   di
   ld a, d
   res 7, d
   set 6, d  ; further along expects $4000-relative addresses
   and $C0
   rlca
   rlca
   add a, $05
   ld l, a
   inc a
   ld h, a
   ;; RACE CONDITION: Always write your intentions before writing the actual paging registers!
   ;; Otherwise an interrupt at the perfect place will break it.
   ;; And then you'll end up with the8bitbeast's 2019 Any% TAS: https://tasvideos.org/3904M
   ;; And no this isn't the place the TAS misuses.
   ld (g_committed_rompage_1), hl
   ld (rompage_1), hl
   ex de, hl
   ei
   ld de, var_C000
   call unpack_level_layout_into_ram
   derp_end:
   .DEF derp derp_end-derp_beg
   .PRINT "Size (w/o jump): ", DEC derp, "\n"
   .REDEF derp derp+$2212+3
   .PRINT "Offset (w/ jump): $", HEX derp, "\n"
   jp $2246
.ENDIF

;;
;; The original block of code for the level decompressor
;;
.BANK $00 SLOT 0
.ORGA $0A10
.IF 1
   ;; LZSS
   ; We omit pre-setting de to $C000 for two reasons:
   ; 1. It saves 3 bytes, which we could do with.
   ;    (Apparently not needed, I accidentally counted hex like it was decimal and was pessimistic by 6 bytes!)
   ; 2. It means we can reuse this for other buffers in RAM.
unpack_level_layout_into_ram:
_lzss_fetch_mask:
   ;; Read mask
   ld a, (hl)                    ; 0A10 1
   scf                           ; 0A11 1
_lzss_inc_hl_read_mask_bit:
   inc hl                        ; 0A12 1 - 16-bit INC/DEC does not affect flags
_lzss_read_mask_bit:
   ;; Process mask bit
   adc a, a                      ; 0A13 1
   jr z, _lzss_fetch_mask        ; 0A14 2
   jr c, _lzss_handle_copy       ; 0A16 2
   ldi                           ; 0A18 2 - does not affect flags, CF still clear
   jr _lzss_read_mask_bit        ; 0A1A 2
_lzss_handle_copy:
   ;; Load length
   ld c, (hl)                    ; 0A1C 1
   inc c                         ; 0A1D 1
   ret z                         ; 0A1E 1 - length byte $FF = terminate
   inc hl                        ; 0A1F 1
   ;; Load offset
   ld b, (hl)                    ; 0A20 1
   bit 7, b                      ; 0A21 2
   jr z, +                       ; 0A23 2
      ;; msbit = 1: short version, low byte
      dec hl                     ; 0A25 1
      ld b, $FF                  ; 0A26 2
      ;; otherwise msbit = 0: long version, high byte needing fixup
   +:
   inc hl                        ; 0A28 1
   push hl                       ; 0A29 1
      ld l, (hl)                 ; 0A2A 1
      ld h, b                    ; 0A2B 1
      set 7, h                   ; 0A2C 2 - setting this is mandatory for the long offset version
      ;; Clean up length
      ld b, $00                  ; 0A2E 2
      ;; Add offset and do copy
      add hl, de                 ; 0A30 1 - DE negative, HL+DE unsigned overflows - CF set
      ldir                       ; 0A31 2 - does not affect CF
   pop hl                        ; 0A32 1
   or a                          ; 0A33 1 - clear CF
   jr _lzss_inc_hl_read_mask_bit ; 0A34 2
   ; 0A36

   ;; LIMIT: Stay below 0A40.

.ELIF 0
   ;; RLE, size-optimised
unpack_level_layout_into_ram:
   ld     de, var_C000                 ; 00:0A10 - 11 00 C0

addr_00A13:
   ld c, (hl) ; 0A13 1
   dec c      ; 0A14 1
   ; old 0A18 new 0A15 save 3

addr_00A18:
   ld     a, (hl)                      ; 00:0A18 - 7E
   cp c ; 0A19 1
   ; old 0A1C new A1A save 2
   jr     z, addr_00A2B                ; 00:0A1C - 28 0D
   ld     (de), a                      ; 00:0A1E - 12
   ld c, a ; 0A1F 1
   ; old 0A22 new 0A20 save 2
   inc    hl                           ; 00:0A22 - 23
   inc    de                           ; 00:0A23 - 13
   bit 4, d         ; 0A24 2
   jr z, addr_00A18 ; 0A26 2
   ; old 0A2A new 0A28 save 2

   ret                                 ; 00:0A2A - C9

addr_00A2B:
   bit 4, d  ; 0A2B 2
   ret nz    ; 0A2D 1
   ; old 0A2F new 0A2E save 2

   ld     a, (hl)                      ; 00:0A2F - 7E
   inc    hl                           ; 00:0A30 - 23
   ; old 0A32 new 0A31 save 1 (deleted 1 op)
   ld     b, (hl)                      ; 00:0A32 - 46

addr_00A33:
   ld     (de), a                      ; 00:0A33 - 12
   inc    de                           ; 00:0A34 - 13
   djnz   addr_00A33                   ; 00:0A35 - 10 FC
   ; old 0A38 new 0A37 save 1 (deleted 1 op)
   inc    hl                           ; 00:0A38 - 23
   bit 4, d         ; 0A39 2
   jr z, addr_00A13 ; 0A3B 2
   ; old 0A3F new 0A3D save 2
   ret                                 ; 00:0A3F - C9
   ;; Total savings: 15 bytes (old 0A40 new 0A31)

.ELIF 0
   ;; RLE, original code
unpack_level_layout_into_ram:
   ld     de, var_C000                 ; 00:0A10 - 11 00 C0

addr_00A13:
   ld     a, (hl)                      ; 00:0A13 - 7E
   cpl                                 ; 00:0A14 - 2F
   ld     (iy+g_last_rle_byte-IYBASE), a      ; 00:0A15 - FD 77 01

addr_00A18:
   ld     a, (hl)                      ; 00:0A18 - 7E
   cp     (iy+g_last_rle_byte-IYBASE)         ; 00:0A19 - FD BE 01
   jr     z, addr_00A2B                ; 00:0A1C - 28 0D
   ld     (de), a                      ; 00:0A1E - 12
   ld     (iy+g_last_rle_byte-IYBASE), a      ; 00:0A1F - FD 77 01
   inc    hl                           ; 00:0A22 - 23
   inc    de                           ; 00:0A23 - 13
   dec    bc                           ; 00:0A24 - 0B
   ld     a, b                         ; 00:0A25 - 78
   or     c                            ; 00:0A26 - B1
   jp     nz, addr_00A18               ; 00:0A27 - C2 18 0A
   ret                                 ; 00:0A2A - C9

addr_00A2B:
   dec    bc                           ; 00:0A2B - 0B
   ld     a, b                         ; 00:0A2C - 78
   or     c                            ; 00:0A2D - B1
   ret    z                            ; 00:0A2E - C8
   ld     a, (hl)                      ; 00:0A2F - 7E
   inc    hl                           ; 00:0A30 - 23
   push   bc                           ; 00:0A31 - C5
   ld     b, (hl)                      ; 00:0A32 - 46

addr_00A33:
   ld     (de), a                      ; 00:0A33 - 12
   inc    de                           ; 00:0A34 - 13
   djnz   addr_00A33                   ; 00:0A35 - 10 FC
   pop    bc                           ; 00:0A37 - C1
   inc    hl                           ; 00:0A38 - 23
   dec    bc                           ; 00:0A39 - 0B
   ld     a, b                         ; 00:0A3A - 78
   or     c                            ; 00:0A3B - B1
   jp     nz, addr_00A13               ; 00:0A3C - C2 13 0A
   ret                                 ; 00:0A3F - C9
;; Ends just before 0A40
.ENDIF
