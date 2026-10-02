import React, { useState } from "react";
import { getWeatherStatistics } from "../services/api";

const PERIODS = [
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
];

const WEEK_DURATIONS = [
  { value: 1, label: "1 Week" },
  { value: 2, label: "2 Weeks" },
  { value: 3, label: "3 Weeks" },
];

const MONTH_DURATIONS = [
  { value: 1, label: "1 Month" },
  { value: 2, label: "2 Months" },
  { value: 3, label: "3 Months" },
  { value: 4, label: "4 Months" },
];

export function WeatherStatistics({ city }) {
  const [period, setPeriod] = useState("week");
  const [duration, setDuration] = useState(1);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastCalculatedParams, setLastCalculatedParams] = useState(null);

  const handlePeriodChange = (newPeriod) => {
    if (newPeriod !== period) {
      setPeriod(newPeriod);
      setDuration(1); // Reset duration to 1 when period changes
    }
  };

  const handleCalculateAverage = async () => {
    if (!city || !city.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getWeatherStatistics(city.trim(), period, duration);
      setStats(data);
      setLastCalculatedParams({
        city: city.trim(),
        period,
        duration,
      });
    } catch (err) {
      setError(err.message || "Failed to load weather statistics.");
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  const currentDurations = period === "week" ? WEEK_DURATIONS : MONTH_DURATIONS;

  const durationLabel =
    currentDurations.find((d) => d.value === duration)?.label ||
    `${duration} ${period === "week" ? (duration === 1 ? "Week" : "Weeks") : (duration === 1 ? "Month" : "Months")}`;

  const isInsufficient =
    stats &&
    (stats.status === "INSUFFICIENT_HISTORICAL_DATA" ||
      stats.status === "insufficient_data" ||
      stats.coverage?.complete === false);

  const isSuccess =
    stats &&
    !isInsufficient &&
    (stats.status === "SUCCESS" || stats.status === "success" || Boolean(stats.statistics));

  const statsData = stats?.statistics || stats;

  return (
    <section className="statistics-section" aria-label="Weather Statistics">
      <div className="statistics-header">
        <div className="statistics-title-group">
          <span className="current-badge">Historical Average</span>
          <h3 className="statistics-title">Weather Statistics</h3>
          <p className="statistics-subtitle">
            Deterministic meteorological analysis for <strong className="city-highlight">{city}</strong>
          </p>
        </div>
      </div>

      {/* Control Panel: Analysis Period, Duration Selector, and Calculate Button */}
      <div className="stats-controls-panel">
        <div className="control-group">
          <label className="control-label">Analysis Period</label>
          <div className="period-tabs" role="tablist" aria-label="Analysis Period">
            {PERIODS.map((item) => (
              <button
                key={item.key}
                type="button"
                role="tab"
                id={`period-tab-${item.key}`}
                aria-selected={period === item.key}
                className={`period-tab-btn ${period === item.key ? "active" : ""}`}
                onClick={() => handlePeriodChange(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-group">
          <label className="control-label">Duration</label>
          <div className="duration-selector" role="group" aria-label="Duration Selection">
            {currentDurations.map((d) => (
              <button
                key={d.value}
                type="button"
                id={`duration-btn-${period}-${d.value}`}
                className={`duration-btn ${duration === d.value ? "active" : ""}`}
                onClick={() => setDuration(d.value)}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-action">
          <button
            type="button"
            id="calculate-average-btn"
            className="calculate-btn"
            disabled={loading}
            onClick={handleCalculateAverage}
          >
            {loading ? "Calculating..." : "Calculate Average"}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="stats-loading" id="stats-loading-indicator">
          <div className="loading-spinner"></div>
          <span>Calculating weather statistics...</span>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="stats-error-card" id="stats-error-card">
          <span className="stats-error-icon">⚠️</span>
          <div className="stats-error-content">
            <h4>Unable to calculate statistics</h4>
            <p>{error}</p>
            <button
              type="button"
              className="stats-retry-btn"
              onClick={handleCalculateAverage}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Initial Prompt State (before first calculation) */}
      {!loading && !error && !stats && (
        <div className="stats-empty-state">
          <span className="empty-state-icon">📈</span>
          <p className="empty-state-text">
            Select an analysis period and duration above, then click <strong>Calculate Average</strong> to view meteorological statistics.
          </p>
        </div>
      )}

      {/* Insufficient Coverage State */}
      {!loading && !error && isInsufficient && (
        <div className="insufficient-data-card" id="stats-insufficient-card">
          <div className="insufficient-header">
            <span className="insufficient-icon">📊</span>
            <div>
              <h4 className="insufficient-title">
                Historical weather data is not available for the complete requested period yet.
              </h4>
              <p className="insufficient-desc">
                Google Weather API provides recent historical observations. Extended period statistics require complete observation coverage to guarantee numerical accuracy without data fabrication.
              </p>
            </div>
          </div>

          <div className="insufficient-details-grid">
            <div className="insufficient-metric">
              <span className="metric-label">Target City</span>
              <span className="metric-value">{stats.city || city}</span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Requested Period</span>
              <span className="metric-value">
                Previous {stats.period_value || duration} {stats.period_type ? (stats.period_type === "week" ? (stats.period_value === 1 ? "Week" : "Weeks") : (stats.period_value === 1 ? "Month" : "Months")) : durationLabel}
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Available Coverage</span>
              <span className="metric-value coverage-low">
                {stats.coverage?.available || `${stats.coverage_percent || 0}%`}
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Data Coverage</span>
              <span className="metric-value">Incomplete</span>
            </div>
          </div>

          <div className="insufficient-footer-note">
            💡 Observations accumulate directly from Google Weather API as queries are processed for {stats.city || city}.
          </div>
        </div>
      )}

      {/* Success State */}
      {!loading && !error && isSuccess && (
        <div className="statistics-card-wrapper" id="stats-success-card">
          <div className="stats-meta-bar">
            <span className="stats-window-tag">
              📍 <strong>{stats.city || city}</strong> &bull; Previous {lastCalculatedParams ? `${lastCalculatedParams.duration} ${lastCalculatedParams.duration === 1 ? (lastCalculatedParams.period === "week" ? "Week" : "Month") : (lastCalculatedParams.period === "week" ? "Weeks" : "Months")}` : durationLabel}
              {stats.start_date && stats.end_date && ` (${stats.start_date} to ${stats.end_date})`}
            </span>
            <span className="stats-coverage-tag">
              ✓ Data Coverage: Complete
            </span>
          </div>

          <div className="stats-metrics-grid">
            <div className="stat-card">
              <span className="stat-icon">🌡️</span>
              <div className="stat-info">
                <span className="stat-label">Average Temperature</span>
                <span className="stat-value">
                  {statsData?.average_temperature != null ? `${statsData.average_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">❄️</span>
              <div className="stat-info">
                <span className="stat-label">Minimum Temperature</span>
                <span className="stat-value">
                  {statsData?.minimum_temperature != null ? `${statsData.minimum_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-icon">🔥</span>
              <div className="stat-info">
                <span className="stat-label">Maximum Temperature</span>
                <span className="stat-value">
                  {statsData?.maximum_temperature != null ? `${statsData.maximum_temperature}°C` : "N/A"}
                </span>
              </div>
            </div>

            {statsData?.average_feels_like_temperature != null && (
              <div className="stat-card">
                <span className="stat-icon">🧍</span>
                <div className="stat-info">
                  <span className="stat-label">Feels Like</span>
                  <span className="stat-value">{statsData.average_feels_like_temperature}°C</span>
                </div>
              </div>
            )}

            {statsData?.average_humidity != null && (
              <div className="stat-card">
                <span className="stat-icon">💧</span>
                <div className="stat-info">
                  <span className="stat-label">Average Humidity</span>
                  <span className="stat-value">{statsData.average_humidity}%</span>
                </div>
              </div>
            )}

            {statsData?.average_wind_speed != null && (
              <div className="stat-card">
                <span className="stat-icon">💨</span>
                <div className="stat-info">
                  <span className="stat-label">Average Wind Speed</span>
                  <span className="stat-value">{statsData.average_wind_speed} km/h</span>
                </div>
              </div>
            )}

            {statsData?.total_precipitation != null && (
              <div className="stat-card">
                <span className="stat-icon">🌧️</span>
                <div className="stat-info">
                  <span className="stat-label">Total Precipitation</span>
                  <span className="stat-value">{statsData.total_precipitation} mm</span>
                </div>
              </div>
            )}

            <div className="stat-card full-width-stat">
              <span className="stat-icon">✅</span>
              <div className="stat-info" style={{ width: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                  <span className="stat-label">Data Coverage</span>
                  <span className="stat-badge-success">Complete</span>
                </div>
                <div className="coverage-bar-track">
                  <div
                    className="coverage-bar-fill"
                    style={{ width: "100%" }}
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
