import React from "react";
import { getWeatherIcon } from "../utils/weatherIcons";

/**
 * CurrentWeatherCard displays real-time weather information in a 2-column layout:
 * - Left column (~58%): "CURRENT WEATHER" badge, city, location, temperature, condition, icon
 * - Right column (~42%): Compact 2x2 grid with Feels Like, Humidity, Wind, Updated, vertically centered
 */
export function CurrentWeatherCard({ data }) {
  if (!data) return null;

  const icon = getWeatherIcon(data.condition);

  // Format updated observation timestamp to clean 24-hr time (e.g. 17:00)
  const formatUpdatedTime = (timestamp) => {
    if (!timestamp) return "--";
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return timestamp;
      return date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    } catch {
      return "--";
    }
  };

  return (
    <div className="current-weather-card" id="current-weather-card">
      <div className="current-weather-grid">
        {/* Left Column: City, Address, Temperature, Condition, Weather Icon */}
        <div className="current-weather-left">
          <div className="current-weather-header">
            <span className="current-badge">CURRENT WEATHER</span>
            <h2 className="current-city">{data.city}</h2>
            {data.resolved_address && (
              <p className="current-address">{data.resolved_address}</p>
            )}
          </div>

          <div className="current-weather-temp-block">
            <div className="current-temp-row">
              <div className="current-temp-wrapper">
                <span className="current-temp">{Math.round(data.temperature)}°</span>
                <span className="current-temp-unit">C</span>
              </div>
              <div className="current-weather-icon-wrapper" aria-label={data.condition}>
                <span className="current-weather-icon">{icon}</span>
              </div>
            </div>
            <div className="current-condition-text">{data.condition}</div>
          </div>
        </div>

        {/* Right Column: Compact 2x2 Metrics Grid (Vertically Centered) */}
        <div className="current-weather-right">
          <div className="current-metrics-grid">
            <div className="current-metric-item" id="metric-feels-like">
              <div className="metric-header">
                <span className="metric-icon" aria-hidden="true">🌡️</span>
                <span className="metric-label">Feels Like</span>
              </div>
              <span className="metric-value">{Math.round(data.feels_like)}°C</span>
            </div>

            <div className="current-metric-item" id="metric-humidity">
              <div className="metric-header">
                <span className="metric-icon" aria-hidden="true">💧</span>
                <span className="metric-label">Humidity</span>
              </div>
              <span className="metric-value">{data.humidity}%</span>
            </div>

            <div className="current-metric-item" id="metric-wind">
              <div className="metric-header">
                <span className="metric-icon" aria-hidden="true">💨</span>
                <span className="metric-label">Wind</span>
              </div>
              <span className="metric-value">{data.wind_speed} km/h</span>
            </div>

            <div className="current-metric-item" id="metric-updated">
              <div className="metric-header">
                <span className="metric-icon" aria-hidden="true">🕒</span>
                <span className="metric-label">Updated</span>
              </div>
              <span className="metric-value">{formatUpdatedTime(data.observed_at)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CurrentWeatherCard;
