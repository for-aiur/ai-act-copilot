# Reviewed demo corpus

The single packaged corpus and manifest lives in
`engine/src/aiact/data/corpus.json`. It includes six reviewed passages, source
URLs, source HTML and passage checksums, retrieval date, source identity, selected
exact supporting quotations, and explicit scope limits. Scans read it locally.

Sources are the European Commission's AI Act Service Desk reproductions:

- [Annex III](https://ai-act-service-desk.ec.europa.eu/en/ai-act/annex-3)
- [Article 6](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-6)
- [Article 50](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50)

Retrieved 29 October 2026. The article pages identify their basis as the EUR-Lex
consolidation as at 27 July 2026. EUR-Lex itself returned a bot challenge/empty
response during setup, so this is explicitly a Commission reproduction rather
than an independently verified EUR-Lex download. Summaries and guidance are
excluded. No applicability dates are encoded or inferred.

`aiact update` downloads only these official pages, verifies that every reviewed
passage still occurs there, and atomically writes a single user cache file. A
changed passage or failed download preserves the existing file and requires
manual legal review. Refresh does not discover or silently import new law.

The reproduction script `scripts/build_reviewed_corpus.py` expects explicitly
downloaded official HTML in `/tmp/ai-act-{annex3,article6,article50}.html`. It
asserts paragraph matches and supporting quotation membership before writing.

This subset does not cover all AI Act provisions, prohibitions, exceptions,
definitions, related legislation, actor roles, or applicability dates. Its
citations identify engineering review questions; they do not certify compliance.
