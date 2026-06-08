import os
from deskworks import config


def test_defaults_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)               # no localmind/deskworks.toml present
    monkeypatch.delenv("DESKWORKS_CONFIG", raising=False)
    c = config.load()
    assert c.llm["model"]
    assert c.index["rrf_k"] == 60
    assert c.index["top_k"] == 10
    assert c.embed["model"].startswith("BAAI/")


def test_user_toml_overrides_and_merges(tmp_path, monkeypatch):
    cfg = tmp_path / "deskworks.toml"
    cfg.write_text(
        '[llm]\nmodel = "my-model"\nbase_url = "http://localhost:9/v1"\n'
        '[corpus]\npaths = ["~/x"]\n'
    )
    c = config.load(str(cfg))
    # overridden
    assert c.llm["model"] == "my-model"
    # untouched default still present (deep merge, not replace)
    assert c.llm["max_tokens"] == 800
    assert c.index["rrf_k"] == 60


def test_path_expansion(tmp_path, monkeypatch):
    cfg = tmp_path / "deskworks.toml"
    cfg.write_text('[corpus]\npaths = ["~/docs"]\n')
    c = config.load(str(cfg))
    expanded = c.corpus_paths()[0]
    assert expanded == os.path.expanduser("~/docs")
    assert "~" not in expanded


def test_env_overrides_embed_device(tmp_path, monkeypatch):
    cfg = tmp_path / "deskworks.toml"
    cfg.write_text('[embed]\ndevice = "cpu"\n')
    monkeypatch.setenv("DESKWORKS_EMBED_DEVICE", "mps")
    c = config.load(str(cfg))
    assert c.embed["device"] == "mps"
