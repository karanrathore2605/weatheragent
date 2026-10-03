import React, { useState, useEffect, useCallback } from "react";
import {
  WeatherHeader,
  CitySearch,
  LoadingState,
  ErrorMessage,
  CurrentWeatherCard,
  WeatherSummaryCard,
  ForecastGrid,
  WeatherStatistics,
  MonthlyWeatherReport,
} from "../components";

import { getCurrentWeather, getWeatherForecast } from "../services/api";

const DEFAULT_CITY = "Indore";

export function Dashboard() {
  const [activeCity, setActiveCity] = useState(DEFAULT_CITY);
  const [currentWeather, setCurrentWeather] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchWeatherData = useCallback(async (city) => {
    if (!city || !city.trim()) {
      setError("Please enter a city.");
      return;
    }

    const trimmed = city.trim();
    setLoading(true);
    setError(null);

    try {
      // Concurrently query current conditions and 5-day forecast
      const [currentRes, forecastRes] = await Promise.all([
        getCurrentWeather(trimmed),
        getWeatherForecast(trimmed, 5),
      ]);

      setCurrentWeather(currentRes);
      setForecastData(forecastRes);
      setActiveCity(trimmed);
    } catch (err) {
      setError(err.message || "Unable to get weather information right now. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWeatherData(DEFAULT_CITY);
  }, [fetchWeatherData]);

  const handleSearch = (city) => {
    fetchWeatherData(city);
  };

  const handleRetry = () => {
    fetchWeatherData(activeCity || DEFAULT_CITY);
  };

  return (
    <div className="weather-app">
      <WeatherHeader />

      <main className="weather-main-content">
        <div className="weather-container">
          <CitySearch onSearch={handleSearch} loading={loading} />

          <ErrorMessage message={error} onRetry={handleRetry} />

          {loading && <LoadingState message="Getting weather data..." />}

          {!loading && !error && currentWeather && (
            <div className="weather-display-area">
              <CurrentWeatherCard data={currentWeather} />
              <WeatherSummaryCard
                summary={currentWeather.summary}
                status={currentWeather.summary_status}
                message={currentWeather.summary_message}
                loading={loading}
              />
              <ForecastGrid forecastData={forecastData} />
              <MonthlyWeatherReport city={activeCity} />
            </div>
          )}

        </div>
      </main>

      <footer className="weather-footer">
        <div className="weather-footer-container">
          <span>Weather Agent</span>
          <span className="footer-tag">Live meteorological forecasts</span>
        </div>
      </footer>
    </div>
  );
}
