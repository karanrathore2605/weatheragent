/**
 * Base API Service client for communicating with the FastAPI backend.
 *
 * Architecture Rule:
 * - Frontend strictly interacts with the backend API.
 * - External weather APIs must NEVER be called directly from frontend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Generic JSON request wrapper with error handling.
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
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const parsed = JSON.parse(errorBody);
        if (parsed.detail) {
          errorMessage = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
        }
      } catch {
        if (errorBody) errorMessage = errorBody;
      }
      throw new Error(errorMessage);
    }
    return await response.json();
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      throw new Error(`Unable to connect to backend at ${API_BASE_URL}. Ensure the backend server is running.`);
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

export default {
  getHealthStatus,
  getRootInfo,
};
