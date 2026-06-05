from app.catalog.frontmatter import parse_frontmatter


def test_parses_basic_frontmatter():
    fm, body = parse_frontmatter("---\nnotebook_id: abc\ntitle: Hi\n---\n# Body\ntext")
    assert fm["notebook_id"] == "abc"
    assert fm["title"] == "Hi"
    assert "# Body" in body


def test_no_frontmatter_returns_whole_text():
    fm, body = parse_frontmatter("# Just a body\nno frontmatter")
    assert fm == {}
    assert body.startswith("# Just a body")


def test_malformed_yaml_never_raises():
    fm, body = parse_frontmatter("---\ntags: [a : b : c\nbad\n---\n# Body")
    assert fm == {}
    assert "# Body" in body


def test_unterminated_frontmatter():
    fm, body = parse_frontmatter("---\nnotebook_id: x\nno closing fence")
    assert fm == {}
