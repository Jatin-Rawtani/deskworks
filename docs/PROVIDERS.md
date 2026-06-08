# Model providers

Deskworks talks to any **OpenAI-compatible** `/chat/completions` endpoint. Set
`[llm]` in your `deskworks.toml`. Embeddings always run locally (BGE via
sentence-transformers), so retrieval is offline regardless of the chat provider.

## Ollama (recommended default)

```bash
ollama pull qwen2.5:7b
```
```toml
[llm]
base_url = "http://localhost:11434/v1"
model    = "qwen2.5:7b"
api_key  = ""
```

## LM Studio

Start the local server (default port 1234), load a model, then:
```toml
[llm]
base_url = "http://localhost:1234/v1"
model    = "your-loaded-model-id"
api_key  = ""
```

## vLLM

```bash
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct
```
```toml
[llm]
base_url = "http://localhost:8000/v1"
model    = "Qwen/Qwen2.5-7B-Instruct"
```

## Rapid-MLX (Apple Silicon)

```bash
rapid-mlx serve qwen2.5-7b --gpu-memory-utilization 0.75
```
```toml
[llm]
base_url = "http://localhost:8000/v1"
model    = "qwen2.5-7b"
disable_thinking = true   # if using a Qwen3 reasoning model
```

## OpenAI / OpenRouter (hosted — not offline)

```toml
[llm]
base_url = "https://api.openai.com/v1"     # or https://openrouter.ai/api/v1
model    = "gpt-4o-mini"
api_key  = "sk-..."
```

> Anthropic's API is **not** OpenAI-compatible natively. To use Claude, run an
> OpenAI-compatible proxy (e.g. LiteLLM) and point `base_url` at the proxy.

## Embedding model

```toml
[embed]
model        = "BAAI/bge-base-en-v1.5"   # default; strong + small (768-dim)
device       = "cpu"                      # cpu | mps (Apple) | cuda
query_prefix = "Represent this sentence for searching relevant passages: "
```

- Use `device = "mps"` on Apple Silicon or `"cuda"` on NVIDIA for a faster index
  build. Serving stays light on CPU by default.
- Swapping models: `bge-large-en-v1.5` (better, slower) keeps the same prefix.
  For the `e5` family use `query_prefix = "query: "`. For models that need no
  instruction, set `query_prefix = ""`.

## The `disable_thinking` flag

Some reasoning models (e.g. Qwen3) emit `<think>…</think>` blocks. Setting
`disable_thinking = true` sends `chat_template_kwargs.enable_thinking = false`,
which those servers honor; other servers ignore it harmlessly. Deskworks also
strips any `<think>` blocks from output as a safety net.
