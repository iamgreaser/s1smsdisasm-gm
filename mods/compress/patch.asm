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

.DEF var_D001 $D001

.DEF var_D200 $D200
.DEF g_last_rle_byte $D201
.DEF g_inputs_player_1 $D203
.DEF g_saved_vdp_reg_00 $D218
.DEF g_saved_vdp_reg_01 $D219
.DEF g_sprite_count $D20A
.DEF g_FF_string_high_byte $D20E

.DEF var_D2B4 $D2B4
.DEF var_D2FC $D2FC

.DEF rompage_1 $FFFE
.DEF rompage_2 $FFFF
.DEF g_committed_rompage_1 $D235
.DEF g_committed_rompage_2 $D236

.DEF g_level $D23E
.DEF g_next_bonus_level $D23F

.DEF g_time_mins $D2CE
.DEF g_time_secs_BCD $D2CF
.DEF g_time_subsecs $D2D0
.DEF var_D23C $D23C
.DEF var_D2BE $D2BE
.DEF draw_sprite_text $35CC

.DEF wait_until_irq_ticked $031C
.DEF signal_load_palettes $0333
.DEF load_art $0405
.DEF load_UNK_00501 $0501
.DEF fill_vram_at_hl_for_bc_bytes_with_a $0595
.DEF print_positioned_FF_string $005AF

.IF 1
   ;; Level timer with subseconds
   .BANK $00 SLOT 0
   .ORGA $2F1F
draw_level_timer:
   ld     hl, var_D2BE                 ; 00:2F1F - 21 BE D2
   push hl
   ;ld     a, (g_time_mins)             ; 00:2F22 - 3A CE D2
   ld de, g_time_mins
   ld a, (de)
   inc de

   ;and    $0F                          ; 00:2F25 - E6 0F
   ; 2-0 = 2 saved
   add    a, a                         ; 00:2F27 - 87
   add    a, $80                       ; 00:2F28 - C6 80
   ld     (hl), a                      ; 00:2F2A - 77
   inc    hl                           ; 00:2F2B - 23

   ;ld     a, (g_time_secs_BCD)         ; 00:2F2F - 3A CF D2
   ld a, (de)
   ; 6-6 = 0 bytes saved (parity!), but we can make a lookup cheaper

   ;ld     c, a                         ; 00:2F32 - 4F
   ;srl    a                            ; 00:2F33 - CB 3F
   ;srl    a                            ; 00:2F35 - CB 3F
   ;srl    a                            ; 00:2F37 - CB 3F
   ;srl    a                            ; 00:2F39 - CB 3F
   ;add    a, a                         ; 00:2F3B - 87
   rrca
   rrca
   rrca
   and $1F
   ; 9-5 = 4 saved
   add    a, $80                       ; 00:2F3C - C6 80
   ld     (hl), a                      ; 00:2F3E - 77
   inc    hl                           ; 00:2F3F - 23
   ;ld     a, c                         ; 00:2F40 - 79
   ld a, (de)
   ; 2-1 = 1 saved
   and    $0F                          ; 00:2F41 - E6 0F
   add    a, a                         ; 00:2F43 - 87
   add    a, $80                       ; 00:2F44 - C6 80
   ld     (hl), a                      ; 00:2F46 - 77
   inc    hl                           ; 00:2F47 - 23
   ;ld     (hl), $B0                    ; 00:2F2C - 36 B0
   ; 2-0 = 2 saved

   ; Savings right now: 2+4+1+2+1+1+1 = 12
   inc de      ; 1
   ld a, (de)  ; 1
   ld b, $3F   ; 2
   -: inc b    ; 1
      sub $06  ; 2
      jr nc, - ; 2
   ld a, b     ; 1
   add a, a    ; 1
   ld (hl), a  ; 1
   ; 12 - parity?

   inc    hl                           ; 00:2F2E - 23
   ld     (hl), $FF                    ; 00:2F48 - 36 FF
   ;ld     c, $18                       ; 00:2F4A - 0E 18
   ;ld     b, $10                       ; 00:2F4C - 06 10
   ld bc, $1018
   ; 3-2 = 1 saved
   ld     a, (g_level)                 ; 00:2F4E - 3A 3E D2
   cp     $1C                          ; 00:2F51 - FE 1C
   jr     c, +                         ; 00:2F53 - 38 04
   ;ld     c, $70                       ; 00:2F55 - 0E 70
   ;ld     b, $38                       ; 00:2F57 - 06 38
   ld bc, $3870
   ; 3-2 = 1 saved
