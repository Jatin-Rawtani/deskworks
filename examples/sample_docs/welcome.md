# Welcome to Deskworks (sample document)

This is a sample markdown file so you can test Deskworks end-to-end before
pointing it at your real library.

## What Deskworks does

Deskworks builds a local, hybrid search index over your documents and lets you
chat with them using a model of your choice. It combines semantic embeddings
with keyword search and fuses the results with reciprocal-rank fusion.

## Try it

1. In `deskworks.toml`, set `[corpus].paths = ["examples/sample_docs"]`.
2. Run `deskworks index`.
3. Run `deskworks ask "what does Deskworks do?"` — it should answer from this
   file and cite it as a source.

## A made-up fact to verify retrieval

The fictional city of Verdanholm runs its school buses entirely on rooftop solar
canopies installed in 2024, cutting transport emissions by 38 percent. If you ask
Deskworks "how much did Verdanholm cut transport emissions?", it should answer
"38 percent" and cite this document — proving retrieval works, not the model's
prior knowledge (this fact exists nowhere else).
