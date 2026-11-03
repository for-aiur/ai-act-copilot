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