+:
   ld     hl, (var_D23C)               ; 00:2F59 - 2A 3C D2
   pop de
   ;ld     de, var_D2BE                 ; 00:2F5C - 11 BE D2
   ; 3-2 = 1 saved
   call   draw_sprite_text             ; 00:2F5F - CD CC 35
   ld     (var_D23C), hl               ; 00:2F62 - 22 3C D2
   ret                                 ; 00:2F65 - C9
fnend:
   .DEF fnlen fnend-draw_level_timer
   .PRINT "Size:   ", DEC fnlen, "\n"
   .REDEF fnlen fnlen+$2F1F
   .PRINT "Offset: $", HEX fnlen, "\n"
   .ASSERT fnlen <= $2F66
   ;; limit: 2F66

.ELIF 0
   ;; Original level timer.
   .BANK $00 SLOT 0
   .ORGA $2F1F

draw_level_timer:
   ld     hl, var_D2BE                 ; 00:2F1F - 21 BE D2
   ld     a, (g_time_mins)             ; 00:2F22 - 3A CE D2
   and    $0F                          ; 00:2F25 - E6 0F
   add    a, a                         ; 00:2F27 - 87
   add    a, $80                       ; 00:2F28 - C6 80
   ld     (hl), a                      ; 00:2F2A - 77
   inc    hl                           ; 00:2F2B - 23
   ld     (hl), $B0                    ; 00:2F2C - 36 B0
   inc    hl                           ; 00:2F2E - 23
   ld     a, (g_time_secs_BCD)         ; 00:2F2F - 3A CF D2
   ld     c, a                         ; 00:2F32 - 4F
   srl    a                            ; 00:2F33 - CB 3F
   srl    a                            ; 00:2F35 - CB 3F
   srl    a                            ; 00:2F37 - CB 3F
   srl    a                            ; 00:2F39 - CB 3F
   add    a, a                         ; 00:2F3B - 87
   add    a, $80                       ; 00:2F3C - C6 80
   ld     (hl), a                      ; 00:2F3E - 77
   inc    hl                           ; 00:2F3F - 23
   ld     a, c                         ; 00:2F40 - 79
   and    $0F                          ; 00:2F41 - E6 0F
   add    a, a                         ; 00:2F43 - 87
   add    a, $80                       ; 00:2F44 - C6 80
   ld     (hl), a                      ; 00:2F46 - 77
   inc    hl                           ; 00:2F47 - 23
   ld     (hl), $FF                    ; 00:2F48 - 36 FF
   ld     c, $18                       ; 00:2F4A - 0E 18
   ld     b, $10                       ; 00:2F4C - 06 10
   ld     a, (g_level)                 ; 00:2F4E - 3A 3E D2
   cp     $1C                          ; 00:2F51 - FE 1C
   jr     c, addr_02F59                ; 00:2F53 - 38 04
   ld     c, $70                       ; 00:2F55 - 0E 70
   ld     b, $38                       ; 00:2F57 - 06 38

addr_02F59:
   ld     hl, (var_D23C)               ; 00:2F59 - 2A 3C D2
   ld     de, var_D2BE                 ; 00:2F5C - 11 BE D2
   call   draw_sprite_text             ; 00:2F5F - CD CC 35
   ld     (var_D23C), hl               ; 00:2F62 - 22 3C D2
   ret                                 ; 00:2F65 - C9
   ;; limit: 2F66
.ENDIF

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

;; Marble Zone music
.IF 1
.BANK $00 SLOT 0
.ORGA $12D8
   ;ld     a, $0C                       ; 00:12D8 - 3E 06

.BANK $03 SLOT 1
.ORGA $4716+($0C*2)
;.ORGA $4716+($00*2)
   .dw $4D0A
.ENDIF

