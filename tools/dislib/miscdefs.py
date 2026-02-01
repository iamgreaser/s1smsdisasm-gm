from __future__ import annotations

import enum

from typing import (
    NewType,
)

VirtAddress = NewType("VirtAddress", tuple[int, int])
PhysAddress = NewType("PhysAddress", int)


class AT(enum.Enum):
    DataByte = enum.auto()
    DataWord = enum.auto()
    Op = enum.auto()

    DataByteLabelLo = enum.auto()
    DataByteLabelHi = enum.auto()
    DataByteRelLabel = enum.auto()
    DataWordLabel = enum.auto()

    File = enum.auto()


LTYPEMAP = {
    "byte": AT.DataByte,
    "word": AT.DataWord,
    "wptr": AT.DataWordLabel,
    "codewptr": AT.DataWordLabel,
}
LTYPESIZE = {
    AT.DataByte: 1,
    AT.DataByteLabelLo: 1,
    AT.DataByteLabelHi: 1,
    AT.DataWord: 2,
    AT.DataWordLabel: 2,
}
LTYPECMD = {
    AT.DataByte: "db",
    AT.DataByteLabelLo: "db",
    AT.DataByteLabelHi: "db",
    AT.DataWord: "dw",
    AT.DataWordLabel: "dw",
}
