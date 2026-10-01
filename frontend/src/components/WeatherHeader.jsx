import React from "react";

export function WeatherHeader() {
  return (
    <header className="weather-header">
      <div className="weather-header-container">
        <div className="brand">
          <div className="brand-icon">🌤️</div>
          <div>
            <h1 className="brand-title">Weather Agent</h1>
            <p className="brand-subtitle">Real-time weather & 5-day forecast</p>
          </div>
        </div>
      </div>
    </header>
  );
}
