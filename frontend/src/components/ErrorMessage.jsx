import React from "react";

export function ErrorMessage({ message, onRetry }) {
  if (!message) return null;

  return (
    <div className="error-banner">
      <div className="error-content">
        <span className="error-icon">⚠️</span>
        <span className="error-message">{message}</span>
      </div>
      {onRetry && (
        <button type="button" className="btn-retry" onClick={onRetry}>
          Try Again
        </button>
      )}
    </div>
  );
}
