.IF 0
   .DEF load_art $0405
.ELIF 1
   ;; Hopefully faster art loading!
   .BANK $00 SLOT 0
   .ORGA $0405

;; A is the bank to load the art from
;; HL is the source data relative to the start of the bank
;; - This CAN point past that bank, actually!
;;   And it'll automatically correct itself so you can load at least 16 KB + 1 byte.
;; DE is the destination in VRAM to write to
load_art:
   ;; The start of this is pretty good so we'll keep it as-is.
   ;; Except some stuff will be made a little shorter.
   ;; Everything else is wasteful enough that I don't have to worry *too* much about fitting it in.
   di                                  ; 00:0405 - F3

   ;; Adjust bank and offset to be relative to the start of the bank
   ld c, a
   ld a, h
   jr +
   -:
      inc c
   +:
      sub $40
      jr nc, -
   add a, $40
   ld h, a
   ;; Write VRAM address
   ld a, e
   out ($BF), a
   ld a, d
   or $40
   out ($BF), a
   ld a, c

   ;;
   ;; vvv This part is as-is EXCEPT rompage writes are swapped around.
   ;; Although it probably doesn't matter as interrupts are disabled anyway.
   ;;

   ;; Make the source address relative to slot 1
   ld     de, $4000                    ; 00:041D - 11 00 40
   add    hl, de                       ; 00:0420 - 19
   ;; Save old slot 1 and 2 bank values
   ld     de, (g_committed_rompage_1)  ; 00:0421 - ED 5B 35 D2
   push   de                           ; 00:0425 - D5
   ;; Load bank address
   ld     (g_committed_rompage_1), a   ; 00:0429 - 32 35 D2
   ld     (rompage_1), a               ; 00:0426 - 32 FE FF
   inc    a                            ; 00:042C - 3C
   ld     (g_committed_rompage_2), a   ; 00:0430 - 32 36 D2
   ld     (rompage_2), a               ; 00:042D - 32 FF FF
   ;; Enable interrupts unless they are to be suppressed
   bit    1, (iy+var_D209-IYBASE)      ; 00:0433 - FD CB 09 4E
   jr     nz, +                        ; 00:0437 - 20 01
      ei                                  ; 00:0439 - FB
   +:

   ;;
   ;; ^^^ End of mostly-as-is part.
   ;;

   ;; And now we get into this mess!
   ;; Track our base register.

   ;; Save base offset
   ld c, l
   ld b, h
   ;; Skip hl header
   inc hl
   inc hl
   ;; Load compressed indices, stash into DE'
   ld e, (hl)
   inc hl
   ld d, (hl)
   inc hl
   ex de, hl
   add hl, bc
   ex de, hl
   push de
      ;; Load uncompressed tile data, stash into HL'
      ld e, (hl)
      inc hl
      ld d, (hl)
      inc hl
      ex de, hl
      add hl, bc
      ld ($D20E), hl
      ex de, hl
      push de
         ;; Load 8x1 4bpp row count
         ld c, (hl)
         inc hl
         ld b, (hl)
         inc hl
         ;; Convert BC into djnz-friendly form
         ;; This frees up the need to proxy through A.
         dec bc
         inc b
         inc c
         ld a, b
         ld b, c
         ld c, a
         ;; Stash HL into DE'
         push hl
            exx
         pop de
      pop hl
   pop bc
   exx

   ;; Load tile data

   ;; Fetch our first byte
   ;; Do our loop!
   ;; HL' AD2  = uncompressed tiles running pointer (base is $D20E)
   ;; DE' BODY = running bitmask pointer
   ;; BC' AD1  = compressed tiles running pointer
   ;; BC  AD3  = rows remaining (converted to DJNZ/DEC C/JR NZ form)
   ;; DE, HL, A are free for use!
   _load_art_mask_fetch:
      exx
         ld a, (de)
         inc de
      exx
      scf
   _load_art_each_row_when_NC:
      ;; RRA does not affect CF, so we need RR A!
      ;; Hayashi-san, where was your crystal ball???
      ;; I could have saved 4 cycles by shifting left with ADC A, A if only you'd used it!!!
      rr a
      jr z, _load_art_mask_fetch
      jr nc, ++
         ex af, af'
         ;; bit == 1: Copy previous
         ;; Load raw offset
         exx
            ld a, (bc)
            inc bc
         exx
         ld h, $00
         cp $F0
         jr c, +
            sub $F0
            ld h, a
            exx
               ld a, (bc)
               inc bc
            exx
         +:
         ld l, a
         ;; Calculate actual address
         add hl, hl
         add hl, hl
         ld de, ($D20E)
         add hl, de
         ;; Load it!
         call _load_art_subfunc_upload_row
   _load_art_reloop:
      ex af, af'
      or a  ; clears CF
      ;; Loop!
      djnz _load_art_each_row_when_NC    ; does not affect CF (or any flags for that matter)
      dec c                              ; does not affect CF
      jp nz, _load_art_each_row_when_NC
      ;; Then we return to the epilogue.
      jr _load_art_epilogue
   ++:
      ;; bit == 0: Write literal
      ex af, af'
      exx
         call _load_art_subfunc_upload_row
         inc hl ; shifted out because we don't need to INC HL in the other case
      exx
      jp _load_art_reloop
   _load_art_epilogue:
