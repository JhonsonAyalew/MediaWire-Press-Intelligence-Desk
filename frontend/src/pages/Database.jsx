import { useEffect, useState, useCallback } from "react";
import { api } from "../api.js";
import PageHeader from "../components/PageHeader.jsx";
import ScoreBadge from "../components/ScoreBadge.jsx";
import DraftModal from "../components/DraftModal.jsx";
import "./Database.css";

export default function Database() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [outlet, setOutlet] = useState("");
  const [hasEmail, setHasEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [draftAuthor, setDraftAuthor] = useState(null);
  const [scoringId, setScoringId] = useState(null);
  const [campaignContext, setCampaignContext] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { limit: 200 };
      if (search) params.search = search;
      if (outlet) params.outlet = outlet;
      if (hasEmail) params.has_email = hasEmail;
      const { data, total } = await api.authors(params);
      setRows(data);
      setTotal(total);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [search, outlet, hasEmail]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const outlets = [...new Set(rows.map((r) => r.outlet))].sort();

  async function scoreOne(author) {
    setScoringId(author.id);
    try {
      await api.scoreAuthor({ author_id: author.id, campaign_context: campaignContext });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setScoringId(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Press Database"
        title="Journalist Database"
        description="Every contact your scrapers have filed. Search, score relevance against a campaign, and draft a pitch in one move."
        action={
          <a className="btn-ghost" href={api.exportUrl({ search, outlet })}>
            Export CSV
          </a>
        }
      />

      <div className="filters">
        <input
          className="filters__search"
          placeholder="Search name, bio, beat…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={outlet} onChange={(e) => setOutlet(e.target.value)}>
          <option value="">All outlets</option>
          {outlets.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <select value={hasEmail} onChange={(e) => setHasEmail(e.target.value)}>
          <option value="">Any contact info</option>
          <option value="true">Has email</option>
          <option value="false">No email</option>
        </select>
        <input
          className="filters__campaign"
          placeholder="Campaign context for AI scoring (optional)…"
          value={campaignContext}
          onChange={(e) => setCampaignContext(e.target.value)}
        />
      </div>

      {error && <p className="modal__error" style={{ marginBottom: 10 }}>{error}</p>}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Journalist</th>
              <th>Outlet</th>
              <th>Beat</th>
              <th>Email</th>
              <th>Social</th>
              <th>Relevance</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <div className="author-cell">
                    <span className="author-cell__name">{r.name}</span>
                    {r.title && <span className="author-cell__title">{r.title}</span>}
                  </div>
                </td>
                <td className="mono">{r.outlet}</td>
                <td>{r.beat || "—"}</td>
                <td>
                  {r.email ? (
                    <a href={`mailto:${r.email}`} className="mono email-link">{r.email}</a>
                  ) : (
                    <span className="dim">none on file</span>
                  )}
                </td>
                <td>
                  <div className="social-icons">
                    {r.twitter && <a href={r.twitter} target="_blank" rel="noreferrer">X</a>}
                    {r.linkedin && <a href={r.linkedin} target="_blank" rel="noreferrer">in</a>}
                    {!r.twitter && !r.linkedin && <span className="dim">—</span>}
                  </div>
                </td>
                <td>
                  <button className="link-btn" onClick={() => scoreOne(r)} disabled={scoringId === r.id}>
                    <ScoreBadge score={r.relevance_score} />
                    {scoringId === r.id ? " scoring…" : " re-score"}
                  </button>
                </td>
                <td>
                  <button className="btn-ghost btn-ghost--sm" onClick={() => setDraftAuthor(r)}>
                    Draft email
                  </button>
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="empty-row">
                  No contacts match. Try clearing filters, or run a scrape job from the Scrape Desk.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="dim" style={{ marginTop: 10, fontSize: 12 }}>
        Showing {rows.length} of {total} contacts.
      </p>

      {draftAuthor && <DraftModal author={draftAuthor} onClose={() => setDraftAuthor(null)} />}
    </div>
  );
}
