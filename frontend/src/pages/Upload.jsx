import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, CheckCircle2, AlertTriangle, X, Loader, Image as ImageIcon } from "lucide-react";
import { uploadApi } from "../api/client";

const VIOLATION_COLORS = {
  helmet_violation:    "#ef4444",
  triple_riding:       "#f59e0b",
  seatbelt_violation:  "#f97316",
  wrong_side_driving:  "#a855f7",
  stop_line_violation: "#3b82f6",
  red_light_violation: "#dc2626",
  illegal_parking:     "#8b5cf6",
};

export default function UploadPage() {
  const [file,      setFile]      = useState(null);
  const [preview,   setPreview]   = useState(null);
  const [result,    setResult]    = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const [cameraId,  setCameraId]  = useState("CAM-001");
  const [location,  setLocation]  = useState("Main Junction");

  const onDrop = useCallback((accepted) => {
    if (!accepted.length) return;
    const f = accepted[0];
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setError(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
  });

  async function handleAnalyze() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append("file",      file);
    form.append("camera_id", cameraId);
    form.append("location",  location);

    try {
      const res = await uploadApi.processImage(form);
      setResult(res.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  }

  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      <div className="page-header">
        <h1 className="page-title">Upload & Analyze</h1>
        <p className="page-subtitle">
          Upload a traffic surveillance image to detect violations
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        {/* Left: Upload + Config */}
        <div>
          <div className="card" style={{ marginBottom: 20 }}>
            {/* Upload Zone */}
            <div
              {...getRootProps()}
              className={`upload-zone ${isDragActive ? "drag-active" : ""}`}
            >
              <input {...getInputProps()} />
              <div className="upload-icon">
                {file ? <CheckCircle2 color="#10b981" /> : <Upload color="#6366f1" />}
              </div>
              {file ? (
                <>
                  <div className="upload-title" style={{ color: "var(--success-light)" }}>
                    {file.name}
                  </div>
                  <div className="upload-subtitle">
                    {(file.size / 1024).toFixed(1)} KB · Click or drop to replace
                  </div>
                </>
              ) : (
                <>
                  <div className="upload-title">
                    {isDragActive ? "Drop it here!" : "Drop traffic image here"}
                  </div>
                  <div className="upload-subtitle">
                    JPEG, PNG, WebP · Max 50 MB
                  </div>
                </>
              )}
            </div>

            {/* Config */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                  Camera ID
                </label>
                <input
                  className="input"
                  value={cameraId}
                  onChange={(e) => setCameraId(e.target.value)}
                  placeholder="e.g. CAM-001"
                />
              </div>
              <div>
                <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                  Location
                </label>
                <input
                  className="input"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. MG Road Junction"
                />
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={handleAnalyze}
                disabled={!file || loading}
              >
                {loading ? (
                  <><Loader size={16} className="spin" /> Analyzing…</>
                ) : (
                  <><Upload size={16} /> Analyze Image</>
                )}
              </button>
              {file && (
                <button className="btn btn-secondary btn-icon" onClick={handleReset}>
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="alert alert-danger fade-in">
              <AlertTriangle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Results panel */}
          {result && (
            <div className="card fade-in">
              <div className="card-header">
                <div className="card-title">
                  {result.violations.length === 0 ? (
                    <span style={{ color: "var(--success)" }}>✓ No Violations</span>
                  ) : (
                    <span style={{ color: "var(--danger)" }}>
                      ⚠ {result.violations.length} Violation{result.violations.length > 1 ? "s" : ""} Found
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  {result.processing_time_ms.toFixed(0)} ms
                </span>
              </div>

              {/* Violation list */}
              {result.violations.map((v, i) => (
                <div
                  key={i}
                  style={{
                    padding: "12px 14px",
                    borderRadius: 8,
                    border: `1px solid ${VIOLATION_COLORS[v.violation_type] || "#6366f1"}44`,
                    background: `${VIOLATION_COLORS[v.violation_type] || "#6366f1"}11`,
                    marginBottom: 10,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <strong style={{ fontSize: 13, color: VIOLATION_COLORS[v.violation_type] || "var(--accent)" }}>
                      {v.violation_type.replace(/_/g, " ").toUpperCase()}
                    </strong>
                    <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {(v.confidence * 100).toFixed(0)}% conf
                    </span>
                  </div>
                  {v.plate && (
                    <span style={{
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: 12,
                      background: "rgba(99,102,241,0.15)",
                      color: "var(--accent-light)",
                      padding: "2px 10px",
                      borderRadius: 100,
                    }}>
                      🚗 {v.plate.plate_text}
                    </span>
                  )}
                  {v.description && (
                    <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
                      {v.description}
                    </div>
                  )}
                </div>
              ))}

              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>
                {result.detected_objects.length} objects detected ·{" "}
                {result.width}×{result.height}px
              </div>
            </div>
          )}
        </div>

        {/* Right: Image Preview */}
        <div>
          <div className="card" style={{ minHeight: 420 }}>
            <div className="card-header">
              <div className="card-title">
                {result ? "Evidence Image" : "Preview"}
              </div>
              {result && (
                <a
                  href={(() => {
                    if (!result?.evidence_path) return "#";
                    let base = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
                    base = base.trim();
                    if (!/^https?:\/\//i.test(base) && !base.startsWith("/")) {
                      base = `https://${base}`;
                    }
                    const host = base.replace(/\/api\/v1\/?$/, "");
                    const relPath = result.evidence_path.split("evidence")[1] || "";
                    return `${host}/evidence${relPath}`;
                  })()}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary btn-sm"
                >
                  Download
                </a>
              )}
            </div>

            {result?.evidence_thumbnail ? (
              <div className="evidence-grid" style={{ gridTemplateColumns: "1fr" }}>
                <div>
                  <div className="evidence-label">Annotated Evidence</div>
                  <img
                    src={`data:image/jpeg;base64,${result.evidence_thumbnail}`}
                    alt="Annotated evidence"
                    className="evidence-img"
                  />
                </div>
              </div>
            ) : preview ? (
              <div className="scanning-container">
                {loading && <div className="scanning-line" />}
                <img
                  src={preview}
                  alt="Preview"
                  style={{
                    width: "100%",
                    display: "block",
                    borderRadius: "var(--radius-md)",
                    opacity: loading ? 0.5 : 1,
                    transition: "opacity 0.3s ease",
                  }}
                />
              </div>
            ) : (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: 320, color: "var(--text-muted)",
              }}>
                <ImageIcon size={64} style={{ marginBottom: 16, opacity: 0.3 }} />
                <p style={{ fontSize: 14 }}>Upload an image to see the preview</p>
              </div>
            )}

            {loading && (
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                gap: 12, padding: 24, color: "var(--text-secondary)", fontSize: 14,
              }}>
                <div className="spinner" />
                Running AI analysis…
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
