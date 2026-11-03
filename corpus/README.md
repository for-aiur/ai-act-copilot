# Official source packs

The M1 corpus comes from the Publications Office of the European Union:

- Consolidation: CELEX `02024R1689-20260727`.
- Authentic original act: `32024R1689`.
- Authentic 2026 amendment: `32026R1744`.

Pinned raw XHTML, canonical URLs, retrieval date and SHA256 values live in
`engine/src/aiact/data/official/`. The deterministic normalized pack is
`engine/src/aiact/data/full-act.json.gz`. It contains 119 articles, 14 annexes,
180 original recitals and 47 amendment recitals, with exact normalized text and
paragraph/block offsets. Recital origins remain distinct. Consolidated text is
informational; the original Official Journal acts are the authentic instruments.

Rebuild without network:

```sh
uv run --project engine python -m aiact.rag.official --output /tmp/full-act.json.gz
```

`uv run --project engine python scripts/fetch-official.py --output NEW_EMPTY_DIRECTORY` explicitly redownloads
and verifies the pinned raw files. `aiact corpus check` discovers official versions;
`aiact corpus sync --staging` rechecks without activating. Source changes require
review. See [workbench operations](../docs/WORKBENCH.md).

`engine/src/aiact/data/corpus.json` is the **legacy 114-passage subset**, retained
for existing CLI/editor/Actions adapters and regression fixtures. Its matching
question bank and `aiact update` re-verification flow remain separate from M1
full-corpus indexing. They do not discover or activate new consolidated editions.
