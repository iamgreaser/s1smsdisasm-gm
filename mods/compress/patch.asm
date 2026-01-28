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
.DEF var_D209 $D209
.DEF g_sprite_count $D20A
.DEF g_FF_string_high_byte $D20E
.DEF var_D20E $D20E
.DEF var_D210 $D210
.DEF var_D212 $D212
.DEF var_D214 $D214

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
.DEF load_UNK_00501 $0501
.DEF fill_vram_at_hl_for_bc_bytes_with_a $0595
.DEF print_positioned_FF_string $005AF


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

;; Decompressors
.include "mods/compress/layoutlz.inc"
.include "mods/compress/tileslz.inc"

;; Misc hacks
.include "mods/compress/lselect.inc"
.include "mods/compress/lvltimer.inc"
