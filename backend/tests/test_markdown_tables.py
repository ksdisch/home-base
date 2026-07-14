from app.catalog.markdown_tables import (
    classify_table_artifacts,
    classify_type,
    extract_bullet_artifacts,
    extract_tables,
)

U1 = "11111111-1111-1111-1111-111111111111"
U2 = "22222222-2222-2222-2222-222222222222"
U3 = "33333333-3333-3333-3333-333333333333"


def _arts(md: str):
    out = []
    for t in extract_tables(md):
        out.extend(classify_table_artifacts(t))
    return out


def test_column_order_independence():
    # ID first vs ID last must both work.
    a = _arts(f"## Audio\n| Artifact ID | Title | Type |\n|---|---|---|\n| {U1} | Ep 1 — X | Audio |\n")
    b = _arts(f"## Audio\n| Type | Title | Artifact ID |\n|---|---|---|\n| Audio | Ep 1 — X | {U1} |\n")
    assert a and b
    assert a[0].type == b[0].type == "audio"
    assert a[0].artifact_id == b[0].artifact_id == U1


def test_two_ids_one_row_yields_two_artifacts():
    arts = _arts(
        f"### Study aids\n| Ep | Topic | Study Guide ID | Quiz ID |\n|---|---|---|---|\n"
        f"| 1 | intro | {U1} | {U2} |\n"
    )
    types = {a.type for a in arts}
    assert types == {"study_guide", "quiz"}
    assert {a.episode for a in arts} == {1}


def test_source_id_column_is_never_an_artifact():
    arts = _arts(f"## Sources\n| # | Title | Source ID |\n|---|---|---|\n| 1 | A source | {U1} |\n")
    assert arts == []


def test_row_without_uuid_is_skipped():
    arts = _arts(
        f"## Audio\n| Ep | Title | Artifact ID |\n|---|---|---|\n"
        f"| 1 | Good | {U1} |\n| 2 | Pending | (none yet) |\n"
    )
    assert len(arts) == 1
    assert arts[0].artifact_id == U1


def test_truncated_id_accepted_and_flagged():
    arts = _arts("## Audio\n| Title | Artifact ID |\n|---|---|\n| Ep 1 | 1a2b3c4d |\n")
    assert len(arts) == 1
    assert arts[0].artifact_id == "1a2b3c4d"
    assert arts[0].id_complete is False


def test_s1e_episode_number_not_the_one_in_s1():
    arts = _arts(
        f"### Screen Ready\n| Ep | Title | Artifact ID |\n|---|---|---|\n"
        f"| S1E2 | Know the Firm | {U1} |\n| S1E6 | Finale | {U2} |\n"
    )
    eps = sorted(a.episode for a in arts)
    assert eps == [2, 6]


def test_bullet_artifacts_only_in_artifact_sections():
    md = (
        f"### Standalone library — audio\n- ✅ A Title — deep_dive / long — {U1}\n\n"
        f"## Migration notes\n- The old notebook (ID `{U2}`) was archived, not deleted.\n"
    )
    arts = extract_bullet_artifacts(md)
    ids = {a.artifact_id for a in arts}
    assert U1 in ids  # real standalone artifact
    assert U2 not in ids  # prose mention must NOT be ingested


def test_classify_type_specificity():
    assert classify_type("Report (Study Guide)") == "study_guide"
    assert classify_type("Report — Personal Roadmap") == "report"
    assert classify_type("Mind Map") == "mind_map"
    assert classify_type("Audio — deep_dive") == "audio"


# -- source manifests (merge-produced sidecars) must never fabricate artifacts ----------
# Regression for the 2026-07-13 ai-stack drift: a "## Source manifest" section with
# "### From <notebook> (23/23 migrated)" subheadings and | New ID | Title | Method | Note |
# tables produced 59 "unknown" artifacts. Three independent guards, each tested alone.


def test_source_manifest_tables_are_never_artifacts():
    md = (
        "## Source manifest (61 = 66 raw − 3 exact dupes)\n\n"
        "### From ai-cs-glossary (23/23 migrated)\n\n"
        "| New ID | Title | Method | Note |\n|---|---|---|---|\n"
        "| 2e92f94c | AI/CS Glossary (master text) | text re-add | **Anchor** |\n"
        "| d147b06d | Big Bird (NeurIPS PDF) | url | URL-as-title |\n\n"
        "### From the Forge notebook (1/1 — via dedupe)\n\n"
        f"| New ID | Title | Method | Note |\n|---|---|---|---|\n| {U1} | Forge paper | file | |\n"
    )
    assert _arts(md) == []


def test_migrated_and_dedupe_headings_are_source_sections():
    # Keyword guard alone: no Method column, plain Artifact ID — the heading must exclude it.
    for heading in ("### From x (3/3 migrated)", "### Merged rows (via dedupe)"):
        arts = _arts(f"{heading}\n| Artifact ID | Title |\n|---|---|\n| {U1} | A thing |\n")
        assert arts == [], heading


def test_method_column_disqualifies_table_even_under_neutral_heading():
    # Shape guard alone: heading carries no source keyword at all.
    arts = _arts(
        f"### Imported items\n| ID | Title | Method |\n|---|---|---|\n| {U1} | A paper | url |\n"
    )
    assert arts == []


def test_source_typed_rows_skipped_but_artifact_rows_kept():
    # Row guard alone: same table, one row typed "url" (a source), one typed Audio.
    arts = _arts(
        f"### Library\n| Artifact ID | Title | Type |\n|---|---|---|\n"
        f"| {U1} | Some webpage | url |\n| {U2} | Ep 1 — Intro | Audio |\n"
    )
    assert len(arts) == 1
    assert arts[0].artifact_id == U2
    assert arts[0].type == "audio"
