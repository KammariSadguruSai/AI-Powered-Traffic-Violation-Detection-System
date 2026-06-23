import { useState, useEffect, useRef, useCallback } from "react";
import {
  Video, VideoOff, Camera, CameraOff, Settings, Activity,
  AlertTriangle, Play, Square, Upload, MonitorPlay, Zap,
  Clock, Eye, Shield, BarChart3, X, FileVideo, ChevronDown
} from "lucide-react";
import { liveApi, uploadApi } from "../api/client";

const VIOLATION_COLORS = {
  helmet_violation:    { bg: "rgba(239,68,68,0.15)",   border: "rgba(239,68,68,0.4)",   text: "#fca5a5" },
  triple_riding:       { bg: "rgba(245,158,11,0.15)",  border: "rgba(245,158,11,0.4)",  text: "#fde68a" },
  seatbelt_violation:  { bg: "rgba(249,115,22,0.15)",  border: "rgba(249,115,22,0.4)",  text: "#fdba74" },
  wrong_side_driving:  { bg: "rgba(168,85,247,0.15)",  border: "rgba(168,85,247,0.4)",  text: "#c4b5fd" },
  stop_line_violation: { bg: "rgba(59,130,246,0.15)",   border: "rgba(59,130,246,0.4)",  text: "#93c5fd" },
  red_light_violation: { bg: "rgba(220,38,38,0.15)",   border: "rgba(220,38,38,0.4)",   text: "#fca5a5" },
  illegal_parking:     { bg: "rgba(139,92,246,0.15)",  border: "rgba(139,92,246,0.4)",  text: "#c4b5fd" },
};