.IF 1
   ;;
   ;; LEVEL SELECT HACK
   ;;
   .BANK $00 SLOT 0
   .ORGA $1C5E
   ;ld     (g_level), a                 ; 00:1C5E - 32 3E D2
   ; end 1C61
   call level_select_trampoline ; 1C5E 3
   ; end 1C61

   .BANK $00 SLOT 0
   .ORGA $000C
   level_select_trampoline:
      di                             ; 000C 1
      ld a, $07                      ; 000D 2
      ld (rompage_1), a              ; 000F 3
      call level_select_init         ; 0012 3
      xor a                          ; 0015 1
      ret                            ; 0016 1
      ; 0017

   ; limit 0017

   .BANK $07 SLOT 1
   ; 4 KB should be enough! (hopefully)
   ;.ORGA $7000
   .ORGA $7C00  ; Try 1KB? It'll also fit in the vanilla ROM.
   level_select_init:
      ld a, (g_committed_rompage_1)
      push af
      ld a, $07
      ld (g_committed_rompage_1), a
      ei

      ;; Hide the screen
      ld     a, (g_saved_vdp_reg_01)      ; 00:258B - 3A 19 D2
      and    $BF                          ; 00:258E - E6 BF
      ld     (g_saved_vdp_reg_01), a      ; 00:2590 - 32 19 D2
      res    0, (iy+var_D200-IYBASE)      ; 00:2593 - FD CB 00 86
      call   wait_until_irq_ticked        ; 00:2597 - CD 1C 03

      ;; Play the Marble Zone music
      ld a, $0C
      ld (var_D2FC), a                ; 00:2311 - 32 FC D2
      rst $18

      ;; Load some art
      ;; This is for the first level intro.
      ld     hl, $0000                    ; 00:0C89 - 21 00 00
      ld     de, $0000                    ; 00:0C8C - 11 00 00
      ld     a, $0C                       ; 00:0C8F - 3E 0C
      call   load_art                     ; 00:0C91 - CD 05 04

      ;; Fill the screen.
      ld d, $78
      --:
         di
         in a, ($BF)
         ld a, $00
         out ($BF), a
         ld a, d
         out ($BF), a
         ld b, $80
         -:
            ld a, $EB     ;  7
            out ($BE), a  ; 11 -> 18
            nop           ;  4 -> 22
            nop           ;  4 -> 26
            nop           ;  4 -> 30 OK
            ld a, $00     ;  7
            out ($BE), a  ; 11 -> 18
            djnz -        ; 12 -> 30 OK
         ei
         inc d
         ld a, d
         cp $7F
         jr c, --

      ;; Clear sprite data
      di
      in a, ($BF)
      ld a, $00
      out ($BF), a
      ld a, $3F
      out ($BF), a
      ld b, $40
      -:
         ld a, $E0     ;  7
         out ($BE), a  ; 11 -> 18
         djnz -        ; 12 -> 30 OK
      ei

      ;; Add a cursor.
      di
      in a, ($BF)
      ld a, $00
      out ($BF), a
      ld a, $60
      out ($BF), a
      ld bc, $08BE
      ld hl, _lsel_cursor
      -:
         outi          ; 16
         ld a, $FF     ;  7 -> 23
         inc de        ;  6 -> 29 OK waste
         out ($BE), a  ; 11
         inc b         ;  4 -> 15
         inc de        ;  6 -> 21 waste
         ld a, $FF     ;  7 -> 28 OK waste
         out ($BE), a  ; 11
         dec e         ;  4 -> 15 waste
         inc de        ;  6 -> 21 waste
         ld a, $FF     ;  7 -> 28 OK waste
         out ($BE), a  ; 11
         inc de        ;  6 -> 17 waste
         djnz -        ; 12 -> 29 OK
      ld b, $20
      -:
         ld a, $00     ; 7 -> 30 OK
         out ($BE), a  ; 11
         djnz -        ; 12 -> 23
      ei

      ;; Print some text using EBCDIC-Sonic1-A. Or whatever this ad-hoc encoding is called.
      ld a, $00
      ld (g_FF_string_high_byte), a
      ld hl, _lsel_rows
      --:
         push hl
         call print_positioned_FF_string
         pop hl
         ld a, $FF
         -:
            cp (hl)
            inc hl  ; no flags affected
            jr nz, -
         ld a, (hl)
         cp $FF
         jr nz, --

      ;; Load the main title palette (for now)
      ld     hl, $0F0E                    ; 00:0CD4 - 21 0E 0F
      ld     a, $03
      call   signal_load_palettes

      ;; Set first level
      ld a, $00
      ld (g_level), a

      ;; Show the screen
      ld     a, (g_saved_vdp_reg_01)      ; 00:25CC - 3A 19 D2
      or     $40                          ; 00:25CF - F6 40
      ld     (g_saved_vdp_reg_01), a      ; 00:25D1 - 32 19 D2
      res    0, (iy+var_D200-IYBASE)      ; 00:25D4 - FD CB 00 86
      call   wait_until_irq_ticked        ; 00:25D8 - CD 1C 03

      ;; Loop!
      ;; Misuse this now-unused byte as a previous input byte
      -:
         ld a, (iy+g_inputs_player_1-IYBASE)
         ld (iy+g_last_rle_byte-IYBASE), a
         ;; Show a cursor.
         ;; Use 1 sprite.
         ld (iy+g_sprite_count-IYBASE), 0
         ld a, (g_level)
         rlca
         rlca
         rlca
         add a, 2*8-1 ; -1 for Y offset
         ld hl, $D000
         ld (hl), 29*8 ; X coord
         inc hl
         ld (hl), a  ; Y
         inc hl
         ld (hl), $00 ; Graphic
         inc hl
         inc (iy+g_sprite_count-IYBASE)
         set 1, (iy+var_D200-IYBASE)
         res 0, (iy+var_D200-IYBASE)      ; 00:0E8D - FD CB 00 86
         call   wait_until_irq_ticked        ; 00:0E91 - CD 1C 03
         res 0, (iy+var_D200-IYBASE)

         ;; Handle arrows
         ld a, (g_level)
         bit 0, (iy+g_inputs_player_1-IYBASE)
         jr nz, +
         bit 0, (iy+g_last_rle_byte-IYBASE)
         jr z, +
            and a
            jr z, +
            dec a
         +:
         bit 1, (iy+g_inputs_player_1-IYBASE)
         jr nz, +
         bit 1, (iy+g_last_rle_byte-IYBASE)
         jr z, +
            cp a, 6*3-1
            jr nc, +
            inc a
         +:
         ld (g_level), a

         ;; Handle 1/2 button
         bit    5, (iy+g_inputs_player_1-IYBASE)  ; 00:1348 - FD CB 03 6E
         jr     nz, -

      ;; Hide the screen
      ld     a, (g_saved_vdp_reg_01)      ; 00:258B - 3A 19 D2
      and    $BF                          ; 00:258E - E6 BF
      ld     (g_saved_vdp_reg_01), a      ; 00:2590 - 32 19 D2
      res    0, (iy+var_D200-IYBASE)      ; 00:2593 - FD CB 00 86
      call   wait_until_irq_ticked        ; 00:2597 - CD 1C 03

      ;; TODO: Stop the music

      pop af
      di
      ld (g_committed_rompage_1), a
      jp $02E5
      ;ld     a, (g_committed_rompage_1)   ; 00:02E5 - 3A 35 D2
      ;ld     (rompage_1), a               ; 00:02E8 - 32 FE FF
      ;ei                                  ; 00:02EB - FB
      ;ret                                 ; 00:02EC - C9

