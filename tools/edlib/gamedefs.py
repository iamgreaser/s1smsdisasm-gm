#!/usr/bin/python3

from __future__ import annotations

import enum

from typing import (
    Sequence,
)


class OT(enum.Enum):
    player_sonic = 0x00
    monitor_rings = 0x01
    monitor_speed_shoes = 0x02
    monitor_life = 0x03
    monitor_shield = 0x04
    monitor_invincibility = 0x05

    chaos_emerald = 0x06
    signpost = 0x07
    badnik_crabmeat = 0x08

    badnik_buzz_bomber = 0x0E
    platform_horizontal = 0x0F

    zaps_player_to_the_right = (
        0x4B  # Not sure how this one works exactly, but it's used in GHZ2.
    )

    flower_raiser = 0x50  # Not sure how this one works exactly, but it's used in GHZ.
    monitor_checkpoint = 0x51
    monitor_continue = 0x52


# ((dx, dy), tile[anim_idx][dy][dx])
obj_sprite_maps: dict[
    int, tuple[tuple[int, int], Sequence[Sequence[Sequence[int]]]]
] = {
    OT.player_sonic.value: (
        (0, -15),
        [
            [[0xB4, 0xB6, 0xB8], [0xBA, 0xBC, 0xBE]],
        ],
    ),
    # MONITOR IMAGE: 05:5180.
    OT.monitor_rings.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5200.
    OT.monitor_speed_shoes.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5280.
    OT.monitor_life.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5300.
    OT.monitor_shield.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5380.
    OT.monitor_invincibility.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5400.
    OT.chaos_emerald.value: (
        (0, 1),
        [
            # Placeholder saying "06" for now.
            [[0x80, 0x8C]],
            # What is actually used.
            [[0x5C, 0x5E]],
        ],
    ),
    OT.signpost.value: (
        (0, 1),
        [
            [[0x4E, 0x50, 0x52, 0x54], [0x6E, 0x70, 0x72, 0x74], [0xFE, 0x42, 0x44]],
        ],
    ),
    # TODO: Transcribe these signpost art things --GM
    # $08, $0A, $0C, $0E, $FF, $FF, $28, $2A, $2C, $2E, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $FE, $12, $14, $FF, $FF, $FF, $FE, $32, $34, $FF, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $16, $18, $1A, $1C, $FF, $FF, $36, $38, $3A, $3C, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $56, $58, $5A, $5C, $FF, $FF, $76, $78, $7A, $7C, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $00, $02, $04, $06, $FF, $FF, $20, $22, $24, $26, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $4E, $4A, $4C, $54, $FF, $FF, $6E, $6A, $6C, $74, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    # $4E, $46, $48, $54, $FF, $FF, $6E, $66, $68, $74, $FF, $FF, $FE, $42, $44, $FF, $FF, $FF
    OT.badnik_crabmeat.value: (
        (4, -14),
        [
            [[0x00, 0x02, 0x04], [0x20, 0x22, 0x24]],
            [[0x00, 0x02, 0x44], [0x46, 0x22, 0x4A]],
            [[0x40, 0x02, 0x44], [0x26, 0x22, 0x2A]],
            [[0x40, 0x02, 0x04], [0x46, 0x22, 0x4A]],
        ],
    ),
    OT.badnik_buzz_bomber.value: (
        (0, 1),
        [
            [[0xFE, 0x0A], [0x0C, 0x0E, 0x10], []],
            [[0xFE], [0x0C, 0x0E, 0x2C], []],
            [[0xFE, 0x0A], [0x12, 0x14, 0x16], [0x32, 0x34]],
            [[0xFE], [0x12, 0x14, 0x16], [0x32, 0x34]],
            [[0xFE, 0x0A], [0x12, 0x14, 0x16], [0x30, 0x34]],
            [[0xFE], [0x12, 0x14, 0x16], [0x30, 0x34]],
        ],
    ),
    OT.platform_horizontal.value: (
        (0, 1),
        [
            # These seem to be based on the tile flags index.
            # GHZ
            [[0xFE], [0x18, 0x1A, 0x18, 0x1A], []],
            # BRI
            [[0xFE], [0x6C, 0x6E, 0x6C, 0x6E], []],
            # Everything else
            [[0xFE], [0x6C, 0x6E, 0x6E, 0x48], []],
        ],
    ),
    # MONITOR IMAGE: 05:5480.
    OT.monitor_checkpoint.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
    # MONITOR IMAGE: 05:5500.
    OT.monitor_continue.value: (
        (4, -7),
        [
            [[0x54, 0x56, 0x58], [0xAA, 0xAC, 0xAE]],
        ],
    ),
}
