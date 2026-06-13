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


def test_model_profiles_merge_and_fallback(tmp_path):
    cfg = tmp_path / "deskworks.toml"
    cfg.write_text(
        '[llm]\nmodel = "base-model"\nmax_tokens = 800\n'
        '[llm.profiles.smart]\nmodel = "big-model"\nmax_tokens = 1200\n'
        '[llm.profiles.fast]\nmodel = "small-model"\n'
    )
    c = config.load(str(cfg))
    assert sorted(c.profiles().keys()) == ["fast", "smart"]
    # profile overrides apply on top of [llm]
    smart = c.with_profile("smart")
    assert smart.llm["model"] == "big-model"
    assert smart.llm["max_tokens"] == 1200
    # keys the profile doesn't set fall through to [llm]
    fast = c.with_profile("fast")
    assert fast.llm["model"] == "small-model"
    assert fast.llm["max_tokens"] == 800
    # unknown / empty profile -> unchanged config
    assert c.with_profile("nope") is c
    assert c.with_profile(None) is c
    # original config is not mutated
    assert c.llm["model"] == "base-model"
