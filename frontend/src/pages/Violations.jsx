import { useState, useEffect } from "react";
import { format } from "date-fns";
import { Search, Filter, Download, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { violationsApi, reportsApi } from "../api/client";

const VIOLATION_TYPES = [
  "helmet_violation", "triple_riding", "seatbelt_violation",
  "wrong_side_driving", "stop_line_violation", "red_light_violation", "illegal_parking",
];

const STATUS_COLORS = {
  pending:   "badge-warning",
  reviewed:  "badge-info",
  resolved:  "badge-success",
  disputed:  "badge-muted",
  dismissed: "badge-muted",
};

export default function Violations() {
  const [violations, setViolations] = useState([]);
  const [total,      setTotal]      = useState(0);
  const [pages,      setPages]      = useState(1);
  const [loading,    setLoading]    = useState(true);

  const [filters, setFilters] = useState({
    page: 1, size: 20,
    violation_type: "",
    status: "",
    plate: "",
  });

  useEffect(() => { fetchData(); }, [filters]);

  async function fetchData() {
    setLoading(true);
    try {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== "")
      );
      const res = await violationsApi.list(params);
      setViolations(res.data.items);
      setTotal(res.data.total);
      setPages(res.data.pages);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function updateFilter(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  async function handleExportCsv() {
    try {
      const res = await reportsApi.downloadCsv({
        violation_type: filters.violation_type || undefined,
      });
      const url  = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href  = url;
      link.download = `violations_${Date.now()}.csv`;
      link.click();
    } catch (err) {
      alert("Export failed: " + err.message);
    }
  }

  async function updateStatus(id, status) {
    try {
      await violationsApi.update(id, { status });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      {/* Header */}
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">Violations</h1>
          <p className="page-subtitle">{total.toLocaleString()} records found</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-secondary btn-sm" onClick={fetchData}>
            <RefreshCw size={14} />
            Refresh
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleExportCsv}>
            <Download size={14} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20, padding: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 12, alignItems: "end" }}>
          {/* Plate search */}
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 6 }}>
              <Search size={11} style={{ marginRight: 4 }} /> Plate Number
            </label>
            <input
              className="input"
              placeholder="Search plate…"
              value={filters.plate}
              onChange={(e) => updateFilter("plate", e.target.value)}
            />
          </div>

          {/* Violation type */}
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 6 }}>
              <Filter size={11} style={{ marginRight: 4 }} /> Violation Type
            </label>
            <select
              className="input"
              value={filters.violation_type}
              onChange={(e) => updateFilter("violation_type", e.target.value)}
            >
              <option value="">All Types</option>
              {VIOLATION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div>
            <label style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 6 }}>
              Status
            </label>
            <select
              className="input"
              value={filters.status}
              onChange={(e) => updateFilter("status", e.target.value)}
            >
              <option value="">All Statuses</option>
              {["pending", "reviewed", "resolved", "disputed", "dismissed"].map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {/* Clear */}
          <button
            className="btn btn-secondary"
            onClick={() => setFilters({ page: 1, size: 20, violation_type: "", status: "", plate: "" })}
          >
            Clear Filters
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Evidence</th>
                <th>Violation</th>
                <th>Plate</th>
                <th>Vehicle</th>
                <th>Confidence</th>
                <th>Location</th>
                <th>Date & Time</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(9)].map((__, j) => (
                      <td key={j}>
                        <div className="skeleton" style={{ height: 16, width: "80%" }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : violations.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: 48, color: "var(--text-muted)" }}>
                    No violations match the current filters.
                  </td>
                </tr>
              ) : (
                violations.map((v) => (
                  <tr key={v.id}>
                    {/* Thumbnail */}
                    <td>
                      {v.evidence_thumbnail ? (
                        <img
                          src={`data:image/jpeg;base64,${v.evidence_thumbnail}`}
                          alt="ev"
                          style={{ width: 64, height: 48, objectFit: "cover", borderRadius: 6, border: "1px solid var(--border)" }}
                        />
                      ) : (
                        <div style={{ width: 64, height: 48, background: "var(--bg-secondary)", borderRadius: 6, border: "1px solid var(--border)" }} />
                      )}
                    </td>

                    {/* Type */}
                    <td>
                      <span className={`vtype-${v.violation_type}`} style={{ fontWeight: 600, fontSize: 12 }}>
                        {v.violation_type.replace(/_/g, " ").toUpperCase()}
                      </span>
                    </td>

                    {/* Plate */}
                    <td>
                      {v.plate_number ? (
                        <span style={{
                          fontFamily: "JetBrains Mono, monospace", fontSize: 12,
                          background: "rgba(99,102,241,0.15)", color: "var(--accent-light)",
                          padding: "3px 10px", borderRadius: 100,
                        }}>
                          {v.plate_number}
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>

                    <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>{v.vehicle_type || "—"}</td>

                    {/* Confidence */}
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{
                          height: 4, width: 60, borderRadius: 2,
                          background: "var(--bg-secondary)",
                          overflow: "hidden",
                        }}>
                          <div style={{
                            height: "100%",
                            width: `${(v.confidence * 100).toFixed(0)}%`,
                            background: v.confidence > 0.8 ? "#10b981" : v.confidence > 0.6 ? "#f59e0b" : "#ef4444",
                            borderRadius: 2,
                          }} />
                        </div>
                        <span style={{ fontSize: 12 }}>{(v.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </td>

                    <td style={{ fontSize: 12, color: "var(--text-secondary)", maxWidth: 140 }}>
                      {v.location || "—"}
                    </td>

                    <td style={{ fontSize: 12, color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                      {v.detected_at
                        ? format(new Date(v.detected_at), "dd MMM yy, HH:mm")
                        : "—"}
                    </td>

                    {/* Status */}
                    <td>
                      <span className={`badge ${STATUS_COLORS[v.status] || "badge-muted"}`}>
                        {v.status}
                      </span>
                    </td>

                    {/* Actions */}
                    <td>
                      <select
                        className="input"
                        style={{ fontSize: 11, padding: "4px 8px" }}
                        value={v.status}
                        onChange={(e) => updateStatus(v.id, e.target.value)}
                      >
                        {["pending", "reviewed", "resolved", "disputed", "dismissed"].map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="pagination">
          <button
            className="page-btn"
            disabled={filters.page <= 1}
            onClick={() => updateFilter("page", filters.page - 1)}
          >
            <ChevronLeft size={14} />
          </button>
          {[...Array(Math.min(pages, 7))].map((_, i) => {
            const pg = i + 1;
            return (
              <button
                key={pg}
                className={`page-btn ${filters.page === pg ? "active" : ""}`}
                onClick={() => updateFilter("page", pg)}
              >
                {pg}
              </button>
            );
          })}
          <button
            className="page-btn"
            disabled={filters.page >= pages}
            onClick={() => updateFilter("page", filters.page + 1)}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
