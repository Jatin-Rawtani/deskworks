"""Document text extraction with a portable cascade + a PDF full-text cache.

PDF extraction tries, in order:
  1. `pdftotext` (poppler) if on PATH       — fast, high quality
  2. `pdfplumber` if installed               — pure-python, good tables
  3. `pypdf`                                 — pure-python fallback (always available)

Extracted PDF text is cached under [index].cache so re-indexing is cheap.
Markdown / text files are read directly (not cached).
"""
from __future__ import annotations
import os, re, json, hashlib, shutil, subprocess

from .config import Config


def _h(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()[:16]


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


# ----------------------------------------------------------------- PDF backends
def _pdftotext(path: str) -> str:
    if not shutil.which("pdftotext"):
        return ""
    try:
        r = subprocess.run(["pdftotext", "-q", path, "-"],
                           capture_output=True, text=True, timeout=300)
        return r.stdout or ""
    except Exception:
        return ""


def _pdfplumber(path: str) -> str:
    try:
        import pdfplumber
    except Exception:
        return ""
    try:
        out = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception:
        return ""


def _pypdf(path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""
    try:
        reader = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception:
        return ""


def _extract_pdf(path: str) -> str:
    for fn in (_pdftotext, _pdfplumber, _pypdf):
        txt = fn(path)
        if txt and len(txt.strip()) > 40:
            return txt
    return ""


# ----------------------------------------------------------------- public API
def read_document_text(path: str, cfg: Config) -> str:
    """Return extracted text for any supported file. PDFs are cached."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        cache_dir = cfg.cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        cpath = os.path.join(cache_dir, _h(path) + ".txt")
        if os.path.exists(cpath) and os.path.getsize(cpath) > 40:
            return _read_text_file(cpath)
        txt = _extract_pdf(path)[: cfg.index["pdf_max_chars"]]
        if len(txt.strip()) > 40:
            with open(cpath, "w") as f:
                f.write(txt)
        return txt
    # markdown / text
    return _read_text_file(path)


def parse_all_pdfs(cfg: Config, verbose: bool = True) -> dict:
    """Pre-warm the PDF cache across all corpus paths. Idempotent."""
    import glob
    exts = (".pdf",)
    excludes = cfg.corpus.get("exclude_substrings", [])
    manifest = os.path.join(cfg.cache_dir(), "manifest.jsonl")
    os.makedirs(cfg.cache_dir(), exist_ok=True)
    done = skip = fail = 0
    with open(manifest, "a") as mf:
        for root in cfg.corpus_paths():
            for path in glob.glob(os.path.join(root, "**", "*.pdf"), recursive=True):
                if any(x in path for x in excludes):
                    continue
                cpath = os.path.join(cfg.cache_dir(), _h(path) + ".txt")
                if os.path.exists(cpath) and os.path.getsize(cpath) > 40:
                    skip += 1
                    continue
                txt = _extract_pdf(path)[: cfg.index["pdf_max_chars"]]
                name = os.path.basename(path)
                if len(txt.strip()) < 40:
                    fail += 1
                    if verbose:
                        print(f"  FAIL    {name[:60]}")
                    continue
                with open(cpath, "w") as f:
                    f.write(txt)
                mf.write(json.dumps({"hash": _h(path), "path": path,
                                     "title": name, "chars": len(txt)}) + "\n")
                done += 1
                if verbose:
                    print(f"  {len(txt):>7}c {name[:60]}")
    if verbose:
        print(f"\nPDF cache: parsed {done}, skipped {skip}, failed {fail}.")
    return {"parsed": done, "skipped": skip, "failed": fail}
