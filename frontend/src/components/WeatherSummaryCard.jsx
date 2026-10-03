import React from "react";

/**
 * WeatherSummaryCard renders the professional AI-generated meteorological report
 * directly below the Current Weather Card.
 *
 * Adheres to:
 * - Professional dark/modern card styling
 * - Seamless fallback when summary is unavailable
 * - Typography and spacing consistent with the design system
 */
export function WeatherSummaryCard({ summary, status, message, loading }) {
  const isAvailable = Boolean(summary && summary.trim() && status !== "UNAVAILABLE");
  const fallbackMessage =
    message || "Weather summary is currently unavailable. Current weather data is shown above.";

  return (
    <div className="weather-summary-card" id="current-weather-summary-card">
      <div className="weather-summary-header">
        <div className="weather-summary-title-wrapper">
          <span className="summary-badge">Meteorological Report</span>
          <h3 className="weather-summary-heading">WEATHER SUMMARY</h3>
        </div>
        <div className="weather-summary-pill-container">
          <span className={`summary-status-pill ${isAvailable ? "status-active" : "status-fallback"}`}>
            {isAvailable ? "Live AI Report" : "Summary Fallback"}
          </span>
        </div>
      </div>

      <div className="weather-summary-body">
        {loading ? (
          <div className="weather-summary-loading">
            <span className="loading-pulse-dot"></span>
            <span>Generating meteorological summary...</span>
          </div>
        ) : isAvailable ? (
          <p className="weather-summary-text" id="weather-summary-text">
            {summary}
          </p>
        ) : (
          <p className="weather-summary-fallback" id="weather-summary-fallback">
            {fallbackMessage}
          </p>
        )}
      </div>

      <div className="weather-summary-footer">
        <span className="weather-summary-source">
          Source: <strong className="source-name">Weather API</strong>
        </span>
      </div>
    </div>
  );
}

export default WeatherSummaryCard;
