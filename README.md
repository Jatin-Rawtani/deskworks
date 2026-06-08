# Deskworks

[![CI](https://github.com/Jatin-Rawtani/deskworks/actions/workflows/ci.yml/badge.svg)](https://github.com/Jatin-Rawtani/deskworks/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

**Your private, always-on AI over your own documents. 100% local. Zero API tokens.**

Point Deskworks at any folder of PDFs, notes, and markdown. It builds a hybrid
search index on your machine and gives you a streaming chat — with citations back
to your source files — answered by any model you choose. Nothing leaves your
computer except the prompt you send to your own (typically local) model.

```
ingest  →  summarize  →  index  →  ask / chat  →  dashboard
 PDFs       zero-token   BGE +     streaming +     searchable
 + md       summaries    BM25      sources         HTML library
            (local LLM)  + RRF
```

> Built by an applied-AI scientist who wanted a second brain over a 400-paper
> research library without sending a single page to a cloud API. Genericized from
> a system that runs as an always-on service over a real corpus.

---

## Why it's different

Most "chat with your docs" projects are framework demos. Deskworks is built to
*live on your machine and just run*:

- **Fully local retrieval.** Semantic embeddings (BGE) + keyword search (BM25)
  fused with **reciprocal-rank fusion**, then de-duplicated per document so one
  long file can't dominate the context.
- **Provider-agnostic generation.** Any OpenAI-compatible endpoint — Ollama,
  LM Studio, vLLM, Rapid-MLX, or a hosted API. One line of config.
- **Always-on.** Ships with macOS `launchd` and Linux `systemd` service files —
  autostart at login, self-restart, browser chat at `localhost:5007`.
- **Cite-or-refuse.** Answers cite the passages they used and say *"that isn't in
  your library yet"* rather than hallucinating.
- **Zero tokens for ingestion.** Bulk-summarize a whole folder and build a
  searchable dashboard using your local model — no API spend.
- **Your data stays yours.** Index, cache, and config are git-ignored by default.

---

## Quickstart

```bash
# 1. Install (Python 3.10+)
git clone https://github.com/Jatin-Rawtani/deskworks && cd deskworks
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. Have a local model running (example: Ollama)
ollama pull qwen2.5:7b      # or llama3.1:8b, mistral, etc.

# 3. Configure
deskworks init             # writes deskworks.toml
#   edit [corpus].paths  -> your folders
#   edit [llm]           -> your model endpoint (Ollama default already set)

# 4. Build + chat
deskworks ingest           # cache PDF text (skip if you only have md/txt)
deskworks index            # build the hybrid index
deskworks web              # open http://127.0.0.1:5007
```

CLI one-shots:

```bash
deskworks ask "what does my library say about X?"
deskworks summarize ~/papers my_papers     # -> ~/.deskworks/summaries/my_papers.{md,csv}
deskworks dashboard ~/.deskworks/summaries/my_papers.csv
deskworks status                            # config + index + model reachability
```

---

## Configuration

Everything lives in `deskworks.toml` (copy from `deskworks.toml.example`). The two
sections you must set:

```toml
[corpus]
paths = ["~/Documents/notes", "~/Documents/papers"]

[llm]
base_url = "http://localhost:11434/v1"   # Ollama
model    = "qwen2.5:7b"
api_key  = ""                            # blank for local; set for hosted APIs
```

See [`docs/PROVIDERS.md`](docs/PROVIDERS.md) for Ollama / LM Studio / vLLM /
Rapid-MLX / OpenAI configs, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for
how retrieval works.

---

## Always-on service

**macOS:** edit and install the launch agent —

```bash
cp service/com.deskworks.brain.plist.example ~/Library/LaunchAgents/com.deskworks.brain.plist
# edit the two REPLACE_ME paths, then:
launchctl load -w ~/Library/LaunchAgents/com.deskworks.brain.plist
```

**Linux:** see `service/deskworks.service.example` (systemd user service).

Both autostart at login and restart on crash. Your library is always one tab away.

---

## How retrieval works (short version)

1. Documents are chunked (~1100 chars, 180 overlap).
2. Each chunk is embedded once with **BGE** (`bge-base-en-v1.5`, 768-dim) and
   indexed for **BM25** keyword search.
3. A query is scored both ways; the two rankings are merged with
   **reciprocal-rank fusion** (`1/(k+rank)`, k=60).
4. Results are capped at N chunks per document for diversity.
5. The top passages are sent to your model with a cite-or-refuse prompt and the
   last few conversation turns for follow-ups.

Standard techniques, carefully assembled and productionized. Full detail in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Development

```bash
pip install -e . && pip install pytest
pytest tests/ -q          # 18 fast unit tests, no network/model needed
```

Retrieval math (`rrf_fuse`, `dedup_by_key`), chunking, config merge, and parsing
are pure functions with unit tests. Heavy deps are lazy-imported so the suite runs
on `numpy + pytest` alone. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Privacy

Deskworks never uploads your documents. The only outbound request is the chat
completion to the `base_url` you configure — set that to a local server (Ollama,
LM Studio, vLLM, Rapid-MLX) and the system is fully offline after the one-time
embedding-model download. Index, PDF cache, summaries, and your `deskworks.toml`
are git-ignored so you can't accidentally commit private content.

## License

MIT — see [LICENSE](LICENSE).
