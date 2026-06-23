import { useState, useEffect } from "react";
import { analyticsApi } from "../api/client";
import StatCard from "../components/StatCard";
import { ViolationPieChart, TrendLineChart } from "../components/Charts";
import ViolationCard from "../components/ViolationCard";
import { violationsApi } from "../api/client";
import {
  AlertTriangle, CheckCircle2, Clock, Camera,
  Car, CreditCard, TrendingUp, Activity,
} from "lucide-react";

export default function Dashboard() {
  const [summary, setSummary]   = useState(null);
  const [byType,  setByType]    = useState([]);
  const [trends,  setTrends]    = useState([]);
  const [recent,  setRecent]    = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error,   setError]     = useState(null);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30_000); // refresh every 30s
    return () => clearInterval(interval);
  }, []);

  async function fetchAll() {
    try {
      const [sumRes, typeRes, trendRes, recentRes] = await Promise.all([
        analyticsApi.summary(),
        analyticsApi.byType(),
        analyticsApi.trends({ period: "daily", days: 30 }),
        violationsApi.list({ page: 1, size: 8 }),
      ]);
      setSummary(sumRes.data);
      setByType(typeRes.data);
      setTrends(trendRes.data.data);
      setRecent(recentRes.data.items);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      {/* Header */}
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">Analytics Dashboard</h1>
          <p className="page-subtitle">Real-time traffic violation monitoring</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div className="pulse-dot" />
          <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Live</span>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger fade-in" style={{ marginBottom: 20 }}>
          <AlertTriangle size={16} />
          <span>Backend connection error: {error}. Start the FastAPI server.</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="stat-grid">
        <StatCard
          icon={<AlertTriangle size={22} />}
          label="Total Violations"
          value={loading ? "…" : summary?.total_violations?.toLocaleString()}
          accentColor="#ef4444"
        />
        <StatCard
          icon={<Activity size={22} />}
          label="Today"
          value={loading ? "…" : summary?.today_violations?.toLocaleString()}
          accentColor="#f59e0b"
          change="↑ Updated live"
        />
        <StatCard
          icon={<Clock size={22} />}
          label="Pending Review"
          value={loading ? "…" : summary?.pending_violations?.toLocaleString()}
          accentColor="#6366f1"
        />
        <StatCard
          icon={<CheckCircle2 size={22} />}
          label="Resolved"
          value={loading ? "…" : summary?.resolved_violations?.toLocaleString()}
          accentColor="#10b981"
        />
        <StatCard
          icon={<CreditCard size={22} />}
          label="Unique Plates"
          value={loading ? "…" : summary?.unique_plates?.toLocaleString()}
          accentColor="#06b6d4"
        />
        <StatCard
          icon={<Camera size={22} />}
          label="Active Cameras"
          value={loading ? "…" : summary?.active_cameras?.toLocaleString()}
          accentColor="#a855f7"
        />
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Violation Types</div>
              <div className="card-subtitle">Distribution by category</div>
            </div>
          </div>
          <ViolationPieChart data={byType} />
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">30-Day Trend</div>
              <div className="card-subtitle">Daily violation count</div>
            </div>
          </div>
          <TrendLineChart data={trends} />
        </div>
      </div>

      {/* Recent Violations */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Recent Violations</div>
            <div className="card-subtitle">Latest detections from all cameras</div>
          </div>
          <a href="/violations" className="btn btn-secondary btn-sm">View All →</a>
        </div>

        {loading ? (
          <div style={{ display: "grid", gap: 12 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 80 }} />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "40px 0",
            color: "var(--text-muted)", fontSize: 14,
          }}>
            <AlertTriangle size={40} style={{ marginBottom: 12, opacity: 0.4 }} />
            <p>No violations detected yet.</p>
            <p style={{ marginTop: 4 }}>Upload a traffic image to get started.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {recent.map((v) => (
              <ViolationCard key={v.id} violation={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
