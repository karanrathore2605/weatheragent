import React, { useState } from "react";
import { getWeatherStatistics } from "../services/api";

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
      if (data.status === "INSUFFICIENT_HISTORICAL_DATA") {
        setError(data.message || "Unable to retrieve historical weather data right now. Please try again.");
        setStats(null);
      } else {
        setStats(data);
        setLastCalculated({
          city: data.city || city.trim(),
          period: data.period_type || period,
          duration: data.duration || duration,
        });
      }
    } catch {
      setError("Unable to retrieve historical weather data right now. Please try again.");
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

  const isSuccess = stats && stats.status !== "INSUFFICIENT_HISTORICAL_DATA";

  const effectivePeriod = lastCalculated ? lastCalculated.period : period;
  const effectiveDuration = lastCalculated ? lastCalculated.duration : duration;
  const isMonthView = effectivePeriod === "month";

  const avgTemp =
    stats?.average_temperature_celsius ??
    stats?.statistics?.average_temperature ??
    stats?.average_temperature;

  const overallAvg =
    stats?.overall_average_temperature_celsius ??
    stats?.average_temperature_celsius ??
    stats?.average_temperature;

  const coverageDisplay =
    stats?.data_coverage_percentage != null
      ? `${stats.data_coverage_percentage}%`
      : stats?.coverage_percentage != null
      ? `${stats.coverage_percentage}%`
      : stats?.coverage_percent != null
      ? `${stats.coverage_percent}%`
      : "100%";

  return (
    <section className="statistics-section" aria-label="Weather Statistics">
      <div className="statistics-header">
        <div className="statistics-title-group">
          <span className="current-badge">Historical Analysis</span>
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
          <span>Calculating historical temperature...</span>
        </div>
      )}

      {/* Error / Failure State */}
      {!loading && error && (
        <div className="stats-error-card" id="stats-error-card">
          <span className="stats-error-icon">⚠️</span>
          <div className="stats-error-content">
            <h4>Unable to retrieve historical weather data right now.</h4>
            <p>Please try again.</p>
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

      {/* Successful Calculation: Historical Temperature Analysis */}
      {!loading && !error && isSuccess && (
        <div className="statistics-card-wrapper" id="stats-success-card">
          <div className="average-temp-hero-card">
            <div className="hero-temp-header">
              <span className="hero-temp-badge">Historical Temperature Analysis</span>
              <div className="hero-meta-row">
                <span className="hero-city-title">City:</span>
                <span className="hero-city-name">{lastCalculated ? lastCalculated.city : city}</span>
              </div>
              <div className="hero-meta-row">
                <span className="hero-period-title">Analysis Period:</span>
                <span className="hero-period-label">{effectivePeriod === "week" ? "Week" : "Month"}</span>
              </div>
              <div className="hero-meta-row">
                <span className="hero-period-title">Duration:</span>
                <span className="hero-period-label">
                  {effectivePeriod === "week"
                    ? `${effectiveDuration} Week${effectiveDuration > 1 ? "s" : ""}`
                    : `${effectiveDuration} Month${effectiveDuration > 1 ? "s" : ""}`}
                </span>
              </div>
              {effectivePeriod === "week" ? (
                <div className="hero-meta-row">
                  <span className="hero-period-title">Period:</span>
                  <span className="hero-period-label">
                    {getPeriodDisplayLabel(effectivePeriod, effectiveDuration)}
                    {stats.start_date && stats.end_date && ` (${stats.start_date} to ${stats.end_date})`}
                  </span>
                </div>
              ) : (
                stats.monthly_averages && stats.monthly_averages.length > 0 && (
                  <div className="hero-meta-row">
                    <span className="hero-period-title">Selected Months:</span>
                    <span className="hero-period-label hero-months-highlight">
                      {stats.monthly_averages.map((m) => m.month).join(", ")}
                    </span>
                  </div>
                )
              )}
            </div>

            {/* Case A: Multi-Month or Single Month Selection -> Show Monthly Breakdown + Overall Average */}
            {isMonthView && stats.monthly_averages && stats.monthly_averages.length > 0 ? (
              <>
                <div className="monthly-breakdown-section" id="monthly-breakdown-section">
                  <h4 className="monthly-breakdown-title">
                    <span>📅</span> MONTHLY TEMPERATURE BREAKDOWN
                  </h4>
                  <div className="monthly-table-wrapper">
                    <table className="monthly-breakdown-table">
                      <thead>
                        <tr>
                          <th>Month</th>
                          <th>Average Temperature</th>
                          <th>Coverage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.monthly_averages.map((m, idx) => (
                          <tr key={`${m.month}-${m.year || idx}`}>
                            <td className="month-name-cell">{m.month}</td>
                            <td className="month-temp-cell">
                              {m.average_temperature_celsius != null
                                ? `${m.average_temperature_celsius}°C`
                                : "N/A"}
                            </td>
                            <td className="month-coverage-cell">
                              <span
                                className={`coverage-pill ${
                                  (m.coverage_percentage ?? 100) >= 99 ? "full" : "partial"
                                }`}
                              >
                                {m.coverage_percentage != null ? `${m.coverage_percentage}%` : "100%"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Highlighted Card: OVERALL AVERAGE TEMPERATURE */}
                <div className="overall-average-card" id="overall-average-card">
                  <span className="overall-card-title">
                    OVERALL {effectiveDuration}-MONTH AVERAGE
                  </span>
                  <span className="overall-card-value">
                    {overallAvg != null ? `${overallAvg}°C` : "N/A"}
                  </span>
                  {stats.monthly_averages && stats.monthly_averages.length > 0 && (
                    <div className="selected-months-container" id="selected-months-container">
                      <span className="selected-months-heading">Selected Months:</span>
                      <span className="selected-months-values">
                        {stats.monthly_averages.map((m) => m.month).join(", ")}
                      </span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              /* Case B: Week Selection (1 to 3 Weeks) -> Daily Breakdown Table + Overall Average */
              <>
                {stats.daily_records && stats.daily_records.length > 0 && (
                  <div className="daily-breakdown-section" id="daily-breakdown-section">
                    <h4 className="daily-breakdown-title">
                      <span>📅</span> DAILY TEMPERATURE BREAKDOWN
                    </h4>
                    <div className="daily-table-wrapper">
                      <table className="daily-breakdown-table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Average Temperature</th>
                            <th>Coverage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stats.daily_records.map((r, idx) => (
                            <tr key={`${r.date}-${idx}`}>
                              <td className="daily-date-cell">
                                {r.formatted_date || r.date}
                              </td>
                              <td className="daily-temp-cell">
                                {r.average_temperature_celsius != null
                                  ? `${r.average_temperature_celsius}°C`
                                  : "--"}
                              </td>
                              <td className="daily-coverage-cell">
                                <span
                                  className={`coverage-pill ${
                                    r.status === "Missing"
                                      ? "missing"
                                      : (r.coverage_percentage ?? 100) >= 99
                                      ? "full"
                                      : "partial"
                                  }`}
                                >
                                  {r.status || (r.coverage_percentage != null ? `${r.coverage_percentage}%` : "100%")}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Highlighted Card: OVERALL N-WEEK AVERAGE */}
                <div className="overall-average-card" id="overall-week-average-card">
                  <span className="overall-card-title">
                    OVERALL {effectiveDuration}-WEEK AVERAGE
                  </span>
                  <span className="overall-card-value">
                    {avgTemp != null ? `${avgTemp}°C` : "N/A"}
                  </span>
                </div>
              </>
            )}

            {/* Metadata Footer: Data Coverage & Source */}
            <div className="hero-temp-footer">
              <div className="hero-footer-item">
                <span className="footer-label">Data Coverage:</span>
                <span className="hero-status-tag">{coverageDisplay}</span>
              </div>
              <div className="hero-footer-item">
                <span className="footer-label">Source:</span>
                <span className="hero-source-tag"><strong>Open-Meteo</strong></span>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
