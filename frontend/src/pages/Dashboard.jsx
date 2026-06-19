import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { api } from "../api.js";
import PageHeader from "../components/PageHeader.jsx";
import StatCard from "../components/StatCard.jsx";
import "./Dashboard.css";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const { data } = await api.stats();
      setStats(data);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  if (error) {
    return (
      <div>
        <PageHeader eyebrow="Desk Overview" title="Dashboard" />
        <div className="empty-panel">
          Can't reach the API at the configured URL. Start the Flask backend
          (<code className="mono">python app.py</code>) and refresh. ({error})
        </div>
      </div>
    );
  }

  if (!stats) return <div className="eyebrow">Loading desk overview…</div>;

  const outletData = stats.by_outlet.map((o) => ({ name: o.outlet || "Unlabeled", count: o.c }));
  const emailRate = stats.total ? Math.round((stats.with_email / stats.total) * 100) : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Desk Overview"
        title="Dashboard"
        description="A live read on every journalist contact your scrapers have filed, and how reachable that list actually is."
      />

      <div className="stat-grid">
        <StatCard label="Total Contacts" value={stats.total} hint="Authors across all outlets" />
        <StatCard label="With Email" value={`${stats.with_email}`} hint={`${emailRate}% reachable by email`} accent="var(--wire-green)" />
        <StatCard label="With Social" value={stats.with_social} hint="Twitter / LinkedIn on file" />
        <StatCard label="Outlets Covered" value={stats.by_outlet.length} hint="Distinct publications" />
      </div>

      <div className="dash-grid">
        <div className="panel">
          <p className="eyebrow">Contacts by Outlet</p>
          <div style={{ height: 260, marginTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={outletData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="var(--ink-line)" horizontal={false} />
                <XAxis type="number" stroke="var(--text-on-ink-dim)" fontSize={11} />
                <YAxis
                  dataKey="name" type="category" stroke="var(--text-on-ink-dim)"
                  fontSize={12} width={110}
                />
                <Tooltip
                  contentStyle={{ background: "var(--paper)", border: "1px solid var(--paper-line)", borderRadius: 3 }}
                  labelStyle={{ color: "var(--text-on-paper)", fontWeight: 600 }}
                />
                <Bar dataKey="count" fill="var(--amber)" radius={[0, 2, 2, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <p className="eyebrow">Recently Filed</p>
          <ul className="wire-list">
            {stats.recent.length === 0 && (
              <li className="wire-list__empty">No contacts filed yet — run a scrape job from the Scrape Desk.</li>
            )}
            {stats.recent.map((r, i) => (
              <li key={i} className="wire-list__item">
                <span className="wire-list__dot" />
                <span className="wire-list__name">{r.name}</span>
                <span className="wire-list__outlet mono">{r.outlet}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {stats.by_beat.length > 0 && (
        <div className="panel" style={{ marginTop: 18 }}>
          <p className="eyebrow">Top AI-Tagged Beats</p>
          <div className="beat-row">
            {stats.by_beat.map((b, i) => (
              <span key={i} className="beat-chip mono">
                {b.beat} <span className="beat-chip__count">{b.c}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
