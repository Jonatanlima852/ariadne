async function request(path, params = {}) {
  const response = await fetch(`${path}?${new URLSearchParams(params)}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `A API respondeu ${response.status}.`,
    );
  }
  return response.json();
}
export const inspectorApi = {
  catalog: (params) => request("/api/catalog", params),
  evidence: (source, identifier) =>
    request("/api/evidence", { source, identifier }),
};
