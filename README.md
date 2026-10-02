# Weather Forecast Agent

A production-oriented, agentic weather forecasting application built with a modern decoupled architecture.

## Architecture Overview

```
weather-agent/
│
├── backend/                  # FastAPI Backend Application
│   ├── app/
│   │   ├── config/           # Environment configuration & settings
│   │   ├── routers/          # API endpoint routes (Router layer)
│   │   ├── services/         # Business logic layer
│   │   ├── agents/           # LangGraph Agent orchestration (Future branches)
│   │   ├── tools/            # Agent tool definitions (Future branches)
│   │   ├── clients/          # External API clients (e.g. Weather, Email)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── models/           # Database / ORM models
│   │   ├── repositories/     # Data access layer
│   │   ├── prompts/          # Agent prompt templates & system instructions
│   │   ├── database/         # Database connection & session management
│   │   └── utils/            # Utility functions and structured logger
│   ├── tests/                # Automated backend test suite
│   ├── requirements.txt      # Python dependencies
│   ├── .env.example          # Backend environment variable template
│   └── .gitignore
│
├── frontend/                 # React Frontend Application (Vite)
│   ├── src/
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # View pages / screens
│   │   ├── services/         # API client & communication services
│   │   ├── hooks/            # Custom React hooks
│   │   ├── context/          # State management context providers
│   │   ├── utils/            # Frontend helper utilities
│   │   ├── App.jsx           # Minimal application shell
│   │   └── main.jsx          # React application entry point
│   ├── public/               # Static assets
│   ├── package.json          # Node.js dependencies & scripts
│   └── .env.example          # Frontend environment variable template
│
├── README.md
└── .gitignore
```

### Architectural Layering Rules

```
Router  ──►  Service  ──►  Client / Repository
Agent   ──►  Tool     ──►  Service  ──►  Client
```
- **Schemas vs Models**: Pydantic schemas (data transfer & validation) are strictly isolated from database models.
- **Decoupled Frontend & Backend**: The React frontend communicates strictly via the REST API; it never calls external weather APIs directly.

---

## Getting Started

### 1. Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+ (with `npm`)

---

### 2. Backend Setup & Run

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create environment file:
   ```bash
   # Windows
   copy .env.example .env

   # Linux / macOS
   cp .env.example .env
   ```

