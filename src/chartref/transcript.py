"""Transcript parsing and detection of spoken references to chart objects."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
NOUNS = (r"bar|bars|candle|candles|breakout|pullback|wedge|entry|setup|trade|pattern|push|signal\s+bar|one"
         r"|range|channel|triangle|leg|swing")
# Objects that span several bars by definition: resolved by the pointer's sweep, not a single dwell.
REGION_NOUNS = {"wedge", "pattern", "range", "channel", "triangle", "leg", "swing"}
DEICTIC = re.compile(
    rf"\b(?P<det>this|that|these|those)\b(?:\s+(?:is|was)\s+(?:the|a|an))?"
    rf"(?:\s+(?P<num>one|two|three|four|five|six|seven|eight|\d+))?"
    rf"(?:\s+(?:second|first|failed|strong|bull|bear|outside|inside|tight))*\s+(?P<noun>{NOUNS})\b"
    rf"|\b(?P<here>(?:buy|sell|enter|exit)\s+here)\b",
    re.IGNORECASE,
)


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str


@dataclass
class Mention:
    phrase: str
    plural: bool
    expected_count: int | None


def _ts(s: str) -> float:
    h, m, rest = s.strip().split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def parse_srt(path: str | Path) -> list[Segment]:
    blocks = Path(path).read_text(encoding="utf-8").strip().split("\n\n")
    segs = []
    for b in blocks:
        lines = [l for l in b.splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        a, z = lines[1].split("-->")
        segs.append(Segment(int(lines[0]), _ts(a), _ts(z), " ".join(lines[2:])))
    return segs


def find_mention(text: str) -> Mention | None:
    m = DEICTIC.search(text)
    if not m:
        return None
    if m.group("here"):
        return Mention(m.group(0), False, 1)
    det, num, noun = m.group("det").lower(), m.group("num"), m.group("noun").lower()
    count = None
    if num:
        count = int(num) if num.isdigit() else NUMBER_WORDS[num.lower()]
    plural = (det in ("these", "those") or (noun.endswith("s") and noun not in ("push",))
              or (count or 1) > 1 or noun in REGION_NOUNS)
    if not plural:
        count = 1
    return Mention(m.group(0), plural, count)
