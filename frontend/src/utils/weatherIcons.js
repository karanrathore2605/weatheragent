/**
 * Utility to map weather condition strings to descriptive icons/emojis.
 */

export function getWeatherIcon(condition = "") {
  const normalized = condition.toLowerCase();

  if (normalized.includes("thunder") || normalized.includes("storm")) {
    return "⛈️";
  }
  if (normalized.includes("rain") || normalized.includes("shower") || normalized.includes("drizzle")) {
    return "🌧️";
  }
  if (normalized.includes("snow") || normalized.includes("flurry") || normalized.includes("ice")) {
    return "❄️";
  }
  if (normalized.includes("fog") || normalized.includes("mist") || normalized.includes("haze")) {
    return "🌫️";
  }
  if (normalized.includes("partly") || normalized.includes("scattered")) {
    return "🌤️";
  }
  if (normalized.includes("cloud") || normalized.includes("overcast")) {
    return "☁️";
  }
  if (normalized.includes("wind") || normalized.includes("breeze")) {
    return "💨";
  }
  if (normalized.includes("clear") || normalized.includes("sun")) {
    return "☀️";
  }
  return "🌤️";
}

/**
 * Format a YYYY-MM-DD date string to a friendly weekday label (e.g. 'Today', 'Fri', 'Sat').
 */
export function formatDayLabel(dateStr, index = 0) {
  if (index === 0) return "Today";
  try {
    const parts = dateStr.split("-");
    if (parts.length === 3) {
      const date = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
      return date.toLocaleDateString("en-US", { weekday: "short" });
    }
  } catch {
    // Fallback
  }
  return dateStr;
}

/**
 * Format short date (e.g. 'Oct 2').
 */
export function formatShortDate(dateStr) {
  try {
    const parts = dateStr.split("-");
    if (parts.length === 3) {
      const date = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
      return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    }
  } catch {
    // Fallback
  }
  return dateStr;
}
