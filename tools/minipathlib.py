from __future__ import annotations

import os.path

from typing import (
    IO,
)


class Path:
    def __init__(self, fname: str) -> None:
        self._fname = fname
        self.stem, self.suffix = os.path.splitext(self._fname)

    def open(self, mode: str) -> IO[bytes]:
        assert "b" in mode
        return open(self._fname, mode)
