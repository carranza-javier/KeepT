"""How much CPU KeepT can use: the thread counts of OCR and translation follow it, so a basic
two core PC is not flooded with threads sized for a twelve thread laptop."""

from __future__ import annotations

import os


_cores: int | None = None


def cores() -> int:
    """Logical CPUs this process may run on (respects the process affinity)."""
    global _cores
    if _cores is None:
        count = None
        try:
            from .platform import services

            count = services().usable_cpus()
        except Exception:  # noqa: BLE001 - fall back to what Python knows
            count = None
        _cores = max(1, count or getattr(os, "process_cpu_count", os.cpu_count)() or 1)
    return _cores


def recognizer_threads() -> int:
    """Threads of the main line recognizer (one line at a time, for clicks)."""
    return max(1, min(4, cores()))


def reread_helpers() -> int:
    """Extra threads that read the blocks asked for when there are several (Enter). On a CPU
    with few cores they would only take time from the block the user waits for."""
    n = cores()
    return 3 if n >= 8 else (1 if n >= 4 else 0)


def translation_slots() -> int:
    """Languages translated at the same time. Each model uses translation_threads(): on a CPU
    with few cores several at once only slow every one of them down (measured on two cores: a
    short block took 6.7 s with four languages at once)."""
    return max(1, min(4, cores() // 3))


def translation_threads() -> int:
    """Threads per translation model: two is as fast as six for one block. With few cores one:
    two threads next to the line recognizer made a page on two cores take 10.7 s instead of
    6.4 s (more threads than cores stall CTranslate2), although alone two are faster."""
    return 2 if cores() >= 6 else 1
