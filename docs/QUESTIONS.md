# Question bank

The engine ships **164 authored questions** in
[questions.json](../engine/src/aiact/data/questions.json), bank format 1.1.
All 114 stored passages have at least one evidence-oriented question.
[Read the full catalogue](QUESTION-CATALOG.md).

Questions challenge a concrete decision and ask for inspectable evidence:

- Training: reproduce a dataset, trace label corrections and check holdout leakage.
- Parameters: compare rejected configurations and justify measured trade-offs.
- Oversight: demonstrate that a reviewer can challenge, stop or reverse an output.
- Data: inspect missingness, group representation and bias-test results.
- Sensitive bias-audit data: justify necessity, access restrictions and deletion.

Each detailed question records its legal source, topic, missing-fact tag,
`applies_when` scenario and `evidence_expected` artifact. The model receives these
fields with the retrieved passages. Detailed questions are offered first;
context questions remain available when the intended use is still unknown.
Seven institutional passages have maintenance-only questions. They address
source/guidance changes and are excluded from developer scan options.

A scan still retrieves at most six passages and returns at most four distinct
findings. Each passage contributes at most four detailed and two context options;
unknown use cases can also receive two general questions. The full bank is not
sent to the model. Editorial order currently chooses detailed options within a
passage; it is not semantic question ranking or automatic answered-fact detection.

Selected questions must come from the offered bank and match their cited passage.
Duplicate missing-fact topics and invented quotations are rejected independently.
Applicability hints guide selection; they do not establish a legal duty or prove
that the developer has supplied adequate evidence. Citation validity alone does
not establish semantic legal support. Questions are editorial content, without
independent legal review; live model question selection still needs evaluation.

Edit the JSON to change questions. New `depth: evidence` records need a specific
condition and expected artifact, an explicit audience and a question under 251
characters. Stable IDs support review history. Do not turn an unknown safeguard
into an accusation, ask the user to certify compliance, or treat Article 4a's
exceptional bias-audit processing as a general personal-data erasure rule.

People or an offline model can prepare drafts; review them before adding them.
No question generator runs during a scan. An editable engine reads changes on
the next scan; a wheel needs rebuilding. This follow-up needs engine 0.3.2; the
0.3.0 extension remains compatible. Result fields and finding limits are unchanged.
