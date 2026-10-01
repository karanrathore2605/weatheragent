import React from "react";
import { APP_NAME, CURRENT_BRANCH } from "../utils/constants";

export function Header() {
  return (
    <header className="app-header">
      <div className="header-container">
        <div className="brand">
          <div className="brand-logo">
            <span className="logo-icon">🌤️</span>
          </div>
          <div className="brand-text">
            <h1 className="brand-title">{APP_NAME}</h1>
            <p className="brand-subtitle">Production Architecture Shell</p>
          </div>
        </div>

        <div className="header-meta">
          <span className="badge badge-branch">
            <span className="badge-dot pulse-blue"></span>
            {CURRENT_BRANCH}
          </span>
          <span className="badge badge-tech">React 19 + FastAPI</span>
        </div>
      </div>
    </header>
  );
}
