"""Configuration loader for LocalMind.

Resolution order:
  1. $LOCALMIND_CONFIG if set
  2. ./localmind.toml in the current directory
  3. ~/.localmind/localmind.toml
Falls back to built-in defaults so `localmind` runs even with no config
(it just won't have any corpus paths until you set them).
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # py3.10
    import tomli as tomllib  # type: ignore

DEFAULTS = {
    "corpus": {
        "paths": [],
        "include_ext": [".pdf", ".md", ".markdown", ".txt"],
        "exclude_substrings": ["/.git/", "node_modules"],
    },
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key": "",
        "max_tokens": 800,
        "temperature": 0.2,
        "disable_thinking": False,
    },
    "embed": {
        "model": "BAAI/bge-base-en-v1.5",
        "device": "cpu",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
    },
    "index": {
        "dir": "~/.localmind/index",
        "cache": "~/.localmind/pdf_cache",
        "chunk_chars": 1100,
        "chunk_overlap": 180,
        "top_k": 10,
        "rrf_k": 60,
        "max_chunks_per_doc": 2,
        "pdf_max_chars": 90000,
    },
    "web": {"host": "127.0.0.1", "port": 5007, "title": "LocalMind"},
    "summarize": {
        "out_dir": "~/.localmind/summaries",
        "taxonomy_hint": "THEMES: <3-5 comma-separated topical tags>",
    },
}


def _expand(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _find_config() -> Path | None:
    env = os.environ.get("LOCALMIND_CONFIG")
    if env and Path(_expand(env)).is_file():
        return Path(_expand(env))
    local = Path("localmind.toml")
    if local.is_file():
        return local
    home = Path(_expand("~/.localmind/localmind.toml"))
    if home.is_file():
        return home
    return None


class Config:
    def __init__(self, data: dict, source: Path | None):
        self._d = data
        self.source = source

    # section accessors
    @property
    def corpus(self): return self._d["corpus"]
    @property
    def llm(self): return self._d["llm"]
    @property
    def embed(self): return self._d["embed"]
    @property
    def index(self): return self._d["index"]
    @property
    def web(self): return self._d["web"]
    @property
    def summarize(self): return self._d["summarize"]

    # resolved paths
    def corpus_paths(self) -> list[str]:
        return [_expand(p) for p in self.corpus.get("paths", [])]

    def index_dir(self) -> str: return _expand(self.index["dir"])
    def cache_dir(self) -> str: return _expand(self.index["cache"])
    def summaries_dir(self) -> str: return _expand(self.summarize["out_dir"])

    def emb_path(self) -> str: return os.path.join(self.index_dir(), "embeddings.npy")
    def meta_path(self) -> str: return os.path.join(self.index_dir(), "chunks.jsonl.gz")


def load(path: str | None = None) -> Config:
    cfg_path = Path(_expand(path)) if path else _find_config()
    data = dict(DEFAULTS)
    if cfg_path and cfg_path.is_file():
        with open(cfg_path, "rb") as f:
            user = tomllib.load(f)
        data = _deep_merge(DEFAULTS, user)
    # env override for embed device (used by the always-on service)
    if os.environ.get("LOCALMIND_EMBED_DEVICE"):
        data["embed"]["device"] = os.environ["LOCALMIND_EMBED_DEVICE"]
    return Config(data, cfg_path)
