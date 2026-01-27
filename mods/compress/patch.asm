.MEMORYMAP
SLOT 0 START $0000 SIZE $4000
SLOT 1 START $4000 SIZE $4000
SLOT 2 START $8000 SIZE $4000
SLOT 3 START $C000 SIZE $2000
DEFAULTSLOT 2
DEFAULTRAMSECTIONSLOT 3
.ENDME

.ROMBANKMAP
BANKSTOTAL 16
BANKSIZE $4000
BANKS 16
.ENDRO

.BACKGROUND "build/compress/repacked.sms"
;.BACKGROUND "out/s1.sms"
.COMPUTESMSCHECKSUM

.DEF IYBASE $D200

.DEF var_C000 $C000
.DEF g_last_rle_byte $D201

.DEF rompage_1 $FFFE
.DEF rompage_2 $FFFF
.DEF g_committed_rompage_1 $D235
.DEF g_committed_rompage_2 $D236
.DEF g_level $D23E
.DEF g_next_bonus_level $D23F

;;
;; LEVEL SKIP HACK
;;
.BANK $00 SLOT 0
.ORGA $1C58
   ;ld     a, $1C                       ; 00:1C58 - 3E 1C
   ;ld     (g_next_bonus_level), a      ; 00:1C5A - 32 3F D2
   ;xor    a                            ; 00:1C5D - AF
   ;ld     (g_level), a                 ; 00:1C5E - 32 3E D2
   ; end 1C61

   ld hl, $1C0C       ; 1C58 3

   ld (g_level), hl   ; 1C5B 3
   xor a              ; 1C5E 1
   nop                ; 1C5F 1
   nop                ; 1C60 1
   ; end 1C61

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
unpack_level_layout_into_ram:
   ;ld de, var_C000               ; 0A10 3
_lzss_fetch_mask:
   ;; Read mask
   ld a, (hl)                    ; 0A13 1
   scf                           ; 0A14 1
_lzss_inc_hl_read_mask_bit:
   inc hl                        ; 0A15 1 - 16-bit INC/DEC does not affect flags
_lzss_read_mask_bit:
   ;; Process mask bit
   adc a, a                      ; 0A16 1
   jr z, _lzss_fetch_mask        ; 0A17 2
   jr c, _lzss_handle_copy       ; 0A19 2
   ldi                           ; 0A21 2 - does not affect flags, CF still clear
   or a                          ; 0A23 1 - clear CF - TODO remove? --GM
   jr _lzss_read_mask_bit        ; 0A24 2
_lzss_handle_copy:
   ;; Load length
   ld c, (hl)                    ; 0A26 1
   inc c                         ; 0A27 1
   ret z                         ; 0A28 1 - length byte $FF = terminate
   inc hl                        ; 0A29 1
   ;; Load offset
   ld b, (hl)                    ; 0A2A 1
   inc hl                        ; 0A2B 1
   push hl                       ; 0A2C 1
      ld h, (hl)                 ; 0A2D 1
      ld l, b                    ; 0A2E 1
      ;; Clean up length
      ld b, $00                  ; 0A2F 2
      ;; Add offset and do copy
      add hl, de                 ; 0A31 1 - DE negative, HL+DE unsigned overflows - CF set
      ldir                       ; 0A32 2 - does not affect CF
   pop hl                        ; 0A34 1
   or a                          ; 0A35 1 - clear CF
   jr _lzss_inc_hl_read_mask_bit ; 0A36 2
   ; 0A38

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

;; Marble Zone music
.IF 0
.BANK $00 SLOT 0
.ORGA $12D8
   ;ld     a, $0C                       ; 00:12D8 - 3E 06

.BANK $03 SLOT 1
;.ORGA $4716+($0C*2)
.ORGA $4716+($00*2)
   .dw $4D0A
.ENDIF
