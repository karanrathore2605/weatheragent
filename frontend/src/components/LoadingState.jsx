import React from "react";

export function LoadingState({ message = "Getting weather data..." }) {
  return (
    <div className="loading-card">
      <div className="loading-spinner"></div>
      <p className="loading-text">{message}</p>
    </div>
  );
}
