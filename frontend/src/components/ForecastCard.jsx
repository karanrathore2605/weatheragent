import React from "react";
import { formatDayLabel, formatShortDate, getWeatherIcon } from "../utils/weatherIcons";

export function ForecastCard({ day, index }) {
  if (!day) return null;

  const dayLabel = formatDayLabel(day.date, index);
  const shortDate = formatShortDate(day.date);
  const icon = getWeatherIcon(day.condition);

  return (
    <div className={`forecast-card ${index === 0 ? "forecast-card-today" : ""}`}>
      <div className="forecast-card-header">
        <span className="forecast-day-name">{dayLabel}</span>
        <span className="forecast-day-date">{shortDate}</span>
      </div>

      <div className="forecast-icon">{icon}</div>

      <div className="forecast-condition">{day.condition}</div>

      <div className="forecast-temps">
        <span className="forecast-temp-max">{Math.round(day.temperature_max)}°</span>
        <span className="forecast-temp-separator">/</span>
        <span className="forecast-temp-min">{Math.round(day.temperature_min)}°</span>
      </div>

      <div className="forecast-meta">
        {day.precipitation_probability > 0 && (
          <span className="forecast-precip" title="Precipitation Probability">
            💧 {day.precipitation_probability}%
          </span>
        )}
        <span className="forecast-wind" title="Wind Speed">
          💨 {Math.round(day.wind_speed)} km/h
        </span>
      </div>
    </div>
  );
}
