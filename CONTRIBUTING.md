# Contributing to Deskworks

Thanks for your interest. Deskworks aims to stay **small, legible, and local-first** —
roughly 1k lines, no heavy framework, every design decision documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Dev setup

```bash
git clone https://github.com/Jatin-Rawtani/deskworks && cd deskworks
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install pytest
pytest tests/ -q
```

## Running it against a real corpus

```bash
deskworks init                 # writes deskworks.toml
# edit [corpus].paths and [llm], then:
deskworks index && deskworks web
```

## Guidelines

- **Keep it dependency-light.** Heavy imports (torch, sentence-transformers,
  flask) must stay *lazy* — imported inside the function that needs them, never at
  module top level. This keeps the CLI fast and the unit tests runnable with just
  `numpy + pytest`.
- **Pure logic gets a unit test.** Retrieval math (`rrf_fuse`, `dedup_by_key`),
  chunking, config merge, and parsing are pure functions — add/extend tests in
  `tests/` for any change to them.
- **No network in unit tests.** Anything touching a model endpoint or the
  embedding model is integration territory; don't put it in the default suite.
- **Privacy first.** Never commit a real corpus, index, cache, or a populated
  `deskworks.toml` — they're git-ignored for a reason.

## Ideas / roadmap

- Incremental re-index (only changed files)
- FAISS / hnswlib backend for very large corpora (swap point: `core.load_index`)
- A `/search` JSON API endpoint
- Optional reranker stage (cross-encoder) behind a config flag

Open an issue before large changes so we can keep the surface area small.
