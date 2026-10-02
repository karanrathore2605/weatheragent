import React, { useState, useEffect, useCallback } from "react";
import { getWeatherStatistics } from "../services/api";

const PERIODS = [
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
  { key: "year", label: "Year" },
];

export function WeatherStatistics({ city }) {
  const [period, setPeriod] = useState("week");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async (targetCity, targetPeriod) => {
    if (!targetCity || !targetCity.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getWeatherStatistics(targetCity.trim(), targetPeriod);
      setStats(data);
    } catch (err) {
      setError(err.message || "Failed to load weather statistics.");
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (city) {
      fetchStats(city, period);
    }
  }, [city, period, fetchStats]);

  const handlePeriodChange = (newPeriod) => {
    if (newPeriod !== period) {
      setPeriod(newPeriod);
    }
  };

  const handleRetry = () => {
    fetchStats(city, period);
  };

  const periodCapitalized = period.charAt(0).toUpperCase() + period.slice(1);

  return (
    <section className="statistics-section" aria-label="Weather Statistics">
      <div className="statistics-header">
        <div className="statistics-title-group">
          <span className="current-badge">Historical Records</span>
          <h3 className="statistics-title">Weather Statistics</h3>
          <p className="statistics-subtitle">
            Deterministic meteorological aggregations for <strong className="city-highlight">{city}</strong>
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
              onClick={() => handlePeriodChange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="stats-loading">
          <div className="loading-spinner"></div>
          <span>Calculating {period} statistics...</span>
        </div>
      )}

      {!loading && error && (
        <div className="stats-error-card">
          <span className="stats-error-icon">⚠️</span>
          <div className="stats-error-content">
            <h4>Unable to load statistics</h4>
            <p>{error}</p>
            <button type="button" className="stats-retry-btn" onClick={handleRetry}>
              Retry
            </button>
          </div>
        </div>
      )}

      {!loading && !error && stats && stats.status === "insufficient_data" && (
        <div className="insufficient-data-card">
          <div className="insufficient-header">
            <span className="insufficient-icon">📊</span>
            <div>
              <h4 className="insufficient-title">
                Not enough historical weather data is available for this period yet.
              </h4>
              <p className="insufficient-desc">
                Statistics require at least 70% data coverage of persisted observations to ensure numerical accuracy without fabrication.
              </p>
            </div>
          </div>

          <div className="insufficient-details-grid">
            <div className="insufficient-metric">
              <span className="metric-label">Requested Period</span>
              <span className="metric-value">
                {periodCapitalized} ({stats.start_date} to {stats.end_date})
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Data Coverage</span>
              <span className="metric-value coverage-low">
                {stats.coverage_percent}% ({stats.observation_count} observations)
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Available Records</span>
              <span className="metric-value">
                {stats.available_from && stats.available_to
                  ? `${stats.available_from} to ${stats.available_to}`
                  : "No recorded observations yet"}
              </span>
            </div>
          </div>

          <div className="insufficient-footer-note">
            💡 Observations accumulate automatically in the database as current weather queries are made for {city}.
          </div>
        </div>
      )}

      {!loading && !error && stats && stats.status === "success" && (
        <div className="statistics-card-wrapper">
          <div className="stats-meta-bar">
            <span className="stats-window-tag">
              🗓️ {periodCapitalized} Window: {stats.start_date} &rarr; {stats.end_date}
            </span>
            <span className="stats-coverage-tag">
              ✓ Coverage: {stats.coverage_percent}% ({stats.observation_count} observations)
            </span>
          </div>

          <div className="stats-metrics-grid">
            <div className="stat-card">
              <span className="stat-icon">🌡️</span>
              <div className="stat-info">
                <span className="stat-label">Avg Temperature</span>
                <span className="stat-value">
                  {stats.average_temperature != null ? `${stats.average_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">❄️</span>
              <div className="stat-info">
                <span className="stat-label">Min Temperature</span>
                <span className="stat-value">
                  {stats.minimum_temperature != null ? `${stats.minimum_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">🔥</span>
              <div className="stat-info">
                <span className="stat-label">Max Temperature</span>
                <span className="stat-value">
                  {stats.maximum_temperature != null ? `${stats.maximum_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">💧</span>
              <div className="stat-info">
                <span className="stat-label">Avg Humidity</span>
                <span className="stat-value">
                  {stats.average_humidity != null ? `${stats.average_humidity}%` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">💨</span>
              <div className="stat-info">
                <span className="stat-label">Avg Wind Speed</span>
                <span className="stat-value">
                  {stats.average_wind_speed != null ? `${stats.average_wind_speed} km/h` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">🌧️</span>
              <div className="stat-info">
                <span className="stat-label">Total Precipitation</span>
                <span className="stat-value">
                  {stats.total_precipitation != null ? `${stats.total_precipitation} mm` : "0.0 mm"}
                </span>
              </div>
            </div>

            <div className="stat-card full-width-stat">
              <span className="stat-icon">📈</span>
              <div className="stat-info" style={{ width: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                  <span className="stat-label">Observation Coverage</span>
                  <span className="stat-badge-success">{stats.coverage_percent}% Complete</span>
                </div>
                <div className="coverage-bar-track">
                  <div
                    className="coverage-bar-fill"
                    style={{ width: `${Math.min(100, stats.coverage_percent)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
