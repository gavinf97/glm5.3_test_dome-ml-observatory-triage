"""Cohort selection, kept free of any database code so it can be tested on synthetic rows.

Un-enriched records carry no domain yet, so diversity is spread over what every record does carry:
publication-year band x preprint or journal article, with a cap on records per venue so no one
journal dominates. Already-enriched records are spread over their stored EDAM tier-1 domain.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Optional

YEAR_BANDS = (("<=2015", None, 2015), ("2016-2019", 2016, 2019), ("2020-2022", 2020, 2022),
              ("2023-2024", 2023, 2024), ("2025-2026", 2025, 2026))


def year_band(year) -> str:
    try:
        y = int(year)
    except (TypeError, ValueError):
        return "unknown"
    for name, lo, hi in YEAR_BANDS:
        if (lo is None or y >= lo) and (hi is None or y <= hi):
            return name
    return "unknown"


def venue(row: dict) -> Optional[str]:
    """What the per-venue cap counts: the journal of a journal article. Preprints are not capped --
    a handful of servers carry them all, so a cap per server would starve the preprint strata -- and
    neither is a record with no journal, so missing metadata never empties a stratum."""
    if row.get("epmc_source") == "PPR":
        return None
    value = (row.get("journal") or "").strip().casefold()
    return value or None


def stratum(row: dict) -> str:
    kind = "preprint" if row.get("epmc_source") == "PPR" else "article"
    return f"{year_band(row.get('year'))}|{kind}"


def allocate(available: dict[str, int], total: int, floor: int) -> dict[str, int]:
    """Proportional allocation with a floor per cell (largest remainder), never more than a cell
    has, summing to `total` when the cells hold that many."""
    total = min(total, sum(available.values()))
    alloc = {cell: min(floor, n) for cell, n in available.items()}
    left = total - sum(alloc.values())
    if left < 0:  # the floors alone exceed the total: shrink the largest cells first
        for cell in sorted(alloc, key=lambda c: -alloc[c]):
            while left < 0 and alloc[cell] > 0:
                alloc[cell] -= 1
                left += 1
        return alloc
    while left > 0:
        room = {c: available[c] - alloc[c] for c in available if available[c] > alloc[c]}
        if not room:
            break
        weight = sum(available[c] for c in room)
        shares = {c: left * available[c] / weight for c in room}
        step = {c: min(room[c], int(shares[c])) for c in room}
        if sum(step.values()) == 0:
            for c in sorted(room, key=lambda c: -(shares[c] - int(shares[c]))):
                if left == 0:
                    break
                alloc[c] += 1
                left -= 1
            continue
        for c, k in step.items():
            alloc[c] += k
            left -= k
    return alloc


def select_unenriched(rows: list[dict], total: int, floor: int, venue_cap: int, seed: int) -> list[dict]:
    """Returns `total` rows, each with `stratum` and `wave` (1 or 2) set. Waves alternate within each
    stratum, so both halves are spread the same way."""
    rng = random.Random(seed)
    cells: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["record_id"]):
        cells[stratum(row)].append(row)
    for members in cells.values():
        rng.shuffle(members)
    alloc = allocate({c: len(m) for c, m in cells.items()}, total, floor)

    per_venue: Counter = Counter()
    picked: dict[str, list[dict]] = defaultdict(list)
    chosen: set[str] = set()

    def take(row: dict, cell: str) -> bool:
        v = venue(row)
        if row["record_id"] in chosen or (v is not None and per_venue[v] >= venue_cap):
            return False
        if v is not None:
            per_venue[v] += 1
        chosen.add(row["record_id"])
        picked[cell].append(row)
        return True

    for cell in sorted(cells):
        for row in cells[cell]:
            if len(picked[cell]) >= alloc[cell]:
                break
            take(row, cell)
    # A cell the venue cap kept short is made up from the others, in the same shuffled order.
    shortfall = total - len(chosen)
    for cell in sorted(cells, key=lambda c: -len(cells[c])):
        for row in cells[cell]:
            if shortfall <= 0:
                break
            if take(row, cell):
                shortfall -= 1

    out = []
    i = 0
    for cell in sorted(picked):
        for row in picked[cell]:
            out.append({**row, "stratum": cell, "wave": 1 + i % 2})
            i += 1
    return out


def select_enriched(rows: list[dict], total: int, venue_cap: int, seed: int, key: str = "domain_tier1") -> list[dict]:
    """Round-robin over the stored tier-1 domain (`row[key]`, a plain string), so every domain present
    is as evenly represented as the pool allows; `stratum` is set to that domain."""
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: r["record_id"]):
        groups[row.get(key) or "(none)"].append(row)
    for members in groups.values():
        rng.shuffle(members)
    order = sorted(groups)
    per_venue: Counter = Counter()
    out: list[dict] = []
    cursor = {g: 0 for g in order}
    while len(out) < total and any(cursor[g] < len(groups[g]) for g in order):
        for g in order:
            if len(out) >= total:
                break
            while cursor[g] < len(groups[g]):
                row = groups[g][cursor[g]]
                cursor[g] += 1
                v = venue(row)
                if v is not None and per_venue[v] >= venue_cap:
                    continue
                if v is not None:
                    per_venue[v] += 1
                out.append({**row, "stratum": g})
                break
    return out
