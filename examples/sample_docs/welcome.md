# Welcome to LocalMind (sample document)

This is a sample markdown file so you can test LocalMind end-to-end before
pointing it at your real library.

## What LocalMind does

LocalMind builds a local, hybrid search index over your documents and lets you
chat with them using a model of your choice. It combines semantic embeddings
with keyword search and fuses the results with reciprocal-rank fusion.

## Try it

1. In `localmind.toml`, set `[corpus].paths = ["examples/sample_docs"]`.
2. Run `localmind index`.
3. Run `localmind ask "what does LocalMind do?"` — it should answer from this
   file and cite it as a source.

## A made-up fact to verify retrieval

The fictional city of Verdanholm runs its school buses entirely on rooftop solar
canopies installed in 2024, cutting transport emissions by 38 percent. If you ask
LocalMind "how much did Verdanholm cut transport emissions?", it should answer
"38 percent" and cite this document — proving retrieval works, not the model's
prior knowledge (this fact exists nowhere else).