;; Epilogue
   ;; Disable interrupts unless they are to be suppressed
   bit    1, (iy+var_D209-IYBASE)      ; 00:04E3 - FD CB 09 4E
   jr     nz, +                        ; 00:04E7 - 20 01
      di                                  ; 00:04E9 - F3
   +:
   ;; Restore old slot 1 and 2 bank values
   pop    de                           ; 00:04EA - D1
   ld     (g_committed_rompage_1), de  ; 00:04EB - ED 53 35 D2
   ld     (rompage_1), de              ; 00:04EF - ED 53 FE FF
   ;; Enable interrupts anyway
   ei                                  ; 00:04F3 - FB
   ;; Clear the interrupt suppression flag
   res    1, (iy+var_D209-IYBASE)      ; 00:04F4 - FD CB 09 8E
   ret                                 ; 00:04F8 - C9

_load_art_subfunc_upload_row:
   ld     a, (hl)                      ; 00:04C7 - 7E
   out    ($BE), a                     ; 00:04C8 - D3 BE
   inc    hl                           ; 00:04CA - 23
   nop                                 ; 00:04CB - 00
   nop                                 ; 00:04CC - 00
   ld     a, (hl)                      ; 00:04CD - 7E
   out    ($BE), a                     ; 00:04CE - D3 BE
   inc    hl                           ; 00:04D0 - 23
   nop                                 ; 00:04D1 - 00
   nop                                 ; 00:04D2 - 00
   ld     a, (hl)                      ; 00:04D3 - 7E
   out    ($BE), a                     ; 00:04D4 - D3 BE
   inc    hl                           ; 00:04D6 - 23
   nop                                 ; 00:04D7 - 00
   nop                                 ; 00:04D8 - 00
   ld     a, (hl)                      ; 00:04D9 - 7E
   out    ($BE), a                     ; 00:04DA - D3 BE
   ;inc    hl                           ; 00:04DC - 23
   ret

.ELIF 1
   ;; Original load_art implementation.
   .BANK $00 SLOT 0
   .ORGA $0405
