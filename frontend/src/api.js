const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5050";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.success === false) {
    throw new Error(json.error || `Request failed: ${res.status}`);
  }
  return json;
}

export const api = {
  health: () => request("/api/health"),
  sites: () => request("/api/sites"),
  stats: () => request("/api/stats"),

  authors: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return request(`/api/authors${q ? `?${q}` : ""}`);
  },
  author: (id) => request(`/api/authors/${id}`),
  exportUrl: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return `${BASE_URL}/api/authors/export${q ? `?${q}` : ""}`;
  },
  importExisting: (dir) =>
    request("/api/import-existing", { method: "POST", body: JSON.stringify({ dir }) }),

  startScrape: (payload) =>
    request("/api/scrape", { method: "POST", body: JSON.stringify(payload) }),
  jobs: (limit = 30) => request(`/api/jobs?limit=${limit}`),
  job: (id) => request(`/api/jobs/${id}`),

  draftEmail: (payload) =>
    request("/api/ai/draft-email", { method: "POST", body: JSON.stringify(payload) }),
  scoreAuthor: (payload) =>
    request("/api/ai/score", { method: "POST", body: JSON.stringify(payload) }),
  scoreBulk: (payload) =>
    request("/api/ai/score-bulk", { method: "POST", body: JSON.stringify(payload) }),
  chat: (payload) =>
    request("/api/ai/chat", { method: "POST", body: JSON.stringify(payload) }),
};
