import React, { useState } from "react";

import { POPULAR_CITIES } from "../utils";

export function CitySearch({ onSearch, loading }) {
  const [cityInput, setCityInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(cityInput);
  };

  const handleChipClick = (city) => {
    setCityInput(city);
    onSearch(city);
  };

  return (
    <div className="search-section">
      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="search-input"
            placeholder="Enter city (e.g. Indore, Delhi, London)..."
            value={cityInput}
            onChange={(e) => setCityInput(e.target.value)}
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          className="btn btn-search"
          disabled={loading}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      <div className="quick-chips">
        <span className="chips-label">Popular cities:</span>
        <div className="chips-list">
          {POPULAR_CITIES.map((c) => (
            <button
              key={c}
              type="button"
              className="chip-btn"
              onClick={() => handleChipClick(c)}
              disabled={loading}
            >
              {c}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
