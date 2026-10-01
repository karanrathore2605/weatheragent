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

6. Verify the Health Endpoint:
   - URL: [http://localhost:8000/health](http://localhost:8000/health)
   - Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

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
