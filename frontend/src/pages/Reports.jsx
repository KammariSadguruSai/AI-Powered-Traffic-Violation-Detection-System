import { useState, useEffect } from "react";
import { Download, FileText, BarChart3, Calendar } from "lucide-react";
import { analyticsApi, reportsApi } from "../api/client";
import { ViolationBarChart, TrendLineChart } from "../components/Charts";

export default function Reports() {
  const [byType,    setByType]    = useState([]);
  const [trends,    setTrends]    = useState([]);
  const [byCam,     setByCam]     = useState([]);
  const [period,    setPeriod]    = useState("daily");
  const [loading,   setLoading]   = useState(true);
  const [dateFrom,  setDateFrom]  = useState("");
  const [dateTo,    setDateTo]    = useState("");

  useEffect(() => { fetchData(); }, [period]);

  async function fetchData() {
    setLoading(true);
    try {
      const [typeRes, trendRes, camRes] = await Promise.all([
        analyticsApi.byType(),
        analyticsApi.trends({ period, days: period === "monthly" ? 365 : 90 }),
        analyticsApi.byCamera(),
      ]);
      setByType(typeRes.data);
      setTrends(trendRes.data.data);
      setByCam(camRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function exportCsv() {
    const res = await reportsApi.downloadCsv({ date_from: dateFrom || undefined, date_to: dateTo || undefined });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url;
    a.download = `violations_${Date.now()}.csv`; a.click();
  }

  async function exportPdf() {
    const res = await reportsApi.downloadPdf({ date_from: dateFrom || undefined, date_to: dateTo || undefined });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url;
    a.download = `violations_report_${Date.now()}.pdf`; a.click();
  }

  const totalViolations = byType.reduce((s, t) => s + t.count, 0);

  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">Reports & Analytics</h1>
          <p className="page-subtitle">Detailed violation statistics and export tools</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-secondary btn-sm" onClick={exportCsv}>
            <Download size={14} /> Export CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={exportPdf}>
            <FileText size={14} /> Export PDF
          </button>
        </div>
      </div>

      {/* Date filter */}
      <div className="card" style={{ marginBottom: 20, padding: 16 }}>
        <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
          <Calendar size={16} style={{ color: "var(--text-muted)" }} />
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>From</label>
            <input type="date" className="input" style={{ width: 160 }} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>To</label>
            <input type="date" className="input" style={{ width: 160 }} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Trend Period</label>
            <select className="input" style={{ width: 140 }} value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="charts-grid" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Violations by Type</div>
              <div className="card-subtitle">Total: {totalViolations.toLocaleString()}</div>
            </div>
            <BarChart3 size={18} style={{ color: "var(--text-muted)" }} />
          </div>
          {loading
            ? <div className="skeleton" style={{ height: 260 }} />
            : <ViolationBarChart data={byType} />}
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">{period.charAt(0).toUpperCase() + period.slice(1)} Trend</div>
              <div className="card-subtitle">Violation count over time</div>
            </div>
          </div>
          {loading
            ? <div className="skeleton" style={{ height: 260 }} />
            : <TrendLineChart data={trends} period={period} />}
        </div>
      </div>

      {/* Violation type breakdown table */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <div className="card-title">Type Breakdown</div>
        </div>
        <div className="table-container" style={{ border: "none" }}>
          <table>
            <thead>
              <tr>
                <th>Violation Type</th>
                <th>Count</th>
                <th>Share</th>
                <th>Distribution</th>
              </tr>
            </thead>
            <tbody>
              {byType.map((t) => (
                <tr key={t.violation_type}>
                  <td>
                    <span className={`vtype-${t.violation_type}`} style={{ fontWeight: 600 }}>
                      {t.violation_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>{t.count.toLocaleString()}</td>
                  <td style={{ color: "var(--text-secondary)" }}>{t.percentage}%</td>
                  <td style={{ width: 200 }}>
                    <div style={{ height: 6, background: "var(--bg-secondary)", borderRadius: 3, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%", width: `${t.percentage}%`,
                          background: "linear-gradient(90deg, var(--accent), var(--accent-light))",
                          borderRadius: 3,
                          transition: "width 0.5s ease",
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Camera breakdown */}
      {byCam.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Violations by Camera</div>
          </div>
          <div className="table-container" style={{ border: "none" }}>
            <table>
              <thead>
                <tr>
                  <th>Camera ID</th>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Violations</th>
                </tr>
              </thead>
              <tbody>
                {byCam.map((c) => (
                  <tr key={c.camera_id}>
                    <td style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12 }}>
                      {c.camera_id}
                    </td>
                    <td>{c.name}</td>
                    <td style={{ color: "var(--text-secondary)" }}>{c.location || "—"}</td>
                    <td><strong>{c.count}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
