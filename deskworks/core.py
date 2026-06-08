"""Deskworks core — retrieval + generation engine.

Fully local retrieval: BGE semantic embeddings + BM25 keyword scores fused with
reciprocal-rank fusion (RRF), de-duplicated per document. Answers are generated
by any OpenAI-compatible chat endpoint with conversation memory, streaming, and a
cite-or-refuse system prompt. No data leaves the machine except the prompt sent
to your configured (typically local) model endpoint.
"""
from __future__ import annotations
import os, re, json, glob, gzip, urllib.request
import numpy as np

from .config import Config, load as load_config
from .ingest import read_document_text

# ------------------------------------------------------------------ chunking
def _chunk(text: str, chars: int, overlap: int) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    if not text:
        return []
    if len(text) <= chars:
        return [text]
    out, i = [], 0
    step = max(1, chars - overlap)
    while i < len(text):
        out.append(text[i:i + chars])
        i += step
    return out


def gather_chunks(cfg: Config) -> list[dict]:
    """Walk corpus paths, extract text, chunk. Returns list of chunk dicts."""
    chunks: list[dict] = []
    exts = tuple(e.lower() for e in cfg.corpus["include_ext"])
    excludes = cfg.corpus.get("exclude_substrings", [])
    cc, co = cfg.index["chunk_chars"], cfg.index["chunk_overlap"]

    def add(text, source, title, path):
        for piece in _chunk(text, cc, co):
            if len(piece.strip()) >= 25:
                chunks.append({"text": piece, "source": source,
                               "title": title, "path": path})

    for root in cfg.corpus_paths():
        if not os.path.isdir(root):
            continue
        for path in glob.glob(os.path.join(root, "**", "*"), recursive=True):
            if not os.path.isfile(path):
                continue
            if any(x in path for x in excludes):
                continue
            if not path.lower().endswith(exts):
                continue
            text = read_document_text(path, cfg)
            if text:
                source = os.path.splitext(path)[1].lstrip(".").lower() or "doc"
                add(text, source, os.path.basename(path), path)
    return chunks


# ------------------------------------------------------------------ embeddings
_model = None
def get_model(cfg: Config):
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        device = os.environ.get("DESKWORKS_EMBED_DEVICE", cfg.embed["device"])
        _model = SentenceTransformer(cfg.embed["model"], device=device)
    return _model


# ------------------------------------------------------------------ index I/O
_cache: dict = {}

def build_index(cfg: Config, verbose: bool = True) -> int:
    chunks = gather_chunks(cfg)
    if not chunks:
        raise SystemExit(
            "No documents found. Set [corpus].paths in your deskworks.toml to "
            "folders that contain .pdf/.md/.txt files."
        )
    if verbose:
        from collections import Counter
        print(f"Gathered {len(chunks)} chunks:")
        for src, n in Counter(c["source"] for c in chunks).most_common():
            print(f"   {n:6d}  {src}")
    model = get_model(cfg)
    texts = [c["text"] for c in chunks]
    emb = model.encode(texts, batch_size=64, normalize_embeddings=True,
                       show_progress_bar=verbose).astype("float32")
    os.makedirs(cfg.index_dir(), exist_ok=True)
    np.save(cfg.emb_path(), emb)
    with gzip.open(cfg.meta_path(), "wt", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    if verbose:
        print(f"Saved index: {len(chunks)} chunks, dim {emb.shape[1]} -> {cfg.index_dir()}")
    _cache.clear()
    return len(chunks)


def load_index(cfg: Config):
    if "emb" not in _cache:
        if not os.path.exists(cfg.emb_path()):
            raise SystemExit("No index yet. Run:  deskworks index")
        _cache["emb"] = np.load(cfg.emb_path())
        rows = []
        with gzip.open(cfg.meta_path(), "rt", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))
        _cache["chunks"] = rows
        from rank_bm25 import BM25Okapi
        _cache["bm25"] = BM25Okapi([_tok(c["text"]) for c in rows])
    return _cache["emb"], _cache["chunks"], _cache["bm25"]


def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def warmup(cfg: Config):
    """Preload model + index so the first query is instant."""
    get_model(cfg).encode(["warm"], normalize_embeddings=True)
    load_index(cfg)


