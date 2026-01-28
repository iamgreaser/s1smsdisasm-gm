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
