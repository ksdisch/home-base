"""Lenient Markdown artifact extraction.

The sidecars are human-authored. Column order varies wildly across notebooks
(``ID`` vs ``Artifact ID``, ``Format`` vs ``Length`` vs ``Len``), some have no artifact-map
JSON at all, and the same row can carry two artifacts (``Study Guide ID`` + ``Quiz ID``).

Two anti-fabrication rules hold everywhere:
  1. A row contributes an artifact only if an *id column* cell contains a real UUID.
  2. ``Source ID`` columns (and any "source" section) are never treated as artifacts.

Artifacts are typed by, in priority order: the id-column header (e.g. "Quiz ID"),
a ``Type`` column, the nearest section heading, then the title text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

KNOWN_TYPES = (
    "audio",
    "quiz",
    "study_guide",
    "report",
    "flashcards",
    "mind_map",
    "slide_deck",
    "infographic",
    "video",
    "data_table",
)

# Ordered: more specific phrases first ("study guide" before "report").
_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("study guide", "study_guide"),
    ("study_guide", "study_guide"),
    ("quiz", "quiz"),
    ("flashcard", "flashcards"),
    ("mind map", "mind_map"),
    ("mind_map", "mind_map"),
    ("mindmap", "mind_map"),
    ("slide", "slide_deck"),
    ("infographic", "infographic"),
    ("data table", "data_table"),
    ("data_table", "data_table"),
    ("video", "video"),
    ("podcast", "audio"),
    ("audio", "audio"),
    ("report", "report"),
    ("briefing", "report"),
]

_FORMAT_HINTS = (
    "deep_dive",
    "deep dive",
    "debate",
    "brief",
    "critique",
    "interview",
    "default",
    "short",
    "long",
)

TYPE_LABELS = {
    "audio": "Audio",
    "quiz": "Quiz",
    "study_guide": "Study Guide",
    "report": "Report",
    "flashcards": "Flashcards",
    "mind_map": "Mind Map",
    "slide_deck": "Slide Deck",
    "infographic": "Infographic",
    "video": "Video",
    "data_table": "Data Table",
    "unknown": "Artifact",
}


# A truncated/display id in a trusted id column: a hex run that must contain at least one
# a–f letter, so pure-decimal values (dates, counts) are treated as placeholders, not ids.
_SHORT_ID_RE = re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,64}\b")


@dataclass
class RawArtifact:
    artifact_id: str
    type: str  # one of KNOWN_TYPES or "unknown"
    title: str
    episode: Optional[int] = None
    fmt: Optional[str] = None
    length: Optional[str] = None
    status: Optional[str] = None
    section: str = ""
    source: str = "readme"  # readme | map | map+readme
    id_complete: bool = True  # False for truncated display ids (e.g. segal's 8-char ids)


@dataclass
class Table:
    headers: List[str]  # normalized: lowercased, stripped
    rows: List[List[str]]
    section: str


# --------------------------------------------------------------------------- types/titles
def classify_type(text: Optional[str]) -> Optional[str]:
    t = (text or "").lower()
    for kw, val in _TYPE_KEYWORDS:
        if kw in t:
            return val
    return None


# Section headings that never describe artifacts (sources + migration/rebuild prose).
_NON_ARTIFACT_SECTION = ("source", "migration", "rebuild", "deleted", "failed import")


def _is_source_section(section: str) -> bool:
    return any(k in (section or "").lower() for k in _NON_ARTIFACT_SECTION)


def _type_from_section(section: str) -> Optional[str]:
    s = (section or "").lower()
    if "study aid" in s:  # ambiguous (holds both guide + quiz) — let the id column decide
        return None
    if "quiz" in s:
        return "quiz"
    if "study guide" in s:
        return "study_guide"
    if any(k in s for k in ("audio", "podcast", "season", "standalone", "episode")):
        return "audio"
    return None


def _type_from_title(title: str) -> Optional[str]:
    t = (title or "").lower()
    if re.search(r"\bquiz\b", t):
        return "quiz"
    if "study guide" in t:
        return "study_guide"
    if re.search(r"s\d+\s*e\s*\d+", t):  # S1E2 -> podcast audio
        return "audio"
    if re.search(r"\bep\.?\s*\d+", t):  # "Ep 3 — ..." defaults to audio episode
        return "audio"
    return None


def _episode_from(cells_ep: Optional[str], title: str) -> Optional[int]:
    # Check both the Ep column and the title for SxEy / "Ep N" before any bare digit, so
    # "S1E2" yields episode 2 (not the '1' in 'S1').
    for text in (cells_ep, title):
        if not text:
            continue
        t = text.lower()
        m = re.search(r"s\d+\s*e\s*(\d+)", t)
        if m:
            return int(m.group(1))
        m = re.search(r"\bep\.?\s*(\d+)", t)
        if m:
            return int(m.group(1))
    if cells_ep:  # a bare-number Ep column ("1".."10")
        m = re.search(r"\d+", cells_ep)
        if m:
            return int(m.group())
    return None


def _clean_title(text: str) -> str:
    # Strip leading status emoji / checkmarks / bold markers and surrounding ** **.
    t = text.strip().strip("*").strip()
    t = re.sub(r"^[\s\W_]*?(?=[0-9A-Za-z])", "", t, count=1)
    return t.strip()


# --------------------------------------------------------------------------- table parsing
def _split_row(line: str) -> List[str]:
    s = line.strip()
    s = s.replace("\\|", "\x00")  # protect escaped pipes so a literal "|" in a cell stays put
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.replace("\x00", "|").strip() for c in s.split("|")]


def _is_separator(cells: List[str]) -> bool:
    seen = False
    for c in cells:
        c = c.strip()
        if c == "":
            continue
        if re.fullmatch(r":?-{1,}:?", c) is None:
            return False
        seen = True
    return seen


def extract_tables(markdown: str) -> List[Table]:
    lines = markdown.splitlines()
    tables: List[Table] = []
    section = ""
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            i += 1
            continue
        if (
            "|" in line
            and i + 1 < n
            and "|" in lines[i + 1]
            and _is_separator(_split_row(lines[i + 1]))
        ):
            headers = [h.lower() for h in _split_row(line)]
            rows: List[List[str]] = []
            j = i + 2
            while j < n and lines[j].strip() and "|" in lines[j]:
                rows.append(_split_row(lines[j]))
                j += 1
            tables.append(Table(headers=headers, rows=rows, section=section))
            i = j
            continue
        i += 1
    return tables


def _is_id_header(h: str) -> bool:
    h = h.strip()
    if "source" in h:  # 'Source ID' columns are sources, never artifacts
        return False
    return h == "id" or h == "artifactid" or h.endswith(" id") or h.endswith("_id")


def _id_header_type(h: str) -> Optional[str]:
    """Type implied by a typed id column, e.g. 'Study Guide ID' -> study_guide."""
    h = h.strip()
    if h in ("id", "artifact id", "artifactid", "artifact_id"):
        return None
    prefix = re.sub(r"[_ ]id$", "", h).strip()
    return classify_type(prefix)


def _find_col(headers: List[str], *names: str) -> Optional[int]:
    for i, h in enumerate(headers):
        if h in names:
            return i
    return None


def classify_table_artifacts(table: Table) -> List[RawArtifact]:
    if _is_source_section(table.section):
        return []  # a Sources table is never artifacts, whatever its id column is named
    headers = table.headers
    id_cols = [(i, _id_header_type(h)) for i, h in enumerate(headers) if _is_id_header(h)]
    if not id_cols:
        return []  # no id column we trust -> emit nothing (never fabricate)

    type_col = _find_col(headers, "type")
    title_col = _find_col(headers, "title", "name", "topic")
    ep_col = _find_col(headers, "ep", "#", "episode", "ep.")
    fmt_col = _find_col(headers, "format")
    len_col = _find_col(headers, "length", "len")
    status_col = _find_col(headers, "status")
    section_type = _type_from_section(table.section)

    # If there's no explicit title column, fall back to the first column that isn't an
    # id/type/format/length/status/ep column (e.g. segal's audio table leads with the title).
    if title_col is None:
        special = {ci for ci, _ in id_cols}
        for c in (type_col, ep_col, fmt_col, len_col, status_col):
            if c is not None:
                special.add(c)
        for i in range(len(headers)):
            if i not in special:
                title_col = i
                break

    out: List[RawArtifact] = []
    for row in table.rows:

        def cell(idx: Optional[int]) -> str:
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        type_text = cell(type_col)
        title_text = cell(title_col)
        ep_text = cell(ep_col)

        for ci, header_type in id_cols:
            raw = cell(ci)
            m = UUID_RE.search(raw)
            if m:
                artifact_id = m.group(0).lower()
                id_complete = True
            else:
                # Accept a truncated hex id (only in a trusted id column).
                sm = _SHORT_ID_RE.search(raw.lower())
                if not sm:
                    continue  # empty / "pending" / "—" -> skip this row's artifact
                artifact_id = sm.group(0)
                id_complete = False

            resolved = (
                header_type
                or classify_type(type_text)
                or section_type
                or _type_from_title(title_text)
                or "unknown"
            )
            episode = _episode_from(ep_text, title_text)
            # A typed id column (Study Guide ID / Quiz ID) carries no per-row title text,
            # so synthesize a clean one.
            if header_type and (not title_text or len(id_cols) > 1):
                label = TYPE_LABELS.get(resolved, "Artifact")
                title = f"Ep {episode} — {label}" if episode is not None else label
            else:
                title = _clean_title(title_text) or (
                    f"{TYPE_LABELS.get(resolved, 'Artifact')}"
                )

            out.append(
                RawArtifact(
                    artifact_id=artifact_id,
                    type=resolved,
                    title=title,
                    episode=episode,
                    fmt=cell(fmt_col) or None,
                    length=cell(len_col) or None,
                    status=cell(status_col) or None,
                    section=table.section,
                    source="readme",
                    id_complete=id_complete,
                )
            )
    return out


# --------------------------------------------------------------------------- bullet parsing
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def _is_artifact_section(section: str) -> bool:
    s = (section or "").lower()
    if _is_source_section(section):  # excludes sources + migration/rebuild/deleted prose
        return False
    return _type_from_section(section) is not None or any(
        k in s for k in ("artifact", "library", "standalone", "episode", "season")
    )


def extract_bullet_artifacts(markdown: str) -> List[RawArtifact]:
    """Catch artifacts written as bullets, e.g. the engineering-abstractions standalone library:
    ``- ✅ A Philosophy of Software Design — deep_dive / long — c4f3842e-...``.

    Guarded against prose: only bullets under an artifact-ish section heading whose UUID sits in
    the final ``—``-segment qualify. This rejects migration-note bullets that merely *mention*
    another notebook's id mid-sentence.
    """
    out: List[RawArtifact] = []
    section = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        m = _BULLET_RE.match(line)
        if not m:
            continue
        if not _is_artifact_section(section):
            continue
        content = m.group(1)
        um = UUID_RE.search(content)
        if not um:
            continue
        artifact_id = um.group(0).lower()

        segs = [s.strip() for s in re.split(r"\s+[—–-]\s+", content)]
        tail = segs[-1] if segs else ""
        tm = UUID_RE.search(tail)
        if not tm:
            continue  # UUID must be the trailing field, not buried in prose
        # The trailing segment must be essentially JUST the UUID (a real artifact line),
        # not prose that happens to end with a notebook id.
        remainder = (tail[: tm.start()] + tail[tm.end() :]).strip()
        if any(ch.isalnum() for ch in remainder):
            continue
        title_seg = segs[0] if segs else content
        title = _clean_title(title_seg)
        fmt = None
        for seg in segs[1:]:
            if UUID_RE.search(seg):
                continue
            if any(h in seg.lower() for h in _FORMAT_HINTS):
                fmt = seg
                break

        resolved = _type_from_section(section) or _type_from_title(title) or "unknown"
        out.append(
            RawArtifact(
                artifact_id=artifact_id,
                type=resolved,
                title=title or TYPE_LABELS.get(resolved, "Artifact"),
                episode=_episode_from(None, title),
                fmt=fmt,
                section=section,
                source="readme",
            )
        )
    return out
