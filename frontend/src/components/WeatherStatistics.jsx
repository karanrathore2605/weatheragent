import React, { useState } from "react";
import { getWeatherSummary } from "../services/api";

const PERIODS = [
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "year", label: "Year" },
];

export function WeatherStatistics({ city }) {
  const [period, setPeriod] = useState("week");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleCalculate = async () => {
    if (!city || !city.trim()) {
      setError("Please search or specify a valid city first.");
      return;
    }

    if (loading) return; // Prevent duplicate concurrent requests

    setLoading(true);
    setError(null);

    try {
      const response = await getWeatherSummary(city.trim(), period);
      setData(response);
    } catch (err) {
      setError(err.message || "Failed to calculate weather statistics and summary.");
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const periodCapitalized = period.charAt(0).toUpperCase() + period.slice(1);

  return (
    <section className="statistics-section" aria-label="Weather Statistics">
      <div className="statistics-header">
        <div className="statistics-title-group">
          <span className="current-badge">On-Demand Analysis</span>
          <h3 className="statistics-title">Weather Statistics</h3>
          <p className="statistics-subtitle">
            Calculate deterministic meteorological averages and AI summaries for{" "}
            <strong className="city-highlight">{city}</strong>
          </p>
        </div>

        {/* Period Selector Tabs */}
        <div className="period-tabs" role="tablist" aria-label="Aggregation Period">
          {PERIODS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={period === item.key}
              className={`period-tab-btn ${period === item.key ? "active" : ""}`}
              onClick={() => {
                setPeriod(item.key);
                setData(null); // Clear previous result when changing period
                setError(null);
              }}
              disabled={loading}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* User-Triggered Action Control */}
      <div className="statistics-action-bar">
        <div className="action-city-info">
          <span className="action-label">Target City:</span>
          <span className="action-value">{city}</span>
          <span className="action-dot">•</span>
          <span className="action-label">Selected Horizon:</span>
          <span className="action-value">{periodCapitalized}</span>
        </div>

        <button
          type="button"
          className="btn-calculate-average"
          onClick={handleCalculate}
          disabled={loading || !city}
        >
          {loading ? (
            <>
              <span className="btn-spinner"></span>
              <span>Analyzing weather data...</span>
            </>
          ) : (
            <>
              <span>✨ Calculate Average</span>
            </>
          )}
        </button>
      </div>

      {/* Loading Indicator */}
      {loading && (
        <div className="stats-loading">
          <div className="loading-spinner"></div>
          <span>Analyzing weather data...</span>
        </div>
      )}

      {/* Error Card */}
      {!loading && error && (
        <div className="stats-error-card">
          <span className="stats-error-icon">⚠️</span>
          <div className="stats-error-content">
            <h4>Unable to calculate statistics</h4>
            <p>{error}</p>
            <button type="button" className="stats-retry-btn" onClick={handleCalculate}>
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Insufficient Data State */}
      {!loading && !error && data && data.status === "insufficient_data" && (
        <div className="insufficient-data-card">
          <div className="insufficient-header">
            <span className="insufficient-icon">📊</span>
            <div>
              <h4 className="insufficient-title">
                Not enough historical weather data is available to calculate a reliable {period} average yet.
              </h4>
              <p className="insufficient-desc">
                Calculations require persistent weather observations to accumulate over time. We never fabricate missing historical metrics.
              </p>
            </div>
          </div>

          <div className="insufficient-details-grid">
            <div className="insufficient-metric">
              <span className="metric-label">Target Period</span>
              <span className="metric-value">{periodCapitalized}</span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Recorded Coverage</span>
              <span className="metric-value coverage-low">
                {data.coverage_percent != null ? `${data.coverage_percent}%` : "0.0%"}
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Available Observations</span>
              <span className="metric-value">
                {data.available_from && data.available_to
                  ? `${data.available_from} to ${data.available_to}`
                  : "None recorded yet"}
              </span>
            </div>
          </div>

          <div className="insufficient-footer-note">
            💡 Live weather observations accumulate in the database automatically as queries occur for {city}.
          </div>
        </div>
      )}

      {/* Successful Summary and Statistics */}
      {!loading && !error && data && (data.status === "success" || data.status === "partial_success") && (
        <div className="statistics-result-card">
          <div className="result-header">
            <h4 className="result-title">
              {data.city} — {periodCapitalized} Weather Summary
            </h4>
            {data.statistics && (
              <span className="result-meta-dates">
                {data.statistics.start_date} to {data.statistics.end_date}
              </span>
            )}
          </div>

          {/* AI Natural Language Summary Block */}
          {data.summary && (
            <div className="ai-summary-block">
              <div className="ai-summary-badge">
                <span className="ai-badge-icon">✦</span> AI Meteorological Summary
              </div>
              <p className="ai-summary-text">{data.summary}</p>
            </div>
          )}

          {/* Partial Success Notice if LLM failed but stats are intact */}
          {data.status === "partial_success" && (
            <div className="partial-notice">
              <span>ℹ️</span> {data.message || "Weather statistics are available, but the AI summary could not be generated right now."}
            </div>
          )}

          {/* Deterministic Calculated Metrics */}
          {data.statistics && (
            <div className="stats-metrics-grid">
              <div className="stat-card">
                <span className="stat-icon">🌡️</span>
                <div className="stat-info">
                  <span className="stat-label">Avg Temperature</span>
                  <span className="stat-value">
                    {data.statistics.average_temperature != null
                      ? `${data.statistics.average_temperature}°C`
                      : "N/A"}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <span className="stat-icon">📉</span>
                <div className="stat-info">
                  <span className="stat-label">Temperature Range</span>
                  <span className="stat-value">
                    {data.statistics.minimum_temperature != null && data.statistics.maximum_temperature != null
                      ? `${data.statistics.minimum_temperature}° - ${data.statistics.maximum_temperature}°C`
                      : "N/A"}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <span className="stat-icon">💧</span>
                <div className="stat-info">
                  <span className="stat-label">Avg Humidity</span>
                  <span className="stat-value">
                    {data.statistics.average_humidity != null
                      ? `${data.statistics.average_humidity}%`
                      : "N/A"}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <span className="stat-icon">💨</span>
                <div className="stat-info">
                  <span className="stat-label">Avg Wind</span>
                  <span className="stat-value">
                    {data.statistics.average_wind_speed != null
                      ? `${data.statistics.average_wind_speed} km/h`
                      : "N/A"}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <span className="stat-icon">🌧️</span>
                <div className="stat-info">
                  <span className="stat-label">Total Precipitation</span>
                  <span className="stat-value">
                    {data.statistics.total_precipitation != null
                      ? `${data.statistics.total_precipitation} mm`
                      : "0.0 mm"}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <span className="stat-icon">📊</span>
                <div className="stat-info">
                  <span className="stat-label">Data Coverage</span>
                  <span className="stat-value">
                    {data.statistics.coverage_percent != null
                      ? `${data.statistics.coverage_percent}%`
                      : "N/A"}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
