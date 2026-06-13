import os
from deskworks import summarize, ingest, dashboard, config


# ----- summary line parsing -----
def test_parse_summary_line_well_formed():
    line = "SUMMARY: A study of X. ;; THEMES: a, b, c"
    out = summarize._parse_line(line)
    assert out["summary"] == "A study of X."
    assert out["themes"] == "a, b, c"


def test_parse_summary_line_trailing_fields():
    line = "SUMMARY: One. ;; THEMES: x, y ;; EXTRA: ignore"
    out = summarize._parse_line(line)
    assert out["themes"] == "x, y"


def test_strip_think_block():
    raw = "<think>reasoning</think>SUMMARY: Final. ;; THEMES: z"
    assert "reasoning" not in summarize._strip_think(raw)
    assert summarize._strip_think(raw).startswith("SUMMARY:")


# ----- ingest text reading -----
def test_read_markdown(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("# Title\n\nbody text here")
    c = config.load()  # defaults
    txt = ingest.read_document_text(str(p), c)
    assert "body text here" in txt


def test_pdf_hash_stable():
    h1 = ingest._h("/a/b/c.pdf")
    h2 = ingest._h("/a/b/c.pdf")
    assert h1 == h2 and len(h1) == 16


# ----- dashboard build -----
def test_dashboard_builds_html(tmp_path):
    csv = tmp_path / "s.csv"
    csv.write_text("file,title,summary,themes\n"
                   "a.pdf,a.pdf,First doc,solar, india\n"
                   "b.pdf,b.pdf,Second doc,water\n")
    c = config.load()
    out = dashboard.build_dashboard(c, str(csv), out_html=str(tmp_path / "d.html"))
    assert os.path.exists(out)
    html = open(out).read()
    assert "First doc" in html and "Second doc" in html
    assert "DATA =" in html        # data embedded inline (self-contained)


def test_looks_empty_detects_page_marker_only_extractions():
    from deskworks.ingest import _looks_empty
    # page markers alone are not real content (the silent-failure case)
    markers = " ".join(f"--- Page {i} ---" for i in range(1, 40))
    assert _looks_empty(markers)
    assert _looks_empty("")
    assert _looks_empty("   \n\n  ")
    # real text is kept
    assert not _looks_empty("x" * 400)
    assert not _looks_empty(markers + " " + "real words " * 60)