5. Run the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. Verify Endpoints:
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)
   - Current Weather: [http://localhost:8000/api/v1/weather/current?city=Indore](http://localhost:8000/api/v1/weather/current?city=Indore)
   - 5-Day Forecast: [http://localhost:8000/api/v1/weather/forecast?city=Indore&days=5](http://localhost:8000/api/v1/weather/forecast?city=Indore&days=5)
   - Weather Statistics: [http://localhost:8000/api/v1/weather/statistics?city=Indore&period=week](http://localhost:8000/api/v1/weather/statistics?city=Indore&period=week)
   - Weather Summary (LLM): [http://localhost:8000/api/v1/weather/statistics/summary?city=Indore&period=week](http://localhost:8000/api/v1/weather/statistics/summary?city=Indore&period=week)
   - Interactive OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

7. Run Backend Tests:
   ```bash
   pytest
   ```

---

### 3. Frontend Setup & Run

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Create environment file:
   ```bash
   # Windows
   copy .env.example .env

   # Linux / macOS
   cp .env.example .env
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

5. Open your browser:
   - Application URL: [http://localhost:5173](http://localhost:5173)

---

## Weather Statistics System

A production-grade, deterministic meteorological statistics system powered by persistent observations and database aggregations.

### Architecture Flow

```
Weather API
    ↓
Weather Client
    ↓
Weather Service
    ↓
Observation Repository
    ↓
Database (SQLAlchemy)
    ↓
Statistics Service
    ↓
Statistics Router
    ↓
Frontend Dashboard
```

### Deterministic Calculations (No LLM for Math)

Numerical metrics are computed deterministically in backend code:
- **Average Temperature**: `sum(temperatures) / valid_temperature_count`
- **Minimum Temperature**: `min(temperatures)`
- **Maximum Temperature**: `max(temperatures)`
- **Average Feels-Like**: `sum(feels_like) / valid_feels_like_count`
- **Average Humidity**: `sum(humidity) / valid_humidity_count`
- **Average Wind Speed**: `sum(wind_speed) / valid_wind_speed_count`
- **Total Precipitation**: `sum(valid_precipitation_amounts)`
- **Data Coverage**: `(valid_observations / expected_period_hours) * 100`

Missing or null values are safely ignored rather than falsely assumed as zero. LLMs are never used for numerical math.

### Data Availability & Provider Limitations

> **Important Provider Limitation**:
> The Google Weather API's hourly historical data endpoint provides a maximum of **up to 24 hours** of historical observations. It **does NOT** provide full historical data for past weeks, months, or years directly.
>
> To solve this reliably in production:
> 1. Weather observations are automatically captured and persisted in the application database whenever live weather queries occur.
> 2. Observations are uniquely deduplicated by `(city, observed_at)`.
> 3. The system enforces a configurable **Minimum Data Coverage Threshold** (`MIN_STATISTICS_COVERAGE=70.0%`).
> 4. If the database has insufficient records for the requested period (coverage < 70%), the system returns a structured `insufficient_data` response with available ranges, rather than fabricating data or presenting misleading zeros.

### Supported Aggregation Periods

The system calculates statistics over calendar-based UTC periods:
- **`week`**: Current ISO calendar week (Monday 00:00:00 UTC to Sunday 23:59:59 UTC, 168 expected hourly observations).
- **`month`**: Current calendar month (1st day 00:00:00 UTC to last day 23:59:59 UTC).
- **`year`**: Current calendar year (January 1 00:00:00 UTC to December 31 23:59:59 UTC).

### API Specification

#### Endpoint

```http
GET /api/v1/weather/statistics?city={city}&period={week|month|year}
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | Yes | — | Target city name (e.g. `Indore`, `London`, `Tokyo`) |
| `period` | string | No | `week` | Statistical horizon: `week`, `month`, or `year` |

#### Example 1: Successful Response (Coverage ≥ 70%)

```bash
curl -X GET "http://localhost:8000/api/v1/weather/statistics?city=Indore&period=week"
```

```json
{
  "status": "success",
  "city": "Indore",
  "period": "week",
  "start_date": "2026-09-28",
  "end_date": "2026-10-04",
  "average_temperature": 28.4,
  "minimum_temperature": 23.1,
  "maximum_temperature": 33.7,
  "average_feels_like_temperature": 30.1,
  "average_humidity": 61.2,
  "average_wind_speed": 11.8,
  "total_precipitation": 12.4,
  "observation_count": 135,
  "coverage_percent": 80.4,
  "available_from": null,
  "available_to": null,
  "message": null
}
```

#### Example 2: Insufficient Data Response (Coverage < 70%)

```bash
curl -X GET "http://localhost:8000/api/v1/weather/statistics?city=Indore&period=year"
```

```json
{
  "status": "insufficient_data",
  "city": "Indore",
  "period": "year",
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "average_temperature": null,
  "minimum_temperature": null,
  "maximum_temperature": null,
  "average_feels_like_temperature": null,
  "average_humidity": null,
  "average_wind_speed": null,
  "total_precipitation": null,
  "observation_count": 24,
  "coverage_percent": 0.3,
  "available_from": "2026-10-01",
  "available_to": "2026-10-02",
  "message": "Not enough historical weather data is available for the requested period."
}
```

### Database Configuration & Abstraction

The persistence layer is built on **SQLAlchemy 2.0+** using environment-based configuration:

```env
# SQLite (default development)
DATABASE_URL="sqlite:///./weatheragent.db"

# PostgreSQL (production drop-in)
# DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/weatheragent"
```

#### Weather Observation Database Model

| Field | Type | Modifiers | Description |
|-------|------|-----------|-------------|
| `id` | Integer | Primary Key, Auto-increment | Observation unique identifier |
| `city` | String(100) | Indexed, Not Null | Normalized city name |
| `latitude` | Float | Not Null | Geocoded latitude |
| `longitude` | Float | Not Null | Geocoded longitude |
| `observed_at` | DateTime (UTC) | Indexed, Not Null | Observation timestamp |
| `temperature` | Float | Not Null | Recorded temperature (°C) |
| `feels_like_temperature` | Float | Nullable | Perceived temperature (°C) |
| `humidity` | Float | Nullable | Relative humidity percentage |
| `precipitation` | Float | Nullable, Default 0.0 | Precipitation amount (mm) |
| `wind_speed` | Float | Nullable | Wind speed (km/h) |
| `pressure` | Float | Nullable | Atmospheric pressure (hPa) |
| `weather_condition` | String(100) | Nullable | Text condition description |
| `source` | String(50) | Not Null, Default `google` | Origin provider |
| `created_at` | DateTime (UTC) | Not Null | Record creation timestamp |

- **Deduplication Constraint**: `UniqueConstraint("city", "observed_at", name="uq_city_observed_at")`
- **Composite Index**: `Index("ix_weather_obs_city_observed_at", "city", "observed_at")`

---

## Groq LLM Weather Summarization System

A production-grade, natural-language summarization layer powered by **Groq Cloud LLMs** (`groq` Python SDK) built on top of deterministic meteorological statistics.

### Architectural Flow

```
                      USER
                        ↓
                    FRONTEND
                        ↓
               STATISTICS API ROUTER
                        ↓
               STATISTICS SERVICE
                        ↓
                    DATABASE
                        ↓
            DETERMINISTIC CALCULATION
                        ↓
            STRUCTURED WEATHER METRICS
                        ↓
                   LLM SERVICE
                        ↓
                   GROQ CLIENT
                        ↓
             GROQ MODEL (e.g. LLaMA 3.3)
                        ↓
             NATURAL LANGUAGE SUMMARY
                        ↓
                    FRONTEND
                        ↓
                      USER
```

### Strict Separation of Responsibilities

1. **Deterministic Backend Math**:
   - The LLM **NEVER** computes mathematical metrics (averages, minimums, maximums, totals, observation counts, or coverage percentages).
   - The backend `StatisticsService` deterministically queries the database and computes statistical values in Python.
2. **Groq Language Generation**:
   - Groq is strictly responsible for synthesizing the already-calculated, structured metrics into concise, friendly, natural-language prose.
   - Structured JSON is fed into the LLM — no loose string concatenations.
3. **Controlled System Prompting & Prompt Injection Safety**:
   - System prompts are fixed and non-overridable.
   - User city inputs are sanitized to alphanumeric text, preventing prompt injection attacks.
4. **Insufficient Data Protection**:
   - If historical observations fall below the minimum coverage threshold (`status = "insufficient_data"`), **Groq is NOT called**.
   - A friendly explanatory message is returned directly without wasting LLM tokens or summarizing incomplete datasets.
5. **Fault-Tolerant Fallback (`partial_success`)**:
   - If Groq encounters an API error, invalid API key, network timeout, or rate limiting, the system catches the failure gracefully.
   - The endpoint returns `status = "partial_success"` with the complete, valid deterministic statistics intact, along with a helpful notification. LLM outages never break core weather capabilities.

### Groq Configuration

Set the following environment variables in `backend/.env`:

```env
GROQ_API_KEY="gsk_your_groq_api_key_here"
GROQ_MODEL="llama-3.3-70b-versatile"
LLM_TIMEOUT_SECONDS=15.0
LLM_TEMPERATURE=0.2
```

> **Security Note**: Never commit `.env` or hardcode API keys in source code. Do not expose `GROQ_API_KEY` to the React frontend.

### API Specification

#### Endpoint

```http
GET /api/v1/weather/statistics/summary?city={city}&period={week|month|year}
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | Yes | — | Target city name (e.g. `Indore`, `London`) |
| `period` | string | No | `week` | Statistical horizon: `week`, `month`, or `year` |

#### Example 1: Full Success (`status = "success"`)

```bash
curl -X GET "http://localhost:8000/api/v1/weather/statistics/summary?city=Indore&period=week"
```

```json
{
  "status": "success",
  "city": "Indore",
  "period": "week",
  "statistics": {
    "city": "Indore",
    "period": "week",
    "start_date": "2026-09-28",
    "end_date": "2026-10-04",
    "average_temperature": 28.4,
    "minimum_temperature": 23.1,
    "maximum_temperature": 33.7,
    "average_feels_like_temperature": 30.1,
    "average_humidity": 61.2,
    "average_wind_speed": 11.8,
    "total_precipitation": 12.4,
    "observation_count": 135,
    "coverage_percent": 80.4
  },
  "summary": "This week in Indore, temperatures averaged 28.4°C with a range between 23.1°C and 33.7°C. Humidity averaged around 61%, and total precipitation reached 12.4 mm.",
  "message": null
}
```

#### Example 2: Partial Success / Groq Fallback (`status = "partial_success"`)

```json
{
  "status": "partial_success",
  "city": "Indore",
  "period": "week",
  "statistics": {
    "city": "Indore",
    "period": "week",
    "start_date": "2026-09-28",
    "end_date": "2026-10-04",
    "average_temperature": 28.4,
    "minimum_temperature": 23.1,
    "maximum_temperature": 33.7,
    "average_feels_like_temperature": 30.1,
    "average_humidity": 61.2,
    "average_wind_speed": 11.8,
    "total_precipitation": 12.4,
    "observation_count": 135,
    "coverage_percent": 80.4
  },
  "summary": null,
  "message": "Weather statistics are available, but the AI summary could not be generated right now."
}
```

#### Example 3: Insufficient Data (`status = "insufficient_data"`)

```json
{
  "status": "insufficient_data",
  "city": "Indore",
  "period": "year",
  "statistics": null,
  "summary": null,
  "message": "Not enough historical weather data is available to calculate a reliable yearly average yet."
}
```

### Frontend User-Triggered Experience

- **User-Triggered Execution**: Historical statistics and LLM summaries are **not** requested automatically when the page loads.
- **Workflow**:
  1. The user selects a **City** and chooses a **Period** (`Week`, `Month`, or `Year`).
  2. The user clicks **`[ Calculate Average ]`**.
  3. A loading indicator displays: `"Analyzing weather data..."` with duplicate-click protection.
  4. The result card displays the natural-language summary alongside structured metric cards (Average Temperature, Range, Humidity, Precipitation, Wind Speed, and Data Coverage).

---

## Testing

Backend test suites use `pytest` with mocked external APIs (no real Google Weather or Groq API calls in tests):

```bash
# Run all unit and integration tests
pytest

# Run Groq client and LLM service unit tests
pytest tests/weather/test_groq_llm_service.py

# Run end-to-end Weather Summary integration tests
pytest tests/weather/test_weather_summary_integration.py
```

---

## Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_NAME` | `Weather Forecast Agent API` | Service name |
| `APP_ENV` | `development` | Deployment environment |
| `PORT` | `8000` | Backend HTTP port |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `GOOGLE_WEATHER_API_KEY` | `""` | Google Maps / Weather API Key |
| `DATABASE_URL` | `sqlite:///./weatheragent.db` | SQLAlchemy database connection URI |
| `MIN_STATISTICS_COVERAGE` | `70.0` | Minimum observation coverage threshold (%) |
| `GROQ_API_KEY` | `""` | Groq Cloud API Authentication Key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq LLM model name (configurable) |
| `LLM_TIMEOUT_SECONDS` | `15.0` | Request timeout for Groq API calls |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature for factual summaries |


