import React from "react";
import { getWeatherIcon } from "../utils/weatherIcons";

export function CurrentWeatherCard({ data }) {
  if (!data) return null;

  const icon = getWeatherIcon(data.condition);

  return (
    <div className="current-weather-card">
      <div className="current-weather-header">
        <div>
          <span className="current-badge">Current Weather</span>
          <h2 className="current-city">{data.city}</h2>
          {data.resolved_address && (
            <p className="current-address">{data.resolved_address}</p>
          )}
        </div>
        <div className="current-weather-icon">{icon}</div>
      </div>

      <div className="current-main">
        <div className="current-temp-wrapper">
          <span className="current-temp">{Math.round(data.temperature)}°</span>
          <span className="current-temp-unit">C</span>
        </div>
        <div className="current-condition-text">{data.condition}</div>
      </div>

      <div className="weather-details-grid">
        <div className="detail-item">
          <span className="detail-icon">🌡️</span>
          <div className="detail-info">
            <span className="detail-label">Feels like</span>
            <span className="detail-value">{Math.round(data.feels_like)}°C</span>
          </div>
        </div>

        <div className="detail-item">
          <span className="detail-icon">💧</span>
          <div className="detail-info">
            <span className="detail-label">Humidity</span>
            <span className="detail-value">{data.humidity}%</span>
          </div>
        </div>

        <div className="detail-item">
          <span className="detail-icon">💨</span>
          <div className="detail-info">
            <span className="detail-label">Wind</span>
            <span className="detail-value">{data.wind_speed} km/h</span>
          </div>
        </div>

        {data.observed_at && (
          <div className="detail-item">
            <span className="detail-icon">🕒</span>
            <div className="detail-info">
              <span className="detail-label">Updated</span>
              <span className="detail-value">
                {new Date(data.observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
