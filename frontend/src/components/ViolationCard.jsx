import { format } from "date-fns";
import { AlertTriangle, Camera } from "lucide-react";

const VIOLATION_LABELS = {
  helmet_violation:    { label: "Helmet",         badge: "badge-danger"  },
  triple_riding:       { label: "Triple Riding",   badge: "badge-warning" },
  seatbelt_violation:  { label: "Seatbelt",        badge: "badge-warning" },
  wrong_side_driving:  { label: "Wrong Side",      badge: "badge-danger"  },
  stop_line_violation: { label: "Stop Line",       badge: "badge-info"    },
  red_light_violation: { label: "Red Light",       badge: "badge-danger"  },
  illegal_parking:     { label: "Parking",         badge: "badge-muted"   },
};

export default function ViolationCard({ violation, onClick }) {
  const meta = VIOLATION_LABELS[violation.violation_type] || {
    label: violation.violation_type, badge: "badge-muted",
  };

  const date = violation.detected_at
    ? format(new Date(violation.detected_at), "dd MMM yyyy, HH:mm")
    : "—";

  return (
    <div
      className="card fade-in"
      style={{ cursor: "pointer", padding: 16 }}
      onClick={() => onClick?.(violation)}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        {/* Thumbnail */}
        <div
          style={{
            width: 90, height: 68,
            borderRadius: 8,
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            overflow: "hidden",
            flexShrink: 0,
          }}
        >
          {violation.evidence_thumbnail ? (
            <img
              src={`data:image/jpeg;base64,${violation.evidence_thumbnail}`}
              alt="evidence"
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          ) : (
            <div style={{
              width: "100%", height: "100%",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--text-muted)",
            }}>
              <AlertTriangle size={24} />
            </div>
          )}
        </div>

        {/* Details */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
            <span className={`badge ${meta.badge}`}>{meta.label}</span>
            {violation.plate_number && (
              <span style={{
                fontFamily: "JetBrains Mono, monospace",
                fontSize: 12,
                background: "rgba(99,102,241,0.15)",
                color: "var(--accent-light)",
                padding: "2px 10px",
                borderRadius: 100,
                border: "1px solid var(--border)",
              }}>
                {violation.plate_number}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>
            <strong>{violation.vehicle_type || "Vehicle"}</strong> ·{" "}
            {(violation.confidence * 100).toFixed(0)}% confidence
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", gap: 12 }}>
            <span>📅 {date}</span>
            {violation.location && <span>📍 {violation.location}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