_lsel_cursor:
   .db %00001100
   .db %00111000
   .db %01100000
   .db %11111111
   .db %01100000
   .db %00111000
   .db %00001100
   .db %00000000

   .db %00000000
   .db %00000000
   .db %00000000
   .db %00000000
   .db %00000000
   .db %00000000
   .db %00000000
   .db %00000000

   ; from the Sonic Retro wiki:
   ; 34 35 36 37 44 45 46 47 40 41 42 43 50 51 52 60 61 62 70 80 81 54 3C 3D 3E 3F EB
   ;  A  B  C  D  E  F  G  H  I  J  K  L  M  N  O  P  Q  R  S  T  U  V  W  X  Y  Z sp
   ; and I've heard that Q is actually also another O... which it seems to be.
   ;
   ; Left column is masked.
_lsel_rows:
   .db 1+6, 0  ; Centre it.
   .db $70, $52, $51, $40, $36, $EB  ; SONIC (sp)
   .db $80, $47, $44, $EB  ; THE (sp)
   .db $47, $44, $37, $46, $44, $47, $52, $46  ; HEDGEHOG
   .db $FF

   ; These titles seem pretty stealable as-is. The first three at least.
   ; The last 3 need conversion.
   .db   3,   2, $46, $62, $44, $44, $51, $EB, $47, $40, $43, $43, $FF
   .db   3,   5, $35, $62, $40, $37, $46, $44, $FF
   .db   3,   8, $41, $81, $51, $46, $43, $44, $FF
   .db   3,  11, $43, $34, $35, $3E, $62, $40, $51, $80, $47, $FF
   .db   3,  14, $70, $36, $62, $34, $60, $EB, $35, $62, $34, $40, $51, $FF
   .db   3,  17, $70, $42, $3E, $EB, $35, $34, $70, $44, $FF

   ; Set up some act names!
   ; Using letters b/c can't be bothered finding numbers right now.
   .REPT 6 INDEX i
   .db  23,   2+i*3, $34, $36, $80, $EB, $34, $FF
   .db  23,   3+i*3, $34, $36, $80, $EB, $35, $FF
   .db  23,   4+i*3, $34, $36, $80, $EB, $36, $FF
   .ENDR

   ;; End of list!
   .db $FF

.ELIF 1
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

      ld hl, $1C00       ; 1C58 3

      ld (g_level), hl   ; 1C5B 3
      xor a              ; 1C5E 1
      nop                ; 1C5F 1
      nop                ; 1C60 1
      ; end 1C61
.ENDIF

