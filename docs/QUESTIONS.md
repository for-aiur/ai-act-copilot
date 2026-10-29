# Question bank

The engine ships ten reviewed question options in
[`questions.json`](../engine/src/aiact/data/questions.json). The bank version is
1.0. Each record has a stable ID, question text, topic, missing-fact tag and an
optional legal section ID:

```json
{
  "id": "chatbot_notice",
  "question": "Where are customers told they are interacting with AI before the first reply?",
  "topic": "chatbot",
  "asks_about": "ai_interaction_notice",
  "legal_source": "article-50-1"
}
```

Edit or add records in this file instead of changing Python question strings.
Drafts can be written by a person or prepared offline with a stronger model;
check their relevance and wording before adding them. No generator runs during
a scan, and a generated draft is not automatically approved.

The current pipeline picks the legal domain and gives that domain's questions
to the local model as allowed options for the initial review. A null
legal_source marks a general question for unknown use cases. References must
match a section in the loaded corpus. Duplicate IDs, invalid data, missing files
or a domain with no questions produce an operational error.

topic and asks_about are editorial metadata today. They do not automatically
detect answered facts or suppress questions. With explicit user context, the
existing follow-up path can still generate a question outside the initial bank.
Initial titles/explanations remain pipeline templates.

An editable engine install reads this source file on the next scan. A wheel
contains its own copy, so distribute edits by rebuilding/reinstalling the engine.
This bank moves content out of code; it does not add legal coverage or establish
generalization to unseen domains. The public ScanResult format is unchanged.
