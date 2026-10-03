import React, { useState, useEffect } from "react";
import { getMonthlyWeatherReport } from "../services/api";

const PRESET_MONTHS = [
  "August 2026",
  "July 2026",
  "September 2026",
  "June 2026",
  "May 2026",
  "April 2026",
  "March 2026",
  "February 2026",
  "January 2026",
  "December 2025",
  "November 2025",
  "October 2025",
];

export function MonthlyWeatherReport({ city = "Indore" }) {
  const [month, setMonth] = useState("August 2026");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // When city changes from Current Weather search, clear previous report
  useEffect(() => {
    setReport(null);
    setError(null);
  }, [city]);

  const handleGenerateReport = async (e) => {
    if (e) e.preventDefault();
    if (!city || !city.trim()) {
      setError("Please search for a city first.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await getMonthlyWeatherReport(city.trim(), month);
      if (data.status === "UNAVAILABLE") {
        setError(data.message || "Historical weather data is currently unavailable for the selected period.");
        setReport(null);
      } else {
        setReport(data);
      }
    } catch (err) {
      setError(
        err.message || "Historical weather data is currently unavailable for the selected period."
      );
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  // Ensure exactly 4 weeks (no Remaining Days)
  const fourWeeks = report?.weekly_averages
    ? report.weekly_averages.filter((item) => item.week !== "Remaining Days").slice(0, 4)
    : [];

  return (
    <section className="monthly-report-section" aria-label="Monthly Weather Report Generation">
      <div className="monthly-report-card">
        {/* Section Header */}
        <div className="monthly-report-header">
          <div className="report-title-group">
            <span className="report-badge">Report Generator</span>
            <h2 className="report-heading">Monthly Weather Report</h2>
            <p className="report-subheading">
              Generate a professional 4-week weather report for the selected city.
            </p>
          </div>
        </div>

        {/* Input Controls: Read-only City from Current Weather + Month Dropdown */}
        <form onSubmit={handleGenerateReport} className="report-controls-form">
          <div className="report-controls-grid">
            <div className="report-input-group">
              <span className="report-label">City</span>
              <div className="report-city-readonly" id="report-city-readonly">
                <span className="city-readonly-icon" aria-hidden="true">📍</span>
                <span className="city-readonly-name">{city || "Indore"}</span>
              </div>
            </div>

            <div className="report-input-group">
              <label htmlFor="report-month-select" className="report-label">
                Month
              </label>
              <select
                id="report-month-select"
                className="report-select"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                disabled={loading}
              >
                {PRESET_MONTHS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div className="report-action-group">
              <button
                type="submit"
                id="generate-weather-report-btn"
                className="generate-report-btn"
                disabled={loading || !city || !city.trim()}
              >
                {loading ? (
                  <>
                    <span className="btn-spinner" aria-hidden="true" />
                    <span>Generating Report...</span>
                  </>
                ) : (
                  <span>Generate Weather Report</span>
                )}
              </button>
            </div>
          </div>

          {/* Quick Month Selectors */}
          <div className="report-presets-row">
            <span className="presets-label">Quick month:</span>
            {["August 2026", "July 2026", "September 2026"].map((m) => (
              <button
                key={m}
                type="button"
                className={`preset-pill ${month === m ? "active" : ""}`}
                onClick={() => setMonth(m)}
                disabled={loading}
              >
                {m}
              </button>
            ))}
          </div>
        </form>

        {/* Error Notice */}
        {error && (
          <div className="report-error-banner" role="alert">
            <span className="error-icon" aria-hidden="true">⚠️</span>
            <span className="error-text">{error}</span>
          </div>
        )}

        {/* Report Display Document */}
        {report && (
          <div className="report-document-container" id="weather-report-display">
            <div className="report-document">
              {/* Document Header */}
              <div className="report-doc-header">
                <div className="doc-main-title">WEATHER REPORT</div>
                <div className="doc-meta-block">
                  <div className="doc-meta-row">
                    <span className="meta-label">City:</span>
                    <span className="meta-value" id="report-city-value">{report.city}</span>
                  </div>
                  <div className="doc-meta-row">
                    <span className="meta-label">Month:</span>
                    <span className="meta-value" id="report-month-value">{report.month}</span>
                  </div>
                </div>
              </div>

              {/* Weekly Average Temperature Section (Exactly 4 Weeks) */}
              <div className="report-doc-section">
                <h3 className="section-title">WEEKLY AVERAGE TEMPERATURE</h3>
                <div className="table-wrapper">
                  <table className="report-weekly-table">
                    <thead>
                      <tr>
                        <th scope="col">Week</th>
                        <th scope="col">Date Range</th>
                        <th scope="col">Average Temperature</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fourWeeks.map((item, idx) => (
                        <tr key={item.week || idx}>
                          <td className="week-name-cell">
                            <span className="week-name">{item.week}</span>
                            {item.note && (
                              <span className="incomplete-badge" title={item.note}>
                                {item.note}
                              </span>
                            )}
                          </td>
                          <td className="date-range-cell">{item.date_range}</td>
                          <td className="temp-cell">
                            {item.average_temperature !== null && item.average_temperature !== undefined ? (
                              <span className="temp-value">{item.average_temperature.toFixed(1)}°C</span>
                            ) : (
                              <span className="temp-missing">Unavailable</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Summary Section */}
              {report.summary && (
                <div className="report-doc-section summary-section">
                  <h3 className="section-title">SUMMARY</h3>
                  <div className="summary-narrative" id="report-summary-text">
                    {report.summary}
                  </div>
                </div>
              )}

              {/* Document Footer Branding */}
              <div className="report-doc-footer">
                <div className="footer-brand">Weather Agent</div>
                <div className="footer-doc-type">Automated Weather Report</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
