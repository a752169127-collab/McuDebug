from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from core.datatype import get_type_info


@dataclass(frozen=True)
class WatchVariableSpec:
    row_id: int
    name: str
    address: int
    type_name: str
    enabled: bool = True

    @property
    def size(self) -> int:
        return get_type_info(self.type_name).size


@dataclass
class RunningStats:
    count: int = 0
    mean: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf

    def add(self, value: float | int) -> None:
        x = float(value)
        if not math.isfinite(x):
            return
        self.count += 1
        self.mean += (x - self.mean) / self.count
        if x < self.minimum:
            self.minimum = x
        if x > self.maximum:
            self.maximum = x

    def clear(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.minimum = math.inf
        self.maximum = -math.inf

    def snapshot(self) -> tuple[int, float | None, float | None, float | None]:
        if self.count == 0:
            return 0, None, None, None
        return self.count, self.mean, self.minimum, self.maximum


@dataclass(frozen=True)
class ReadBlock:
    address: int
    size: int
    variables: tuple[WatchVariableSpec, ...]


class MemoryReadPlanner:
    """Merge nearby Watch variables into a small number of ReadMemEx calls.

    A small gap is allowed because one contiguous read is usually cheaper than
    multiple debugger transactions. The block size is deliberately bounded so
    unrelated variables far apart in RAM are never merged into a huge read.
    """

    def __init__(self, max_gap_bytes: int = 8, max_block_bytes: int = 256) -> None:
        self.max_gap_bytes = max(0, int(max_gap_bytes))
        self.max_block_bytes = max(1, int(max_block_bytes))

    def plan(self, variables: Iterable[WatchVariableSpec]) -> list[ReadBlock]:
        items = sorted(
            (v for v in variables if v.enabled),
            key=lambda v: (v.address, v.size, v.row_id),
        )
        if not items:
            return []

        blocks: list[ReadBlock] = []
        block_start = items[0].address
        block_end = items[0].address + items[0].size
        block_vars = [items[0]]

        for var in items[1:]:
            var_start = var.address
            var_end = var.address + var.size
            gap = max(0, var_start - block_end)
            candidate_end = max(block_end, var_end)
            candidate_size = candidate_end - block_start

            if gap <= self.max_gap_bytes and candidate_size <= self.max_block_bytes:
                block_vars.append(var)
                block_end = candidate_end
            else:
                blocks.append(
                    ReadBlock(
                        address=block_start,
                        size=block_end - block_start,
                        variables=tuple(block_vars),
                    )
                )
                block_start = var_start
                block_end = var_end
                block_vars = [var]

        blocks.append(
            ReadBlock(
                address=block_start,
                size=block_end - block_start,
                variables=tuple(block_vars),
            )
        )
        return blocks
