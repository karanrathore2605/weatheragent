import React from "react";
import { useHealthCheck } from "../hooks/useHealthCheck";

export function HealthStatus() {
  const { data, loading, error, latency, refetch } = useHealthCheck();

  const isHealthy = Boolean(data && data.status === "ok");

  return (
    <div className="card health-card">
      <div className="card-header">
        <div className="card-title-group">
          <span className="card-icon">⚡</span>
          <div>
            <h2 className="card-title">Backend Connectivity</h2>
            <p className="card-description">Live probe to FastAPI <code>GET /health</code> endpoint</p>
          </div>
        </div>

        <button
          onClick={refetch}
          disabled={loading}
          className="btn btn-secondary"
          title="Refresh health status"
        >
          {loading ? (
            <span className="spinner"></span>
          ) : (
            <span>↻ Ping Backend</span>
          )}
        </button>
      </div>

      <div className="card-body">
        <div className="status-hero">
          <div className={`status-indicator ${isHealthy ? "status-online" : loading ? "status-loading" : "status-offline"}`}>
            <span className="status-ping"></span>
            <span className="status-circle"></span>
          </div>

          <div className="status-info">
            <div className="status-headline">
              {loading
                ? "Probing backend server..."
                : isHealthy
                ? "Backend is Online & Healthy"
                : "Backend Unreachable"}
            </div>
            <div className="status-subline">
              {error ? (
                <span className="error-text">{error}</span>
              ) : data ? (
                <span>Response: <code>{JSON.stringify(data)}</code> in <strong>{latency}ms</strong></span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="meta-grid">
          <div className="meta-item">
            <span className="meta-label">Status</span>
            <span className="meta-value tag">{data ? data.status : "offline"}</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Protocol</span>
            <span className="meta-value font-mono">REST / JSON</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Endpoint</span>
            <span className="meta-value font-mono">/health</span>
          </div>
          <div className="meta-item">
            <span className="meta-label">CORS</span>
            <span className="meta-value tag">Enabled</span>
          </div>
        </div>

        <div className="endpoint-callout">
          <span className="method-badge">GET</span>
          <span className="endpoint-path">/health</span>
          <span className="endpoint-note">Expected payload: {`{"status": "ok"}`}</span>
        </div>
      </div>
    </div>
  );
}
