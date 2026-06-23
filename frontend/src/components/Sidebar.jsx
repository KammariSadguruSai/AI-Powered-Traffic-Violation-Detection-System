import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Upload, AlertTriangle, BarChart3,
  Camera, Shield, Activity
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/",          icon: LayoutDashboard, label: "Dashboard"  },
  { to: "/upload",    icon: Upload,          label: "Upload Image"},
  { to: "/violations",icon: AlertTriangle,   label: "Violations" },
  { to: "/reports",   icon: BarChart3,       label: "Reports"    },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🚦</div>
        <div>
          <div className="sidebar-logo-text">TrafficAI</div>
          <div className="sidebar-logo-sub">Violation Detection</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Navigation</div>
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `nav-link${isActive ? " active" : ""}`
            }
          >
            <Icon className="nav-link-icon" size={18} />
            {label}
          </NavLink>
        ))}

        <div className="sidebar-section-label" style={{ marginTop: 20 }}>System</div>
        <NavLink
          to="/live"
          className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
        >
          <Activity size={18} className="nav-link-icon" />
          <span>Live Monitor</span>
          <span
            style={{
              marginLeft: "auto",
              fontSize: 10,
              background: "rgba(16,185,129,0.2)",
              color: "#6ee7b7",
              padding: "2px 8px",
              borderRadius: 100,
              border: "1px solid rgba(16,185,129,0.3)",
            }}
          >
            LIVE
          </span>
        </NavLink>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <div className="pulse-dot" />
          <span>System Online</span>
        </div>
        <div style={{ color: "var(--text-muted)", fontSize: 11 }}>
          AI Core v1.0 · YOLOv8
        </div>
      </div>
    </aside>
  );
}
