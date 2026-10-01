import React from "react";
import { ForecastCard } from "./ForecastCard";

export function ForecastGrid({ forecastData }) {
  if (!forecastData || !forecastData.forecast || forecastData.forecast.length === 0) {
    return null;
  }

  const daysCount = forecastData.forecast.length;

  return (
    <div className="forecast-section">
      <div className="forecast-header">
        <h3 className="forecast-title">{daysCount}-Day Forecast</h3>
      </div>

      <div className="forecast-grid">
        {forecastData.forecast.map((day, idx) => (
          <ForecastCard key={day.date || idx} day={day} index={idx} />
        ))}
      </div>
    </div>
  );
}