# ------------------------------------------------------------------ retrieval
def retrieve(cfg: Config, query: str, top_k: int | None = None) -> list[dict]:
    emb, chunks, bm25 = load_index(cfg)
    top_k = top_k or cfg.index["top_k"]
    model = get_model(cfg)
    prefix = cfg.embed.get("query_prefix", "")
    qv = model.encode([prefix + query], normalize_embeddings=True).astype("float32")[0]
    sem = emb @ qv
    lex = np.array(bm25.get_scores(_tok(query)), dtype="float32")

    pool = max(top_k * 4, 40)
    sem_rank = np.argsort(-sem)[:pool]
    lex_rank = np.argsort(-lex)[:pool]
    K = float(cfg.index["rrf_k"])
    fused: dict[int, float] = {}
    for r, idx in enumerate(sem_rank):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (K + r)
    for r, idx in enumerate(lex_rank):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (K + r)

    max_per_doc = cfg.index["max_chunks_per_doc"]
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])
    hits, seen = [], {}
    for idx, score in ranked:
        c = chunks[idx]
        key = (c["source"], c["title"])
        if seen.get(key, 0) >= max_per_doc:
            continue
        seen[key] = seen.get(key, 0) + 1
        hits.append({"text": c["text"], "source": c["source"], "title": c["title"],
                     "path": c.get("path", ""), "score": float(score),
                     "sem": float(sem[idx])})
        if len(hits) >= top_k:
            break
    return hits


# ------------------------------------------------------------------ generation
SYS = (
    "You are Deskworks, a research assistant answering ONLY from the user's own "
    "documents. Use the CONTEXT passages provided. Cite the passages you use with "
    "their bracket numbers like [1], [2]. Prefer specifics — names, numbers, "
    "findings — over generalities. If the answer is not in the context, say plainly: "
    "\"That isn't in your library yet.\" Never invent sources, numbers, or facts. "
    "Use earlier turns of the conversation for follow-ups like \"tell me more about the second one.\""
)


def _build_messages(query, hits, history):
    ctx = "\n\n".join(
        f"[{i+1}] ({h['source']} · {h['title']})\n{h['text']}" for i, h in enumerate(hits)
    )
    msgs = [{"role": "system", "content": SYS}]
    for turn in (history or [])[-4:]:
        role, content = turn.get("role"), turn.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content[:1500]})
    msgs.append({"role": "user",
                 "content": f"CONTEXT:\n{ctx}\n\nQUESTION: {query}\n\nAnswer with citations."})
    return msgs


def _endpoint(cfg: Config) -> str:
    return cfg.llm["base_url"].rstrip("/") + "/chat/completions"


def _payload(cfg: Config, msgs, stream: bool) -> bytes:
    body = {
        "model": cfg.llm["model"], "messages": msgs,
        "max_tokens": cfg.llm["max_tokens"], "temperature": cfg.llm["temperature"],
        "stream": stream,
    }
    if cfg.llm.get("disable_thinking"):
        body["chat_template_kwargs"] = {"enable_thinking": False}
    return json.dumps(body).encode()


def _headers(cfg: Config) -> dict:
    h = {"Content-Type": "application/json"}
    if cfg.llm.get("api_key"):
        h["Authorization"] = f"Bearer {cfg.llm['api_key']}"
    return h


def answer(cfg: Config, query: str, history=None, top_k=None) -> dict:
    hits = retrieve(cfg, query, top_k)
    req = urllib.request.Request(_endpoint(cfg),
                                 data=_payload(cfg, _build_messages(query, hits, history), False),
                                 headers=_headers(cfg))
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            d = json.load(resp)
        text = re.sub(r"<think>.*?</think>", "", d["choices"][0]["message"]["content"],
                      flags=re.DOTALL | re.I).strip()
    except Exception as e:
        text = f"(model error talking to {cfg.llm['base_url']}: {e})"
    return {"answer": text, "sources": hits}


def stream_answer(cfg: Config, query: str, history=None, top_k=None):
    """Yields ('sources', hits), then ('delta', str)…, then ('done', None)."""
    hits = retrieve(cfg, query, top_k)
    yield ("sources", hits)
    req = urllib.request.Request(_endpoint(cfg),
                                 data=_payload(cfg, _build_messages(query, hits, history), True),
                                 headers=_headers(cfg))
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                except Exception:
                    delta = ""
                if delta:
                    yield ("delta", delta)
    except Exception as e:
        yield ("delta", f"(model error talking to {cfg.llm['base_url']}: {e})")
    yield ("done", None)
