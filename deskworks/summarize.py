"""Bulk-summarize a folder of documents with the local model — zero API tokens.

For each PDF/markdown/text file: one-sentence summary + theme tags, written
incrementally to Markdown + CSV. Resumable (skips files already summarized).
Feeds the searchable dashboard (see dashboard.py).
"""
from __future__ import annotations
import os, csv, glob, json, re, urllib.request

from .config import Config
from .ingest import read_document_text


def _strip_think(t: str) -> str:
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL | re.I)
    m = re.search(r"SUMMARY:.*", t, flags=re.DOTALL)
    return (m.group(0) if m else t).strip().replace("\n", " ")


def _prompt(taxonomy_hint: str) -> str:
    return (
        "You are tagging a document for a personal research library.\n"
        "Reply with ONE line only, in this exact format:\n"
        f"SUMMARY: <one clear sentence> ;; {taxonomy_hint}\n"
        "Example: SUMMARY: Reviews methods for low-cost rooftop solar in schools. ;; "
        "THEMES: solar, education, cost analysis, India\n\n"
        "DOCUMENT TEXT:\n"
    )


def _call(cfg: Config, text: str, taxonomy_hint: str, max_chars: int = 6000) -> str:
    body = json.dumps({
        "model": cfg.llm["model"],
        "messages": [{"role": "user", "content": _prompt(taxonomy_hint) + text[:max_chars]}],
        "max_tokens": 220, "temperature": 0.1, "stream": False,
        **({"chat_template_kwargs": {"enable_thinking": False}}
           if cfg.llm.get("disable_thinking") else {}),
    }).encode()
    headers = {"Content-Type": "application/json"}
    if cfg.llm.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg.llm['api_key']}"
    req = urllib.request.Request(cfg.llm["base_url"].rstrip("/") + "/chat/completions",
                                 data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            d = json.load(resp)
        return _strip_think(d["choices"][0]["message"]["content"])
    except Exception as e:
        return f"SUMMARY: (model error: {e}) ;; THEMES: error"


def _parse_line(line: str) -> dict:
    summary, themes = line, ""
    m = re.search(r"SUMMARY:\s*(.*?)\s*;;\s*THEMES:\s*(.*)", line, re.I)
    if m:
        summary = m.group(1).strip()
        themes = m.group(2).strip()
        # drop any trailing extra fields after another ;;
        themes = themes.split(";;")[0].strip()
    return {"summary": summary, "themes": themes}


def summarize_folder(cfg: Config, folder: str, out_basename: str,
                     verbose: bool = True) -> str:
    folder = os.path.expanduser(folder)
    out_dir = cfg.summaries_dir()
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, out_basename + ".md")
    csv_path = os.path.join(out_dir, out_basename + ".csv")

    done = set()
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                done.add(row.get("file", ""))

    exts = tuple(e.lower() for e in cfg.corpus["include_ext"])
    files = sorted(p for p in glob.glob(os.path.join(folder, "**", "*"), recursive=True)
                   if os.path.isfile(p) and p.lower().endswith(exts))
    if verbose:
        print(f"{len(files)} files in {folder} ({len(done)} already done).")

    new_csv = not os.path.exists(csv_path)
    with open(md_path, "a") as md, open(csv_path, "a", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=["file", "title", "summary", "themes"])
        if new_csv:
            writer.writeheader()
        for i, path in enumerate(files, 1):
            name = os.path.basename(path)
            if name in done:
                continue
            text = read_document_text(path, cfg)
            if not text or len(text.strip()) < 40:
                continue
            parsed = _parse_line(_call(cfg, text, cfg.summarize["taxonomy_hint"]))
            writer.writerow({"file": name, "title": name,
                             "summary": parsed["summary"], "themes": parsed["themes"]})
            cf.flush()
            md.write(f"### {name}\n\n- **Summary:** {parsed['summary']}\n"
                     f"- **Themes:** {parsed['themes']}\n\n")
            md.flush()
            if verbose:
                print(f"[{i}/{len(files)}] {parsed['summary'][:70]}")
    if verbose:
        print(f"\nWrote {md_path}\n      {csv_path}")
    return csv_path
