from __future__ import annotations

import enum


class AT(enum.Enum):
    DataByte = enum.auto()
    DataWord = enum.auto()
    Op = enum.auto()

    DataByteRelLabel = enum.auto()
    DataWordLabel = enum.auto()


LTYPEMAP = {
    "byte": AT.DataByte,
    "word": AT.DataWord,
    "wptr": AT.DataWordLabel,
    "codewptr": AT.DataWordLabel,
}
LTYPESIZE = {
    AT.DataByte: 1,
    AT.DataWord: 2,
    AT.DataWordLabel: 2,
}
LTYPECMD = {
    AT.DataByte: "db",
    AT.DataWord: "dw",
    AT.DataWordLabel: "dw",
}
