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
      ;; 12 cycles per out - need a gap of 16 or better
      -:
         ld a, (hl)   ; 7 -> 19 OK
         out (c), a
         ld d, a      ; 4
         rrc d        ; 8 -> 12
         or d         ; 4 -> 16 OK
         out (c), a
         inc hl       ; 6
         inc de       ; 6 -> 12 waste
         dec de       ; 6 -> 18 OK waste
         out (c), a
         nop          ; 4
         inc de       ; 6 -> 10 waste
         dec de       ; 6 -> 16 OK waste
         out (c), a
         djnz -        ; 12
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
   .db %11111110
   .db %01100000
   .db %00111000
   .db %00001100
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
