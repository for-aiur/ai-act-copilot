export type Section = {
  id: string;
  title: string;
  text: string;
  url: string;
  checksum: string;
  text_kind: string;
  applicability_date: string | null;
};
export type Corpus = {
  domain: string;
  coverage: string;
  version: string;
  checksum: string;
  source_identity: string;
  verified_at: string;
  scope_limits: string[];
  total: number;
  source_count: number;
  sections: Section[];
};
export type DraftInput = {
  title: string;
  scenario: string;
  context: string;
  source_ids: string[];
  corpus_checksum: string;
};
export type Draft = DraftInput & {
  id: string;
  created_at: string;
  status: "draft";
  corpus_version: string;
};

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message =
      "The local API is unavailable. Check the Python service and retry.";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (response.status === 422)
        message = "Check the scenario fields and source references.";
    } catch {
      /* Proxy errors may be plain text. */
    }
    throw new Error(message);
  }
  return response.json();
}
