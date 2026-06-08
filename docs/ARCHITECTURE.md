# Architecture

LocalMind is a small, legible RAG system. ~700 lines of Python, no heavy
framework. This document explains every design decision so you can trust and
modify it.

## Pipeline

```
corpus folders
   │  ingest.py        extract text (pdftotext → pdfplumber → pypdf), cache PDF text
   ▼
chunks               core.gather_chunks(): ~1100 chars, 180 overlap, min 25 chars
   │  core.build_index()
   ▼
index/               embeddings.npy (BGE, L2-normalized) + chunks.jsonl.gz (metadata)
   │  core.retrieve()
   ▼
hybrid retrieval     BGE cosine  +  BM25  →  reciprocal-rank fusion  →  per-doc dedup
   │  core.stream_answer()
   ▼
generation           top-K passages + cite-or-refuse prompt + last 4 turns → your model
```

## Retrieval detail

**Two scorers, fused.** Pure vector search misses exact terms (names, IDs,
numbers); pure keyword search misses paraphrase. We run both:

- **Semantic:** query embedded with BGE (asymmetric — queries get an instruction
  prefix, documents don't), cosine similarity against the normalized matrix
  (a single `emb @ qv` matmul).
- **Lexical:** BM25 over whitespace/alphanumeric tokens.

**Reciprocal-rank fusion (RRF).** Rather than trying to normalize two
incomparable score scales, we fuse by *rank*:

```
score(doc) = Σ  1 / (k + rank_in_that_ranker)      k = 60
```

over the top `pool = max(4·top_k, 40)` of each ranker. RRF is robust, parameter-
light, and needs no score calibration — the standard choice for hybrid search.

**Per-document diversity.** After fusion we cap how many chunks any single
document contributes (`max_chunks_per_doc`, default 2). This stops one long file
from filling the whole context window and surfaces a broader evidence base.

## Generation

- **Cite-or-refuse system prompt.** The model is told to answer only from the
  provided passages, cite them as `[1]`, `[2]`, and explicitly say when something
  isn't in the library. This is the single biggest hallucination reducer.
- **Conversation memory.** The last 4 turns (truncated) are included so
  follow-ups like "tell me more about the second one" work.
- **Streaming.** Server-sent events: sources are emitted first (so the UI can
  render citations immediately), then answer deltas, then a done marker.

## Index format

- `embeddings.npy` — `float32` matrix, `[n_chunks, dim]`, L2-normalized so cosine
  is a dot product.
- `chunks.jsonl.gz` — one JSON object per chunk: `text`, `source`, `title`,
  `path`. Gzipped; loaded once and cached in process.
- BM25 is rebuilt in memory on load (fast; avoids a second on-disk artifact).

This is deliberately simple — `.npy` + brute-force matmul handles tens of
thousands of chunks in milliseconds on CPU. If you outgrow it, the swap point is
`core.load_index()` / `core.retrieve()` (drop in FAISS or hnswlib without
touching the rest).

## Performance notes

- **Build on GPU, serve on CPU.** `localmind index` uses Apple MPS (or CUDA) if
  available for the one-time embedding pass; the always-on server pins the
  embedder to CPU to avoid contending with your local LLM for GPU memory.
- **First-query warmup.** The web server preloads the model + index in a
  background thread on startup so the first question isn't slow.

## Files

| File | Responsibility |
|------|----------------|
| `config.py` | TOML config, defaults, path expansion |
| `ingest.py` | text extraction + PDF cache |
| `core.py` | chunking, embeddings, index I/O, retrieval, generation |
| `summarize.py` | zero-token bulk folder summaries |
| `dashboard.py` | self-contained searchable HTML |
| `web.py` | streaming Flask chat + safe file-open |
| `cli.py` | `localmind` command |
