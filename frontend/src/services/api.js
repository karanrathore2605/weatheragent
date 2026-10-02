/**
 * Base API Service client for communicating with the FastAPI backend.
 *
 * Architecture Rule:
 * - Frontend strictly interacts with the backend API.
 * - External weather APIs must NEVER be called directly from frontend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Generic JSON request wrapper with user-friendly error handling.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const errorBody = await response.text();
      let rawDetail = "";
      try {
        const parsed = JSON.parse(errorBody);
        rawDetail = parsed.detail || "";
      } catch {
        rawDetail = errorBody;
      }

      // Map status codes to clean user-facing error messages
      if (response.status === 404) {
        throw new Error("City not found. Please check the city name.");
      }
      if (response.status === 400) {
        if (rawDetail.toLowerCase().includes("empty")) {
          throw new Error("Please enter a city.");
        }
        throw new Error(rawDetail || "Invalid city name. Please try again.");
      }
      if (response.status === 503 || response.status === 504 || response.status === 502) {
        throw new Error("Unable to get weather information right now. Please try again.");
      }
      throw new Error(rawDetail || "Unable to get weather information right now. Please try again.");
    }
    return await response.json();
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      throw new Error("Unable to connect to backend server. Please verify backend is running.");
    }
    throw err;
  }
}

/**
 * Check backend service health status.
 * Calls GET /health
 */
export async function getHealthStatus() {
  return request("/health");
}

/**
 * Fetch root application metadata.
 * Calls GET /
 */
export async function getRootInfo() {
  return request("/");
}

/**
 * Fetch current weather for a city.
 * Calls GET /api/v1/weather/current?city=...
 */
export async function getCurrentWeather(city) {
  if (!city || !city.trim()) {
    throw new Error("Please enter a city.");
  }
  return request(`/api/v1/weather/current?city=${encodeURIComponent(city.trim())}`);
}

/**
 * Fetch multi-day weather forecast for a city.
 * Calls GET /api/v1/weather/forecast?city=...&days=...
 */
export async function getWeatherForecast(city, days = 5) {
  if (!city || !city.trim()) {
    throw new Error("Please enter a city.");
  }
  return request(`/api/v1/weather/forecast?city=${encodeURIComponent(city.trim())}&days=${days}`);
}

/**
 * Fetch meteorological statistics for a city over a defined period (week or month) and duration.
 * Calls GET /api/v1/weather/statistics?city=...&period_type=...&period_value=...
 */
export async function getWeatherStatistics(city, periodType = "week", periodValue = 1) {
  if (!city || !city.trim()) {
    throw new Error("Please enter a city.");
  }
  return request(
    `/api/v1/weather/statistics?city=${encodeURIComponent(city.trim())}&period_type=${encodeURIComponent(periodType)}&period_value=${encodeURIComponent(periodValue)}`
  );
}

export default {
  getHealthStatus,
  getRootInfo,
  getCurrentWeather,
  getWeatherForecast,
  getWeatherStatistics,
};

