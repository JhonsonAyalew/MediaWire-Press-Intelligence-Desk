import "./ScoreBadge.css";

export default function ScoreBadge({ score }) {
  if (score === null || score === undefined) {
    return <span className="score-badge score-badge--none mono">—</span>;
  }
  const level = score >= 4 ? "high" : score >= 3 ? "mid" : "low";
  return <span className={`score-badge score-badge--${level} mono`}>{score}/5</span>;
}
