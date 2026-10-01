import React from "react";
import { Header, HealthStatus, ArchitectureCard } from "../components";

export function Dashboard() {
  return (
    <div className="app-shell">
      <Header />
      <main className="main-content">
        <div className="content-container">
          <div className="welcome-banner">
            <div className="banner-badge">Branch 01 • Production Foundation</div>
            <h2 className="banner-title">Welcome to Weather Agent Foundation</h2>
            <p className="banner-text">
              The project is cleanly decoupled between FastAPI backend and React frontend.
              Upcoming branches will integrate Google Weather API, LangGraph agent workflows,
              calculators, conversation memory, and Gmail tools.
            </p>
          </div>

          <div className="dashboard-grid">
            <HealthStatus />
            <ArchitectureCard />
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <div className="footer-container">
          <span>Weather Forecast Agent • Decoupled Micro-Architecture</span>
          <span className="footer-note">Initial Setup Ready</span>
        </div>
      </footer>
    </div>
  );
}
