"""Enumerate the sidecar root and parse each notebook. One bad dir never sinks the catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .sidecar import ParsedSidecar, parse_sidecar


@dataclass
class CatalogLoad:
    sidecars: List[ParsedSidecar] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def load_sidecars(root: Path) -> CatalogLoad:
    load = CatalogLoad()
    if not root.exists() or not root.is_dir():
        load.warnings.append(f"NotebookLM root not found: {root}")
        return load

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        readme = child / "README.md"
        if not readme.exists():
            continue
        try:
            parsed = parse_sidecar(readme)
        except Exception as e:  # defensive: a single sidecar must not break the catalog
            load.warnings.append(f"{child.name}: skipped (parse error: {e})")
            continue
        if parsed is None:
            load.warnings.append(f"{child.name}: skipped (no notebook_id found)")
            continue
        load.sidecars.append(parsed)
        load.warnings.extend(f"{parsed.dir_name}: {w}" for w in parsed.warnings)
    return load


def find_sidecar(root: Path, notebook_id: str) -> Optional[ParsedSidecar]:
    for sc in load_sidecars(root).sidecars:
        if sc.notebook_id == notebook_id:
            return sc
    return None