;; A is the bank to load the art from
;; HL is the source data relative to the start of the bank
;; - This CAN point past that bank, actually!
;;   And it'll automatically correct itself so you can load at least 16 KB + 1 byte.
;; DE is the destination in VRAM to write to
load_art:
   di                                  ; 00:0405 - F3

   ;; Adjust bank and offset to be relative to the start of the bank
   -:
      push   af                           ; 00:0406 - F5
         ld     a, h                         ; 00:0407 - 7C
         cp     $40                          ; 00:0408 - FE 40
         jr     c, +                         ; 00:040A - 38 08
         sub    $40                          ; 00:040C - D6 40
         ld     h, a                         ; 00:040E - 67
      pop    af                           ; 00:040F - F1
      inc    a                            ; 00:0410 - 3C
      jp     -                            ; 00:0411 - C3 06 04
   +:

      ;; Write VRAM address
      ld     a, e                         ; 00:0414 - 7B
      out    ($BF), a                     ; 00:0415 - D3 BF
      ld     a, d                         ; 00:0417 - 7A
      or     $40                          ; 00:0418 - F6 40
      out    ($BF), a                     ; 00:041A - D3 BF
   pop    af                           ; 00:041C - F1

   ;; Make the source address relative to slot 1
   ld     de, $4000                    ; 00:041D - 11 00 40
   add    hl, de                       ; 00:0420 - 19
   ;; Save old slot 1 and 2 bank values
   ld     de, (g_committed_rompage_1)  ; 00:0421 - ED 5B 35 D2
   push   de                           ; 00:0425 - D5
   ;; Load bank address
   ld     (rompage_1), a               ; 00:0426 - 32 FE FF
   ld     (g_committed_rompage_1), a   ; 00:0429 - 32 35 D2
   inc    a                            ; 00:042C - 3C
   ld     (rompage_2), a               ; 00:042D - 32 FF FF
   ld     (g_committed_rompage_2), a   ; 00:0430 - 32 36 D2
   ;; Enable interrupts unless they are to be suppressed
   bit    1, (iy+var_D209-IYBASE)      ; 00:0433 - FD CB 09 4E
   jr     nz, +                        ; 00:0437 - 20 01
      ei                                  ; 00:0439 - FB
   +:

   ;; Stash base source address
   ld     (var_D212), hl               ; 00:043A - 22 12 D2
   ;; Skip "HY" magic bytes
   inc    hl                           ; 00:043D - 23
   inc    hl                           ; 00:043E - 23
   ;; Load and push AD1
   ld     e, (hl)                      ; 00:043F - 5E
   inc    hl                           ; 00:0440 - 23
   ld     d, (hl)                      ; 00:0441 - 56
   inc    hl                           ; 00:0442 - 23
   push   de                           ; 00:0443 - D5
      ;; Load and push AD2
      ld     e, (hl)                      ; 00:0444 - 5E
      inc    hl                           ; 00:0445 - 23
      ld     d, (hl)                      ; 00:0446 - 56
      push   de                           ; 00:0447 - D5
         inc    hl                           ; 00:0448 - 23
         ;; Load AD3
         ld     c, (hl)                      ; 00:0449 - 4E
         inc    hl                           ; 00:044A - 23
         ld     b, (hl)                      ; 00:044B - 46
         inc    hl                           ; 00:044C - 23
         ;; Stash AD3
         ;; BC = AD3
         ld     (var_D210), bc               ; 00:044D - ED 43 10 D2
         ;; Stash our post-header input address, which we will call BODY
         ;; HL = BODY
         ld     (var_D214), hl               ; 00:0451 - 22 14 D2

         ;; ENTER SHADOW REGISTERS (BC', DE', HL')
         exx                                 ; 00:0454 - D9

         ;; Load base source address into BC' and DE'
         ld     bc, (var_D212)               ; 00:0455 - ED 4B 12 D2
         ld     e, c                         ; 00:0459 - 59
         ld     d, b                         ; 00:045A - 50
      ;; Pop AD2
      pop    hl                           ; 00:045B - E1
      ;; Make AD2 absolute and save
      add    hl, bc                       ; 00:045C - 09
      ld     ($D20E), hl  ; 00:045D - 22 0E D2
      ;; Set BC' = AD2
      ld     c, l                         ; 00:0460 - 4D
      ld     b, h                         ; 00:0461 - 44
   ;; Pop AD1
   pop    hl                           ; 00:0462 - E1
   ;; Make AD1 absolute
   add    hl, de                       ; 00:0463 - 19
   ex     de, hl                       ; 00:0464 - EB
   ;; BC' = AD2
   ;; DE' = AD1
   ;; HL' = base address

   ;; ENTER MAIN REGISTERS (BC, DE, HL)
   exx                                 ; 00:0465 - D9

--:
   ;; Not going to spell this out step by step below.
   ;; This code is just... horribly slow. Please, never do this on a Z80.
   ;; 1. Get the bit index by computing AD3 minus bytes_left (BC).
   ;; 2. Use the low 3 bits to index a LUT of `(1<<x)` values, store that in A.
   ;; 3. Compute BODY+(index>>3), store that in HL.
   ;; 4. AND (HL).b into A and branch based on that.
   ld     hl, (var_D210)               ; 00:0466 - 2A 10 D2
   xor    a                            ; 00:0469 - AF
   sbc    hl, bc                       ; 00:046A - ED 42
   ;; Use HL as an offset to a bit in BODY.
   ;; Compute
   push   hl                           ; 00:046C - E5
      ld     d, a                         ; 00:046D - 57
      ld     a, l                         ; 00:046E - 7D
      and    $07                          ; 00:046F - E6 07
      ld     e, a                         ; 00:0471 - 5F
      ld     hl, LUT_004F9_left_shift_bitmask  ; 00:0472 - 21 F9 04
      add    hl, de                       ; 00:0475 - 19
      ld     a, (hl)                      ; 00:0476 - 7E
   pop    de                           ; 00:0477 - D1
   srl    d                            ; 00:0478 - CB 3A
   rr     e                            ; 00:047A - CB 1B
   srl    d                            ; 00:047C - CB 3A
   rr     e                            ; 00:047E - CB 1B
   srl    d                            ; 00:0480 - CB 3A
   rr     e                            ; 00:0482 - CB 1B
   ld     hl, (var_D214)               ; 00:0484 - 2A 14 D2
   add    hl, de                       ; 00:0487 - 19
   ld     e, a                         ; 00:0488 - 5F
   ld     a, (hl)                      ; 00:0489 - 7E
   and    e                            ; 00:048A - A3
   jr     nz, +                        ; 00:048B - 20 21
   ;; Bit == 0 case.
   ;; ENTER SHADOW REGISTERS (BC', DE', HL')
   exx                                 ; 00:048D - D9
      ;; Copy 4 bytes from BC' (AD2) to VRAM
      ;; 11+6+4+4+7 = 32 cycles per write in the fastest case.
      ld     a, (bc)                      ; 00:048E - 0A
      out    ($BE), a                     ; 00:048F - D3 BE
      inc    bc                           ; 00:0491 - 03
      nop                                 ; 00:0492 - 00
      nop                                 ; 00:0493 - 00
      ld     a, (bc)                      ; 00:0494 - 0A
      out    ($BE), a                     ; 00:0495 - D3 BE
      inc    bc                           ; 00:0497 - 03
      nop                                 ; 00:0498 - 00
      nop                                 ; 00:0499 - 00
      ld     a, (bc)                      ; 00:049A - 0A
      out    ($BE), a                     ; 00:049B - D3 BE
      inc    bc                           ; 00:049D - 03
      nop                                 ; 00:049E - 00
      nop                                 ; 00:049F - 00
      ld     a, (bc)                      ; 00:04A0 - 0A
      out    ($BE), a                     ; 00:04A1 - D3 BE
      inc    bc                           ; 00:04A3 - 03
   ;; ENTER MAIN REGISTERS (BC, DE, HL)
   exx                                 ; 00:04A4 - D9
   ;; Decrement AD3 counter and advance.
   dec    bc                           ; 00:04A5 - 0B
   ld     a, b                         ; 00:04A6 - 78
   or     c                            ; 00:04A7 - B1
   jp     nz, --                       ; 00:04A8 - C2 66 04
   ;; Jump to the epilogue and clean up
   jp     ++                           ; 00:04AB - C3 E3 04

+:
   ;; Bit == 1 case.
   ;; ENTER SHADOW REGISTERS (BC', DE', HL')
   exx                                 ; 00:04AE - D9
   ;; DE' is AD1, fetch a byte from there.
   ld     a, (de)                      ; 00:04AF - 1A
   inc    de                           ; 00:04B0 - 13
   ;; ENTER MAIN REGISTERS (BC, DE, HL)
   exx                                 ; 00:04B1 - D9
   ;; Compute offset into AD2_base
   ;; There are two forms of this:
   ;; - Fx yy: Offset is $Fxyy.
   ;; - xx:    Offset is $xx ($xx <= $EF).
   ld     h, $00                       ; 00:04B2 - 26 00
   cp     $F0                          ; 00:04B4 - FE F0
   jr     c, +                         ; 00:04B6 - 38 07
   sub    $F0                          ; 00:04B8 - D6 F0
   ld     h, a                         ; 00:04BA - 67
   ;; ENTER SHADOW REGISTERS (BC', DE', HL')
   exx                                 ; 00:04BB - D9
   ;; DE' is AD1, fetch another byte from there.
   ld     a, (de)                      ; 00:04BC - 1A
   inc    de                           ; 00:04BD - 13
   ;; ENTER MAIN REGISTERS (BC, DE, HL)
   exx                                 ; 00:04BE - D9

+:
   ld     l, a                         ; 00:04BF - 6F
   ;; Shift HL left by 2 (multiply by 4)
   add    hl, hl                       ; 00:04C0 - 29
   add    hl, hl                       ; 00:04C1 - 29
   ;; Apply AD2_base offset
   ld     de, ($D20E)  ; 00:04C2 - ED 5B 0E D2
   add    hl, de                       ; 00:04C6 - 19
   ;; Copy 4 bytes from HL to VRAM
   ld     a, (hl)                      ; 00:04C7 - 7E
   out    ($BE), a                     ; 00:04C8 - D3 BE
   inc    hl                           ; 00:04CA - 23
   nop                                 ; 00:04CB - 00
   nop                                 ; 00:04CC - 00
   ld     a, (hl)                      ; 00:04CD - 7E
   out    ($BE), a                     ; 00:04CE - D3 BE
   inc    hl                           ; 00:04D0 - 23
   nop                                 ; 00:04D1 - 00
   nop                                 ; 00:04D2 - 00
   ld     a, (hl)                      ; 00:04D3 - 7E
   out    ($BE), a                     ; 00:04D4 - D3 BE
   inc    hl                           ; 00:04D6 - 23
   nop                                 ; 00:04D7 - 00
   nop                                 ; 00:04D8 - 00
   ld     a, (hl)                      ; 00:04D9 - 7E
   out    ($BE), a                     ; 00:04DA - D3 BE
   inc    hl                           ; 00:04DC - 23
   ;; Decrement AD3 counter and advance.
   dec    bc                           ; 00:04DD - 0B
   ld     a, b                         ; 00:04DE - 78
   or     c                            ; 00:04DF - B1
   jp     nz, --                       ; 00:04E0 - C2 66 04

;; Epilogue
++:
   ;; Disable interrupts unless they are to be suppressed
   bit    1, (iy+var_D209-IYBASE)      ; 00:04E3 - FD CB 09 4E
   jr     nz, +                        ; 00:04E7 - 20 01
      di                                  ; 00:04E9 - F3
   +:
   ;; Restore old slot 1 and 2 bank values
   pop    de                           ; 00:04EA - D1
   ld     (g_committed_rompage_1), de  ; 00:04EB - ED 53 35 D2
   ld     (rompage_1), de              ; 00:04EF - ED 53 FE FF
   ;; Enable interrupts anyway
   ei                                  ; 00:04F3 - FB
   ;; Clear the interrupt suppression flag
   res    1, (iy+var_D209-IYBASE)      ; 00:04F4 - FD CB 09 8E
   ret                                 ; 00:04F8 - C9

LUT_004F9_left_shift_bitmask:
.db $01, $02, $04, $08, $10, $20, $40, $80                                          ; 00:04F9
.ENDIF
