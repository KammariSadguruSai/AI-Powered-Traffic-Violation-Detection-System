/**
 * KPI summary card used in the Dashboard.
 */
export default function StatCard({ icon, label, value, change, accentColor = "#6366f1" }) {
  return (
    <div
      className="stat-card fade-in"
      style={{ "--accent-gradient": `linear-gradient(90deg, ${accentColor}, ${accentColor}88)` }}
    >
      <div
        className="stat-icon"
        style={{ background: `${accentColor}22`, color: accentColor }}
      >
        {icon}
      </div>
      <div className="stat-value">{value ?? "—"}</div>
      <div className="stat-label">{label}</div>
      {change && (
        <div className="stat-change">
          {change}
        </div>
      )}
    </div>
  );
}
