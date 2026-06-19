import { useEffect, useState } from "react";
import { api } from "../api.js";
import PageHeader from "../components/PageHeader.jsx";
import "./ScrapeDesk.css";

const LEVEL_COLOR = {
  info: "var(--text-on-ink-dim)",
  progress: "var(--amber)",
  success: "var(--wire-green)",
  error: "var(--rust)",
  warning: "var(--amber)",
  debug: "var(--text-on-ink-dim)",
};

export default function ScrapeDesk() {
  const [sites, setSites] = useState([]);
  const [selected, setSelected] = useState(null);
  const [categoryUrl, setCategoryUrl] = useState("");
  const [maxPages, setMaxPages] = useState(1);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.sites().then(({ data }) => {
      setSites(data);
      setSelected(data[0]?.key);
      setCategoryUrl(data[0]?.default_url || "");
    }).catch((e) => setError(e.message));
    refreshJobs();
  }, []);

  function refreshJobs() {
    api.jobs(10).then(({ data }) => setJobs(data)).catch(() => {});
  }

  useEffect(() => {
    if (!activeJobId) return;
    const t = setInterval(async () => {
      try {
        const { data } = await api.job(activeJobId);
        setActiveJob(data);
        if (data.status !== "running" && data.status !== "queued") {
          clearInterval(t);
          refreshJobs();
        }
      } catch {
        clearInterval(t);
      }
    }, 1500);
    return () => clearInterval(t);
  }, [activeJobId]);

  function pickSite(key) {
    setSelected(key);
    const site = sites.find((s) => s.key === key);
    setCategoryUrl(site?.default_url || "");
  }

  async function launch() {
    setError("");
    try {
      const { data } = await api.startScrape({
        site: selected, category_url: categoryUrl, max_pages: Number(maxPages),
      });
      setActiveJobId(data.job_id);
      setActiveJob(null);
      refreshJobs();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Scrape Desk"
        title="Run a Scrape Job"
        description="Pick a wire source, point it at a category page, and watch the transmission land in real time."
      />

      <div className="site-grid">
        {sites.map((s) => (
          <button
            key={s.key}
            className={`site-card${selected === s.key ? " is-selected" : ""}`}
            onClick={() => pickSite(s.key)}
          >
            <span className="site-card__label mono">{s.label}</span>
            <span className="site-card__url">{s.default_url}</span>
          </button>
        ))}
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="form-row">
          <label className="field" style={{ flex: 2 }}>
            <span className="eyebrow">Category / section URL</span>
            <input value={categoryUrl} onChange={(e) => setCategoryUrl(e.target.value)} />
          </label>
          <label className="field" style={{ flex: 0.4 }}>
            <span className="eyebrow">Pages</span>
            <input type="number" min={1} max={10} value={maxPages} onChange={(e) => setMaxPages(e.target.value)} />
          </label>
          <button className="btn-primary" style={{ alignSelf: "flex-end" }} onClick={launch}>
            Launch scrape
          </button>
        </div>
        {error && <p className="modal__error">{error}</p>}
      </div>

      {activeJob && (
        <div className="terminal">
          <div className="terminal__bar">
            <span className="mono">job #{activeJob.id} · {activeJob.site} · {activeJob.status}</span>
            <span className="mono">{activeJob.found_count} saved</span>
          </div>
          <div className="terminal__body">
            {activeJob.log.map((l, i) => (
              <div key={i} className="terminal__line" style={{ color: LEVEL_COLOR[l.level] || "inherit" }}>
                <span className="dim">{l.t.slice(11, 19)}</span> {l.msg}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel" style={{ marginTop: 18 }}>
        <p className="eyebrow">Job History</p>
        <table className="data-table" style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>ID</th><th>Site</th><th>Status</th><th>Found</th><th>Started</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id} onClick={() => setActiveJobId(j.id)} style={{ cursor: "pointer" }}>
                <td className="mono">#{j.id}</td>
                <td className="mono">{j.site}</td>
                <td>
                  <span style={{ color: LEVEL_COLOR[j.status === "completed" ? "success" : j.status === "failed" ? "error" : "progress"] }}>
                    {j.status}
                  </span>
                </td>
                <td>{j.found_count}</td>
                <td className="dim">{j.created_at?.slice(0, 19).replace("T", " ")}</td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={5} className="empty-row">No jobs yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="dim" style={{ fontSize: 12, marginTop: 14 }}>
        Note: outlets change their HTML often. If a job returns 0 authors, the site's markup
        likely shifted — the selectors live in <span className="mono">backend/scrapers/</span> and are easy to update.
      </p>
    </div>
  );
}