export default function LiveMonitor() {
  // Refs
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const fileInputRef = useRef(null);

  // State
  const [isStreaming, setIsStreaming]   = useState(false);
  const [isConnected, setIsConnected]  = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [annotatedFrame, setAnnotatedFrame] = useState(null);
  const [violations, setViolations]    = useState([]);
  const [stats, setStats]              = useState({
    totalObjects: 0, totalViolations: 0, sessionViolations: 0,
    sessionObjects: 0, sessionFrames: 0, fps: 0, latency: 0, imageSize: "",
  });
  const [error, setError]              = useState(null);
  const [showConfig, setShowConfig]    = useState(false);
  const [mode, setMode]                = useState("webcam"); // "webcam" | "video"
  const [videoProcessing, setVideoProcessing] = useState(false);
  const [videoResults, setVideoResults] = useState(null);

  // Config
  const [config, setConfig] = useState({
    cameraId: "CAM-001",
    location: "Main Junction",
    stopLineY: "",
    roadCenterX: "",
    fps: 5,
  });

  // FPS tracking
  const fpsRef = useRef({ count: 0, lastTime: Date.now() });

  // ── Cleanup on unmount ──────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopStreaming();
      stopCamera();
    };
  }, []);

  // ── Camera Controls ─────────────────────────────────────────────────────
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
        setError(null);
      }
    } catch (err) {
      setError("Camera access denied or unavailable. Try video upload mode instead.");
      console.error("Camera error:", err);
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  }, []);

  // ── WebSocket Connection ────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    const url = liveApi.getWebSocketUrl();
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      // Send config
      ws.send(JSON.stringify({
        type: "config",
        camera_id: config.cameraId,
        location: config.location,
        stop_line_y: config.stopLineY || null,
        road_center_x: config.roadCenterX || null,
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "result") {
          // Update annotated frame
          if (data.annotated_frame) {
            setAnnotatedFrame(`data:image/jpeg;base64,${data.annotated_frame}`);
          }

          // Update violations feed (prepend new ones)
          if (data.violations && data.violations.length > 0) {
            setViolations((prev) => [...data.violations, ...prev].slice(0, 50));
          }

          // Update stats
          const s = data.stats || {};
          fpsRef.current.count++;
          const now = Date.now();
          const elapsed = (now - fpsRef.current.lastTime) / 1000;
          let currentFps = 0;
          if (elapsed >= 1) {
            currentFps = Math.round(fpsRef.current.count / elapsed);
            fpsRef.current = { count: 0, lastTime: now };
          }

          setStats((prev) => ({
            totalObjects: s.total_objects || 0,
            totalViolations: s.total_violations || 0,
            sessionViolations: s.session_violations || prev.sessionViolations,
            sessionObjects: s.session_objects || prev.sessionObjects,
            sessionFrames: s.session_frames || prev.sessionFrames,
            fps: currentFps || prev.fps,
            latency: data.processing_ms || prev.latency,
            imageSize: s.image_size || prev.imageSize,
          }));
        }

        if (data.type === "error") {
          console.error("WS error:", data.message);
        }

        if (data.type === "session_summary") {
          setIsStreaming(false);
        }
      } catch (e) {
        console.error("WS message parse error:", e);
      }
    };

    ws.onerror = (e) => {
      setError("WebSocket connection error. Make sure the backend is running.");
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsStreaming(false);
    };

    wsRef.current = ws;
  }, [config]);

  // ── Frame Capture & Send ────────────────────────────────────────────────
  const captureAndSend = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
    if (wsRef.current.readyState !== WebSocket.OPEN) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64 = reader.result.split(",")[1];
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "frame", data: base64 }));
          }
        };
        reader.readAsDataURL(blob);
      },
      "image/jpeg",
      0.7,
    );
  }, []);

  // ── Start/Stop Streaming ────────────────────────────────────────────────
  const startStreaming = useCallback(() => {
    if (!cameraActive) return;
    connectWS();
    setIsStreaming(true);

    const intervalMs = Math.round(1000 / config.fps);
    intervalRef.current = setInterval(captureAndSend, intervalMs);
  }, [cameraActive, connectWS, captureAndSend, config.fps]);

  const stopStreaming = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "stop" }));
        }
        wsRef.current.close();
      } catch (e) { /* ignore */ }
      wsRef.current = null;
    }
    setIsStreaming(false);
    setIsConnected(false);
  }, []);

  // ── Video File Processing ───────────────────────────────────────────────
  async function handleVideoUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setVideoProcessing(true);
    setVideoResults(null);
    setError(null);

    const form = new FormData();
    form.append("file", file);
    form.append("camera_id", config.cameraId);
    form.append("location", config.location);
    form.append("skip_frames", "10");

    try {
      const res = await liveApi.processVideo(form);
      setVideoResults(res.data);
      // Add violations to feed
      if (res.data.violations) {
        setViolations((prev) => [...res.data.violations.map((v) => ({
          ...v, timestamp: new Date().toISOString(),
        })), ...prev].slice(0, 100));
      }
    } catch (err) {
      setError("Video processing failed: " + err.message);
    } finally {
      setVideoProcessing(false);
    }
  }

  // ── Violation type stats ────────────────────────────────────────────────
  const violationCounts = violations.reduce((acc, v) => {
    acc[v.violation_type] = (acc[v.violation_type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      {/* Header */}
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <MonitorPlay size={32} style={{ color: "var(--accent)" }} />
            Live Monitor
          </h1>
          <p className="page-subtitle">Real-time traffic violation detection from camera feed</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {isStreaming && (
            <div className="live-indicator-badge">
              <div className="live-pulse" />
              <span>LIVE</span>
            </div>
          )}
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowConfig(!showConfig)}
          >
            <Settings size={14} />
            Config
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger fade-in" style={{ marginBottom: 20 }}>
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Configuration Panel */}
      {showConfig && (
        <div className="card fade-in" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <div className="card-title">Stream Configuration</div>
            <button className="btn btn-secondary btn-sm btn-icon" onClick={() => setShowConfig(false)}>
              <X size={14} />
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: 14 }}>
            <div>
              <label className="config-label">Camera ID</label>
              <input className="input" value={config.cameraId}
                onChange={(e) => setConfig({ ...config, cameraId: e.target.value })}
                placeholder="CAM-001" />
            </div>
            <div>
              <label className="config-label">Location</label>
              <input className="input" value={config.location}
                onChange={(e) => setConfig({ ...config, location: e.target.value })}
                placeholder="Main Junction" />
            </div>
            <div>
              <label className="config-label">Stop Line Y (px)</label>
              <input className="input" type="number" value={config.stopLineY}
                onChange={(e) => setConfig({ ...config, stopLineY: e.target.value })}
                placeholder="Auto" />
            </div>
            <div>
              <label className="config-label">Road Center X (px)</label>
              <input className="input" type="number" value={config.roadCenterX}
                onChange={(e) => setConfig({ ...config, roadCenterX: e.target.value })}
                placeholder="Auto" />
            </div>
            <div>
              <label className="config-label">Capture FPS</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="range" min="1" max="15" value={config.fps}
                  onChange={(e) => setConfig({ ...config, fps: parseInt(e.target.value) })}
                  style={{ flex: 1, accentColor: "var(--accent)" }}
                />
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--accent-light)", minWidth: 30 }}>
                  {config.fps}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats Bar */}
      <div className="live-stats-bar">
        <div className="live-stat">
          <Zap size={14} />
          <span className="live-stat-value">{stats.latency.toFixed(0)}</span>
          <span className="live-stat-label">ms latency</span>
        </div>
        <div className="live-stat">
          <Activity size={14} />
          <span className="live-stat-value">{stats.fps}</span>
          <span className="live-stat-label">FPS</span>
        </div>
        <div className="live-stat">
          <Eye size={14} />
          <span className="live-stat-value">{stats.totalObjects}</span>
          <span className="live-stat-label">objects</span>
        </div>
        <div className="live-stat">
          <AlertTriangle size={14} />
          <span className="live-stat-value" style={{ color: stats.totalViolations > 0 ? "var(--danger-light)" : "inherit" }}>
            {stats.totalViolations}
          </span>
          <span className="live-stat-label">violations</span>
        </div>
        <div className="live-stat-divider" />
        <div className="live-stat">
          <Shield size={14} />
          <span className="live-stat-value">{stats.sessionViolations}</span>
          <span className="live-stat-label">session total</span>
        </div>
        <div className="live-stat">
          <BarChart3 size={14} />
          <span className="live-stat-value">{stats.sessionFrames}</span>
          <span className="live-stat-label">frames</span>
        </div>
        <div className="live-stat">
          <MonitorPlay size={14} />
          <span className="live-stat-value">{stats.imageSize || "—"}</span>
          <span className="live-stat-label">resolution</span>
        </div>
      </div>

      {/* Main Grid: Camera + Results */}
      <div className="live-grid">
        {/* Left: Camera Feed + Controls */}
        <div>
          {/* Mode Tabs */}
          <div className="mode-tabs">
            <button
              className={`mode-tab ${mode === "webcam" ? "active" : ""}`}
              onClick={() => setMode("webcam")}
            >
              <Camera size={14} /> Webcam
            </button>
            <button
              className={`mode-tab ${mode === "video" ? "active" : ""}`}
              onClick={() => setMode("video")}
            >
              <FileVideo size={14} /> Video File
            </button>
          </div>

          <div className="card" style={{ overflow: "hidden" }}>
            {mode === "webcam" ? (
              <>
                {/* Camera Feed */}
                <div className="camera-feed-container">
                  <video
                    ref={videoRef}
                    muted
                    playsInline
                    className="camera-feed-video"
                    style={{ display: cameraActive ? "block" : "none" }}
                  />
                  {!cameraActive && (
                    <div className="camera-placeholder">
                      <CameraOff size={64} style={{ opacity: 0.2, marginBottom: 16 }} />
                      <p style={{ fontSize: 16, fontWeight: 600 }}>Camera Offline</p>
                      <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
                        Click "Start Camera" to begin live detection
                      </p>
                    </div>
                  )}
                  {/* Hidden canvas for frame capture */}
                  <canvas ref={canvasRef} style={{ display: "none" }} />

                  {/* Connection status overlay */}
                  {isStreaming && (
                    <div className="camera-overlay-status">
                      <div className={`connection-dot ${isConnected ? "connected" : ""}`} />
                      <span>{isConnected ? "Connected" : "Connecting…"}</span>
                    </div>
                  )}
                </div>

                {/* Camera Controls */}
                <div className="camera-controls">
                  {!cameraActive ? (
                    <button className="btn btn-primary" onClick={startCamera} style={{ flex: 1 }}>
                      <Camera size={16} /> Start Camera
                    </button>
                  ) : !isStreaming ? (
                    <>
                      <button className="btn btn-primary" onClick={startStreaming} style={{ flex: 1 }}>
                        <Play size={16} /> Start Detection
                      </button>
                      <button className="btn btn-secondary btn-icon" onClick={stopCamera}>
                        <CameraOff size={16} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button className="btn btn-danger" onClick={stopStreaming} style={{ flex: 1 }}>
                        <Square size={16} /> Stop Detection
                      </button>
                      <button className="btn btn-secondary btn-icon" onClick={() => { stopStreaming(); stopCamera(); }}>
                        <VideoOff size={16} />
                      </button>
                    </>
                  )}
                </div>
              </>
            ) : (
              /* Video Upload Mode */
              <div style={{ padding: 24 }}>
                <div
                  className="upload-zone"
                  onClick={() => fileInputRef.current?.click()}
                  style={{ padding: "40px 30px" }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/*"
                    onChange={handleVideoUpload}
                    style={{ display: "none" }}
                  />
                  <div className="upload-icon" style={{ marginBottom: 16 }}>
                    <FileVideo size={28} color="#6366f1" />
                  </div>
                  {videoProcessing ? (
                    <>
                      <div className="upload-title">Processing Video…</div>
                      <div style={{ marginTop: 16 }}>
                        <div className="spinner" style={{ margin: "0 auto" }} />
                      </div>
                      <div className="upload-subtitle" style={{ marginTop: 12 }}>
                        Analyzing frames for traffic violations
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="upload-title">Upload Traffic Video</div>
                      <div className="upload-subtitle">
                        MP4, AVI, MOV · The system will process every 10th frame
                      </div>
                    </>
                  )}
                </div>

                {/* Video Results */}
                {videoResults && (
                  <div className="fade-in" style={{ marginTop: 20 }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
                      <div className="video-result-stat">
                        <span className="video-result-value">{videoResults.total_frames}</span>
                        <span className="video-result-label">Total Frames</span>
                      </div>
                      <div className="video-result-stat">
                        <span className="video-result-value">{videoResults.processed_frames}</span>
                        <span className="video-result-label">Analyzed</span>
                      </div>
                      <div className="video-result-stat">
                        <span className="video-result-value" style={{ color: "var(--danger-light)" }}>
                          {videoResults.violations_found}
                        </span>
                        <span className="video-result-label">Violations</span>
                      </div>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      Duration: {videoResults.video_duration_sec}s · FPS: {videoResults.video_fps?.toFixed(0)} ·
                      Skip rate: every {videoResults.skip_rate} frames
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Annotated Output + Violation Feed */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Annotated Frame */}
          <div className="card">
            <div className="card-header">
              <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Eye size={16} />
                AI Detection Output
              </div>
              {isStreaming && (
                <span className="badge badge-success" style={{ fontSize: 10 }}>
                  Processing
                </span>
              )}
            </div>
            <div className="annotated-frame-container">
              {annotatedFrame ? (
                <img src={annotatedFrame} alt="AI annotated" className="annotated-frame-img" />
              ) : (
                <div className="annotated-placeholder">
                  <Shield size={48} style={{ opacity: 0.15, marginBottom: 12 }} />
                  <p style={{ fontSize: 14 }}>AI output will appear here</p>
                  <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                    Start the camera and begin detection
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Live Violation Feed */}
          <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div className="card-header">
              <div>
                <div className="card-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <AlertTriangle size={16} />
                  Violation Feed
                </div>
                <div className="card-subtitle">{violations.length} events captured</div>
              </div>
              {violations.length > 0 && (
                <button className="btn btn-secondary btn-sm" onClick={() => setViolations([])}>
                  Clear
                </button>
              )}
            </div>

            {/* Violation type summary mini-bar */}
            {Object.keys(violationCounts).length > 0 && (
              <div className="violation-summary-bar">
                {Object.entries(violationCounts).map(([type, count]) => {
                  const colors = VIOLATION_COLORS[type] || { bg: "rgba(99,102,241,0.15)", text: "#818cf8" };
                  return (
                    <span key={type} className="violation-count-chip" style={{ background: colors.bg, color: colors.text }}>
                      {type.replace(/_/g, " ").split(" ").map(w => w[0].toUpperCase()).join("")}: {count}
                    </span>
                  );
                })}
              </div>
            )}

            {/* Scrollable feed */}
            <div className="violation-feed">
              {violations.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)" }}>
                  <Shield size={32} style={{ opacity: 0.2, marginBottom: 8 }} />
                  <p style={{ fontSize: 13 }}>No violations detected yet</p>
                </div>
              ) : (
                violations.map((v, i) => {
                  const colors = VIOLATION_COLORS[v.violation_type] || { bg: "rgba(99,102,241,0.15)", border: "rgba(99,102,241,0.3)", text: "#818cf8" };
                  return (
                    <div key={i} className="violation-feed-item fade-in" style={{ borderLeft: `3px solid ${colors.border}` }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: colors.text }}>
                          {v.violation_type.replace(/_/g, " ").toUpperCase()}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                          {(v.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                        <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                          {v.description || v.vehicle_type || "—"}
                        </span>
                        {v.plate_text && (
                          <span style={{
                            fontSize: 11, fontFamily: "JetBrains Mono, monospace",
                            background: "rgba(99,102,241,0.15)", color: "var(--accent-light)",
                            padding: "1px 8px", borderRadius: 100,
                          }}>
                            {v.plate_text}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 3 }}>
                        <Clock size={10} style={{ verticalAlign: "middle", marginRight: 3 }} />
                        {v.timestamp ? new Date(v.timestamp).toLocaleTimeString() : "—"}
                        {v.frame && ` · Frame ${v.frame}`}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
