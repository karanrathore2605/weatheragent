import React from "react";
import { PLANNED_MODULES } from "../utils/constants";

export function ArchitectureCard() {
  return (
    <div className="card architecture-card">
      <div className="card-header">
        <div className="card-title-group">
          <span className="card-icon">🏛️</span>
          <div>
            <h2 className="card-title">Clean Architecture & Branch Roadmap</h2>
            <p className="card-description">Extensible system design isolating layers</p>
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="flow-container">
          <div className="flow-title">Architectural Flow Rules</div>
          <div className="flow-diagram">
            <div className="flow-row">
              <span className="flow-badge flow-router">Router</span>
              <span className="flow-arrow">⟶</span>
              <span className="flow-badge flow-service">Service</span>
              <span className="flow-arrow">⟶</span>
              <span className="flow-badge flow-client">Client / Repository</span>
            </div>
            <div className="flow-row">
              <span className="flow-badge flow-agent">Agent</span>
              <span className="flow-arrow">⟶</span>
              <span className="flow-badge flow-tool">Tool</span>
              <span className="flow-arrow">⟶</span>
              <span className="flow-badge flow-service">Service</span>
              <span className="flow-arrow">⟶</span>
              <span className="flow-badge flow-client">Client</span>
            </div>
          </div>
        </div>

        <div className="roadmap-section">
          <div className="roadmap-title">Module Implementation Matrix</div>
          <div className="module-list">
            {PLANNED_MODULES.map((mod, idx) => (
              <div key={idx} className="module-item">
                <div className="module-header">
                  <span className="module-name">{mod.name}</span>
                  <span className={`status-pill ${mod.status === "Active" ? "pill-active" : "pill-upcoming"}`}>
                    {mod.status}
                  </span>
                </div>
                <div className="module-branch">{mod.branch}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
