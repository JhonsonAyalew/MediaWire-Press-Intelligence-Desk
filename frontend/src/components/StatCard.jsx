import "./StatCard.css";

export default function StatCard({ label, value, hint, accent }) {
  return (
    <div className="stat-card">
      <p className="eyebrow">{label}</p>
      <p className="stat-card__value mono" style={accent ? { color: accent } : undefined}>
        {value}
      </p>
      {hint && <p className="stat-card__hint">{hint}</p>}
    </div>
  );
}
