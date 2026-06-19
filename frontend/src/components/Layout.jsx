import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api.js";
import "./Layout.css";

const NAV = [
  { to: "/", label: "Dashboard", num: "01" },
  { to: "/database", label: "Database", num: "02" },
  { to: "/scrape", label: "Scrape Desk", num: "03" },
  { to: "/assistant", label: "AI Assistant", num: "04" },
];

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function Ticker() {
  const [lines, setLines] = useState(["Wire room idle — start a scrape job to see live transmission."]);

  useEffect(() => {
    let mounted = true;
    async function poll() {
      try {
        const { data: jobs } = await api.jobs(5);
        const active = jobs.filter((j) => j.status === "running");
        const target = active.length ? active : jobs.slice(0, 2);
        const detailed = await Promise.all(target.map((j) => api.job(j.id)));
        const collected = [];
        detailed.forEach(({ data: job }) => {
          job.log.slice(-4).forEach((l) =>
            collected.push(`[${job.site.toUpperCase()}] ${l.msg}`)
          );
        });
        if (mounted && collected.length) setLines(collected);
      } catch {
        /* backend not reachable yet — keep idle message */
      }
    }
    poll();
    const t = setInterval(poll, 4000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, []);

  const feed = lines.join("   ◆   ");

  return (
    <div className="ticker">
      <span className="ticker__tag">ON THE WIRE</span>
      <div className="ticker__track">
        <span className="ticker__feed">{feed}</span>
        <span className="ticker__feed" aria-hidden="true">{feed}</span>
      </div>
    </div>
  );
}

export default function Layout({ children }) {
  const now = useClock();
  const dateline = now
    .toUTCString()
    .replace(" GMT", " UTC");

  return (
    <div className="shell">
      <header className="masthead">
        <div className="masthead__brand">
          <span className="masthead__mark">MW</span>
          <div>
            <div className="masthead__title">MediaWire</div>
            <div className="masthead__sub eyebrow">Press Intelligence Desk</div>
          </div>
        </div>
        <div className="masthead__dateline mono">{dateline}</div>
      </header>

      <Ticker />

      <div className="body">
        <nav className="sidebar">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `sidebar__item${isActive ? " is-active" : ""}`}
            >
              <span className="sidebar__num mono">{item.num}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
          <hr className="hairline" style={{ margin: "16px 18px" }} />
          <div className="sidebar__note">
            <p className="eyebrow">Status</p>
            <p>Connects to your local Flask API and the Anthropic API for AI features.</p>
          </div>
        </nav>

        <main className="content">{children}</main>
      </div>
    </div>
  );
}
