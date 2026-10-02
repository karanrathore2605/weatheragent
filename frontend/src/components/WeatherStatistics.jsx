import React, { useState } from "react";
import { getWeatherStatistics } from "../services/api";

const WEEK_DURATIONS = [
  { value: 1, label: "1 Week" },
  { value: 2, label: "2 Weeks" },
  { value: 3, label: "3 Weeks" },
  { value: 4, label: "4 Weeks" },
];

const MONTH_DURATIONS = [
  { value: 1, label: "1 Month" },
  { value: 2, label: "2 Months" },
  { value: 3, label: "3 Months" },
  { value: 4, label: "4 Months" },
  { value: 5, label: "5 Months" },
  { value: 6, label: "6 Months" },
  { value: 7, label: "7 Months" },
  { value: 8, label: "8 Months" },
  { value: 9, label: "9 Months" },
  { value: 10, label: "10 Months" },
  { value: 11, label: "11 Months" },
  { value: 12, label: "12 Months" },
];

export function WeatherStatistics({ city }) {
  const [period, setPeriod] = useState("week");
  const [duration, setDuration] = useState(1);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastCalculated, setLastCalculated] = useState(null);

  const handlePeriodChange = (newPeriod) => {
    setPeriod(newPeriod);
    setDuration(1); // Reset duration on period change
  };

  const handleCalculateAverage = async () => {
    if (!city || !city.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const data = await getWeatherStatistics(city.trim(), period, duration);
      setStats(data);
      setLastCalculated({
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

  const getPeriodDisplayLabel = (targetPeriod, targetDuration) => {
    const isWeek = targetPeriod === "week";
    if (targetDuration === 1) {
      return isWeek ? "Previous 1 Week" : "Previous 1 Month";
    }
    return isWeek
      ? `Previous ${targetDuration} Weeks`
      : `Previous ${targetDuration} Months`;
  };

  const isInsufficient =
    stats &&
    (stats.status === "INSUFFICIENT_HISTORICAL_DATA" ||
      stats.status === "insufficient_data" ||
      stats.data_coverage?.complete === false ||
      stats.coverage?.complete === false);

  const isSuccess = stats && !isInsufficient;

  const avgTemp =
    stats?.average_temperature_celsius ??
    stats?.statistics?.average_temperature ??
    stats?.average_temperature;

  return (
    <section className="statistics-section" aria-label="Weather Statistics">
      <div className="statistics-header">
        <div className="statistics-title-group">
          <span className="current-badge">Historical Average</span>
          <h3 className="statistics-title">Weather Statistics</h3>
          <p className="statistics-subtitle">
            Historical temperature analysis for <strong className="city-highlight">{city}</strong>
          </p>
        </div>
      </div>

      {/* Control Panel with Dropdowns and Calculate Button */}
      <div className="stats-controls-panel">
        <div className="control-group">
          <label htmlFor="analysis-period-select" className="control-label">
            ANALYSIS PERIOD
          </label>
          <div className="select-wrapper">
            <select
              id="analysis-period-select"
              className="dropdown-select"
              value={period}
              onChange={(e) => handlePeriodChange(e.target.value)}
            >
              <option value="week">Week</option>
              <option value="month">Month</option>
            </select>
            <span className="select-arrow" aria-hidden="true">▼</span>
          </div>
        </div>

        <div className="control-group">
          <label htmlFor="duration-select" className="control-label">
            DURATION
          </label>
          <div className="select-wrapper">
            <select
              id="duration-select"
              className="dropdown-select"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            >
              {currentDurations.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
            <span className="select-arrow" aria-hidden="true">▼</span>
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
          <span>Calculating average temperature...</span>
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

      {/* Before calculation / Initial state */}
      {!loading && !error && !stats && (
        <div className="stats-empty-state" id="stats-prompt-state">
          <span className="empty-state-icon">📈</span>
          <p className="empty-state-text">
            Select an analysis period and duration, then click <strong>Calculate Average</strong>.
          </p>
        </div>
      )}

      {/* Insufficient Data State */}
      {!loading && !error && isInsufficient && (
        <div className="insufficient-data-card" id="stats-insufficient-card">
          <div className="insufficient-header">
            <span className="insufficient-icon">📊</span>
            <div>
              <h4 className="insufficient-title">
                Historical weather data is not available for the complete requested period.
              </h4>
              <p className="insufficient-desc">
                AccuWeather provides recent historical observations. Extended period statistics require complete observation coverage to guarantee numerical accuracy without data fabrication.
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
                {getPeriodDisplayLabel(stats.period_type || period, stats.duration || duration)}
              </span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Provider</span>
              <span className="metric-value">AccuWeather</span>
            </div>

            <div className="insufficient-metric">
              <span className="metric-label">Data Coverage</span>
              <span className="metric-value coverage-low">Incomplete</span>
            </div>
          </div>

          <div className="insufficient-footer-note">
            💡 Historical observations originate from AccuWeather.
          </div>
        </div>
      )}

      {/* Successful Calculation: Main statistic is Average Temperature */}
      {!loading && !error && isSuccess && (
        <div className="statistics-card-wrapper" id="stats-success-card">
          <div className="stats-meta-bar">
            <span className="stats-window-tag">
              📍 <strong>{stats.city || city}</strong> &bull;{" "}
              {lastCalculated
                ? getPeriodDisplayLabel(lastCalculated.period, lastCalculated.duration)
                : getPeriodDisplayLabel(period, duration)}
              {stats.start_date && stats.end_date && ` (${stats.start_date} to ${stats.end_date})`}
            </span>
            <span className="stats-coverage-tag">
              Source: AccuWeather
            </span>
          </div>

          <div className="average-temp-hero-card">
            <div className="hero-temp-header">
              <span className="hero-temp-badge">AccuWeather Historical Analysis</span>
              <span className="hero-city-name">{stats.city || city}</span>
              <span className="hero-period-label">
                {lastCalculated
                  ? getPeriodDisplayLabel(lastCalculated.period, lastCalculated.duration)
                  : getPeriodDisplayLabel(period, duration)}
              </span>
            </div>

            <div className="hero-temp-display">
              <span className="hero-temp-icon" aria-hidden="true">🌡️</span>
              <div className="hero-temp-details">
                <span className="hero-temp-title">Average Temperature</span>
                <span className="hero-temp-value">
                  {avgTemp != null ? `${avgTemp}°C` : "N/A"}
                </span>
              </div>
            </div>

            <div className="hero-temp-footer">
              <span className="hero-source-tag">Source: <strong>AccuWeather</strong></span>
              <span className="hero-status-tag">✓ Coverage: Complete</span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
