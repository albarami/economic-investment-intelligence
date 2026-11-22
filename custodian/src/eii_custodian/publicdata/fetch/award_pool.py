"""Bounded award readers; transport pressure permanently reduces this run to one."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import TypeVar

from .award_checks import AwardError

T = TypeVar("T")


def reader_count(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 4:
        raise AwardError("award_readers_invalid")
    return value


@dataclass
class ReaderPool:
    max_readers: int = 1
    reduced: Event = field(default_factory=Event)
    _lock: Lock = field(default_factory=Lock)
    reason: str = ""

    def __post_init__(self) -> None:
        reader_count(self.max_readers)

    def reduce(self, reason: str) -> None:
        with self._lock:
            if not self.reduced.is_set():
                self.reason = reason
                self.reduced.set()

    def receipt(self) -> dict[str, object]:
        return {
            "max_readers": self.max_readers,
            "fallback": self.reduced.is_set(),
            "fallback_reason": self.reason,
        }

    def read(self, urls: Sequence[str], read: Callable[[str], T]) -> list[T]:
        """Drain each bounded batch before starting another; no queued population.

        Already running requests finish after a refusal; no next batch can start
        in parallel after reduction. Each worker inherits its own Context copy.
        """
        results: dict[str, T] = {}
        offset = 0
        with ThreadPoolExecutor(max_workers=self.max_readers) as executor:
            while offset < len(urls):
                width = 1 if self.reduced.is_set() else self.max_readers
                batch = urls[offset : offset + width]
                if width == 1:
                    results[batch[0]] = read(batch[0])
                else:
                    pending = {
                        executor.submit(copy_context().run, read, url): url
                        for url in batch
                    }
                    for future in as_completed(pending):
                        results[pending[future]] = future.result()
                offset += len(batch)
        return [results[url] for url in urls]
