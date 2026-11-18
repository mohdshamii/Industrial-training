# EstateIQ AI — Smart Real Estate Intelligence Platform

**EstateIQ AI** is a full-stack, AI-powered real estate intelligence SaaS platform built with Python, Flask, SQLAlchemy, Chart.js, Leaflet.js, and ReportLab. It transforms an existing scikit-learn house price prediction project into a production-ready real estate advisory suite while **100% preserving** the original trained machine learning model, encoder, feature order, dataset, and Jupyter Notebook.

---

## Table of Contents

1. [Platform Vision & Core Capabilities](#1-platform-vision--core-capabilities)
2. [Design System & Visual Identity](#2-design-system--visual-identity)
3. [Preserved Machine Learning Pipeline](#3-preserved-machine-learning-pipeline)
4. [Free Public APIs (Zero API Key Required)](#4-free-public-apis-zero-api-key-required)
5. [Optional Personal Free-Tier AI API Keys](#5-optional-personal-free-tier-ai-api-keys)
6. [Project Architecture & Directory Structure](#6-project-architecture--directory-structure)
7. [REST API Reference](#7-rest-api-reference)
8. [Installation & Running Locally](#8-installation--running-locally)
9. [Environment Configuration (.env)](#9-environment-configuration-env)
10. [Production Deployment (Windows, Linux, Docker, PostgreSQL)](#10-production-deployment-windows-linux-docker-postgresql)
11. [Security & Performance Architecture](#11-security--performance-architecture)
12. [Automated Testing](#12-automated-testing)
13. [Disclaimers & Statistical Transparency](#13-disclaimers--statistical-transparency)

---

## 1. Platform Vision & Core Capabilities

EstateIQ AI goes far beyond single-number house price inference by giving homebuyers, sellers, renters, and investors an integrated decision suite:

### AI House Price Valuation Studio (`/predict`)
- Dynamic input form mapped strictly to all **11 authentic model features** (expanded to 37 features via the preserved `OneHotEncoder`).
- Optional **OpenStreetMap Nominatim location tagger** that attaches verified coordinates and a nearby facility snapshot to any valuation and its PDF dossier.
- Instant output in **INR** (converted from the model's native USD output using live cached USD/INR exchange rates) alongside native **USD**.
- **Statistically Valid Ensemble Spread**: Extracts individual predictions from all 10 `DecisionTreeRegressor` estimators inside `best_house_price_model.pkl` to display the empirical minimum, interquartile range (25th–75th percentile), point estimate, maximum, standard deviation, and Coefficient of Variation (CV%). Never fabricates arbitrary accuracy or confidence claims.
- **Counterfactual Valuation Drivers**: Perturbs each input individually against the historical dataset median/mode while holding other inputs constant to explain exactly how each feature shifts the estimate in INR.
- Persistent prediction history with reload, save-to-portfolio, delete, and one-click PDF download.

### Multi-Property Comparison Engine (`/compare`)
- Compare **2 to 4 properties** side-by-side by loading saved valuations or configuring custom structural specs.
- Compares Estimated Price (INR & USD), 10-Tree Ensemble Range, Price per Sq Ft, Lot Area, Basement Footprint, Year Built, Condition Rating, Building Type, Zoning, Estimated Monthly EMI, Structural Suitability Score (transparent weighted formula), and optional Gross/Net Rental Yield (computed only when user-supplied rent is entered).
- Interactive Chart.js **Valuation Bar Chart** and **Multi-Axis Structural Radar Chart**.

### Location Intelligence & Amenity Radar (`/map`)
- Full interactive **Leaflet.js** map with dark/light Carto & OpenStreetMap tiles synced automatically to the active theme.
- Live **Nominatim geocoding** search, click-to-inspect anywhere on the map, and configurable scan radius (1.5 km / 3.0 km / 5.0 km).
- Live **Overpass API** scanning across **8 nearby facility categories** with Haversine distance calculations (km) and category filter pills:
  - Schools, Hospitals, Metro Stations, Railway Stations, Shopping Malls, Restaurants, Parks, and Airports.
- Live **Open-Meteo weather telemetry** (current temperature, humidity, wind speed, WMO condition, and 3-day outlook).
- **Location-to-Location Infrastructure Comparison** (pin up to 3 neighborhoods side-by-side) and user **Favorite Location Bookmarks**.

### Smart Investment Analytics & Dataset Benchmarks (`/analytics`)
Clearly separates **Calculated Financial Scenarios** (based on user inputs) from **Historical Dataset Benchmarks**:
1. **EMI & Down Payment Calculator**: Monthly EMI, upfront cash (down payment + stamp duty/registration), total interest, and year-by-year principal/interest stacked amortization chart.
2. **Rental Yield Calculator**: Gross yield %, Net yield % (accounting for vacancy, maintenance, and property tax), payback years, and cash-flow donut chart.
3. **ROI & Cash-on-Cash Return Calculator**: Leveraged net equity, cumulative cash flow, total ROI %, annualized equity CAGR, and Year-1 Cash-on-Cash %.
4. **Loan Affordability Calculator**: Maximum affordable monthly EMI, eligible loan, maximum property budget, and conservative safe budget based on FOIR.
5. **Buy vs. Rent Simulator**: Multi-year net-worth trajectory comparing homeownership against renting + investing upfront cash and monthly savings, including break-even year detection.
6. **Property Appreciation Scenario Simulator**: Conservative, Moderate, and Optimistic compound growth curves over 1–30 years.
7. **Historical Training Dataset Benchmarks**: Real distributions computed directly from `HousePricePrediction.xlsx` (N=1,460 actual recorded sales) — Price Distribution Histogram, Median Price by Construction Decade, Building Type, and Zoning Classification.

### AI Real Estate Advisor (`/assistant`)
- Context-aware conversational advisor bound automatically to the user's latest ML valuation, recent comparisons, and favorite locations.
- Answers valuation explanations, fair-value/overpriced diagnostics, buy-vs-rent math, 10-year appreciation scenarios, property comparisons, and neighborhood/zoning evaluation frameworks.
- Powered out-of-the-box by a **free public zero-key AI endpoint** with seamless fallback to the built-in **Quantitative Local Analytical Engine** and optional personal free-tier LLM keys (`Gemini`, `Groq`, `OpenRouter`).

### Personalized User Dashboard (`/dashboard`) & RBAC Admin Console (`/admin`)
- User authentication (`Flask-Login`, salted password hashing), profile & currency preferences, saved properties, recently viewed valuations, favorite locations, and prediction history.
- Role-based Admin Console (`@admin_required`) displaying total users, total predictions, 14-day activity chart, popular property types chart, most searched locations, API usage latency & telemetry logs, system health checks, cache clearing, and user role management.

### Executive PDF Valuation Reports (`/api/predictions/<id>/report.pdf`)
- Multi-section ReportLab PDF dossier featuring KPI valuation summary, all 11 model specifications, embedded vector Feature Impact bar chart, verified ML model metrics, illustrative financing & 10-year appreciation scenarios, nearby amenities table (when tagged), and legal/statistical disclaimers.

---

## 2. Design System & Visual Identity

EstateIQ AI uses an exclusive, high-contrast luxury SaaS palette restricted strictly to **four colors**:
- **Black** (`#050507`, `#0B0C10`, `#12141B`) — Obsidian dark-mode surfaces and light-mode typography
- **White** (`#FFFFFF`, `#F6F8FC`) — Crisp light-mode canvas and high-legibility dark-mode text
- **Royal Blue** (`#1D4ED8`, `#2563EB`, `#60A5FA`) — Primary interactive actions, charts, focus rings, and data accents
- **Sovereign Gold** (`#D4AF37`, `#B8860B`, `#F2D16B`) — Valuation highlights, active states, premium badges, and secondary chart series

Design principles:
- **Zero Emojis**: Every icon across the UI, maps, alerts, and reports uses crisp inline **SVG** graphics (`1.75px–2px` stroke).
- **Dark Mode & Light Mode**: Persisted in `localStorage` with zero-FOUC initialization; automatically updates CSS variables, Chart.js theming, and Leaflet basemaps (Carto Dark Matter / OpenStreetMap Standard).
- **Typography**: `Plus Jakarta Sans`, `Inter`, and `JetBrains Mono` (`tabular-nums`) for aligned financial figures and coordinates.

---

## 3. Preserved Machine Learning Pipeline

All original training artifacts remain untouched in the project root:

| Artifact | Role | Preserved Status |
| :--- | :--- | :--- |
| `best_house_price_model.pkl` | `RandomForestRegressor(n_estimators=10, random_state=0)` | Untouched (read-only) |
| `onehot_encoder.pkl` | `OneHotEncoder(sparse_output=False, handle_unknown='ignore')` | Untouched (read-only) |
| `feature_columns.pkl` | Exact 37-column feature ordering from training | Untouched (read-only) |
| `HousePricePrediction.xlsx` | Source Ames Housing dataset (2,919 rows; 1,460 labeled prices) | Untouched (read-only) |
| `house_price_prediction.ipynb` | Original EDA, preprocessing, and model selection notebook | Untouched |
| `legacy_streamlit_app.py` | Backup copy of the original Streamlit prototype (`app.py`) | Preserved backup |

### Exact 11 Model Input Features (37 One-Hot Encoded)

| Feature | Type | Allowed Range / Categories | Global Importance |
| :--- | :--- | :--- | :--- |
| `TotalBsmtSF` | Numeric | `0 – 10,000` sq ft | 31.68% |
| `LotArea` | Numeric | `500 – 300,000` sq ft | 18.61% |
| `YearBuilt` | Numeric | `1872 – 2026` | 18.17% |
| `YearRemodAdd` | Numeric | `1950 – 2026` | 8.85% |
| `Exterior1st` | Categorical (15) | `AsbShng`, `AsphShn`, `BrkComm`, `BrkFace`, `CBlock`, `CemntBd`, `HdBoard`, `ImStucc`, `MetalSd`, `Plywood`, `Stone`, `Stucco`, `VinylSd`, `Wd Sdng`, `WdShing` | 8.51% |
| `MSSubClass` | Numeric Code | `20, 30, 40, 45, 50, 60, 70, 75, 80, 85, 90, 120, 150, 160, 180, 190` | 4.21% |
| `OverallCond` | Numeric Rating | `1 – 9` | 4.03% |
| `LotConfig` | Categorical (5) | `Corner`, `CulDSac`, `FR2`, `FR3`, `Inside` | 2.88% |
| `BsmtFinSF2` | Numeric | `0 – 5,000` sq ft (`<= TotalBsmtSF`) | 1.44% |
| `MSZoning` | Categorical (5) | `C (all)`, `FV`, `RH`, `RL`, `RM` | 1.21% |
| `BldgType` | Categorical (5) | `1Fam`, `2fmCon`, `Duplex`, `Twnhs`, `TwnhsE` | 0.43% |

### Audited Validation Metrics (Reproduced from Original 80/20 Split, `random_state=0`)
- **Validation MAPE**: `18.50%` (exact match to notebook `0.1850`)
- **Validation MAE**: `$30,749.85`
- **Validation RMSE**: `$44,608.80`
- **Validation R-squared**: `0.2641` *(reflects mean-imputation of 1,459 missing `SalePrice` rows in the source notebook)*

---

## 4. Free Public APIs (Zero API Key Required)

Every external capability works out-of-the-box with **free, public, zero-key APIs**, backed by persistent SQLite/PostgreSQL caching (`ApiCache`) and graceful offline fallbacks:

| Capability | Public API Provider | Endpoint | Key Required | Cache TTL & Policy |
| :--- | :--- | :--- | :--- | :--- |
| **Live USD to INR FX** | ExchangeRate-API Open Access | `https://open.er-api.com/v6/latest/USD` | No | 6 hours (`frankfurter.app` backup + offline fallback) |
| **Backup FX** | Frankfurter (ECB Data) | `https://api.frankfurter.app/latest?from=USD&to=INR` | No | 6 hours |
| **Geocoding** | OpenStreetMap Nominatim | `https://nominatim.openstreetmap.org/search` | No | 24 hours + 1 req/sec throttle + custom `User-Agent` |
| **Nearby Facilities** | Overpass API (+ Kumi mirror) | `https://overpass-api.de/api/interpreter` | No | 24 hours across 8 facility categories |
| **Live Weather** | Open-Meteo Forecast API | `https://api.open-meteo.com/v1/forecast` | No | 30 minutes (current + 3-day outlook) |
| **AI Chat (Default)** | Pollinations Public Text API | `https://text.pollinations.ai/openai` | No | 12s timeout + automatic Local Analytical Fallback |

---

## 5. Optional Personal Free-Tier AI API Keys

If you prefer dedicated rate limits on your own free-tier LLM provider, copy `.env.example` to `.env` and set **any one** of the following (keys are read exclusively on the backend and never exposed to frontend JavaScript):

1. **Google Gemini Free Tier** (`GEMINI_API_KEY`) — Obtain free key at `https://aistudio.google.com/apikey` (default model: `gemini-2.0-flash`).
2. **Groq Free Tier** (`GROQ_API_KEY`) — Obtain free key at `https://console.groq.com/keys` (default model: `llama-3.3-70b-versatile`).
3. **OpenRouter Free Models** (`OPENROUTER_API_KEY`) — Obtain free key at `https://openrouter.ai/keys` (default model: `meta-llama/llama-3.3-70b-instruct:free`).

**Provider Priority Order**: `Gemini` -> `Groq` -> `OpenRouter` -> `Pollinations Public Free AI (No Key)` -> `EstateIQ Local Analytical Engine`.

---

## 6. Project Architecture & Directory Structure

```text
house price prediction/
├── app.py                        # Flask application factory, extensions, security headers, health endpoint
├── wsgi.py                       # Production WSGI entry point (Waitress / Gunicorn)
├── config.py                     # Environment-driven configuration (dev, test, prod)
├── requirements.txt              # Pinned virtual environment dependencies
├── .env.example                  # Environment variables template (no secrets committed)
├── .gitignore                    # Ignores .venv, .env, SQLite DB, generated PDFs, caches
├── pytest.ini                    # Pytest configuration
├── Procfile                      # Render / Heroku process definition
├── Dockerfile                    # Production container specification
├── README.md                     # Detailed platform documentation
│
├── best_house_price_model.pkl    # Preserved RandomForestRegressor (n_estimators=10)
├── onehot_encoder.pkl            # Preserved OneHotEncoder (4 categorical features)
├── feature_columns.pkl           # Preserved 37-feature column order
├── HousePricePrediction.xlsx     # Preserved source dataset
├── house_price_prediction.ipynb  # Preserved training notebook
├── legacy_streamlit_app.py       # Backup of original Streamlit app.py
│
├── database/
│   ├── __init__.py               # SQLAlchemy, Flask-Login, CSRFProtect, Limiter instances
│   └── models.py                 # ORM models (User, Prediction, SavedProperty, FavoriteLocation, ChatMessage, ApiUsageLog, ApiCache)
│
├── services/
│   ├── __init__.py               # Persistent API cache & API usage telemetry helpers
│   ├── prediction_service.py     # ML inference, 10-tree uncertainty spread, counterfactual factor attribution
│   ├── market_service.py         # Live USD->INR FX & real dataset statistical benchmarks
│   ├── geolocation_service.py    # Nominatim geocoding, Overpass 8-category POIs, Haversine, Open-Meteo weather
│   ├── investment_service.py     # EMI, Rental Yield, ROI, Affordability, Buy vs Rent, Appreciation Simulator
│   ├── ai_service.py             # Multi-provider AI Advisor (Gemini/Groq/OpenRouter/Public AI/Local Fallback)
│   └── report_service.py         # ReportLab PDF valuation report generator with vector charts
│
├── routes/
│   ├── __init__.py               # Session token helper & @admin_required RBAC decorator
│   ├── auth.py                   # Register, Login, Logout, Profile & Password management
│   ├── dashboard.py              # Landing overview & personalized User Dashboard
│   ├── prediction.py             # Valuation UI, prediction REST APIs, history, save, PDF export
│   ├── properties.py             # Comparison Engine, Location Map, Geocode/Overpass/Weather/Bookmark APIs
│   ├── analytics.py              # Investment Calculators & Dataset Market Intelligence APIs
│   ├── chatbot.py                # AI Advisor UI & conversational REST APIs
│   └── admin.py                  # RBAC Admin Dashboard, telemetry stats, cache clear, role management
│
├── templates/                    # Jinja2 responsive templates (base, index, dashboard, prediction, comparison, map, analytics, chatbot, admin, login, register, profile, error)
├── static/
│   ├── css/style.css             # White, Black, Blue & Gold design system (Dark + Light modes)
│   └── js/                       # Modular frontend scripts (app.js, prediction.js, comparison.js, map.js, analytics.js)
├── reports/                      # Generated PDF dossiers (gitignored)
└── tests/
    └── test_estateiq.py          # End-to-end automated pytest verification suite
```

---

## 7. REST API Reference

| Method | Endpoint | Description | Auth / Rate Limit |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Service & ML model readiness check | Public |
| `GET` | `/api/predict/schema` | Returns all 11 model features, valid categories, and verified metrics | Public |
| `POST` | `/api/predict` | Runs preserved ML model, returns INR/USD, 10-tree spread, factors, saves record | Public / 60/hr |
| `GET` | `/api/predictions/history` | Lists recent predictions for current user or guest session | Public |
| `GET`/`DELETE` | `/api/predictions/<id>` | Fetch or delete a valuation record | Owner / Admin |
| `POST` | `/api/predictions/<id>/save` | Save valuation into user's portfolio (`SavedProperty`) | Login Required |
| `GET` | `/api/predictions/<id>/report.pdf` | Generates and downloads executive ReportLab PDF report | Owner / Admin |
| `POST` | `/api/properties/compare` | Side-by-side comparison for 2 to 4 properties | Public / 60/hr |
| `GET` | `/api/geocode?q=...` | OpenStreetMap Nominatim location search (cached + throttled) | Public / 45/hr |
| `GET` | `/api/nearby?lat=...&lon=...&radius=...` | Overpass API nearby amenities across 8 categories + Amenity Index | Public / 35/hr |
| `GET` | `/api/weather?lat=...&lon=...` | Open-Meteo current weather + 3-day outlook | Public / 60/hr |
| `GET`/`POST`/`DELETE` | `/api/locations/favorite` | Manage user's bookmarked map neighborhoods | Login Required |
| `POST` | `/api/analytics/emi` | EMI, Down Payment, Stamp Duty & Annual Amortization Schedule | Public |
| `POST` | `/api/analytics/rental-yield` | Gross & Net Rental Yield + Payback Period | Public |
| `POST` | `/api/analytics/roi` | Leveraged ROI, Net Equity & Cash-on-Cash Return | Public |
| `POST` | `/api/analytics/affordability` | Maximum Eligible Home Loan & Property Budget (FOIR) | Public |
| `POST` | `/api/analytics/buy-vs-rent` | Multi-year Buy vs. Rent net-worth comparison + break-even year | Public |
| `POST` | `/api/analytics/appreciation` | Conservative / Moderate / Optimistic appreciation scenarios | Public |
| `GET` | `/api/market/dataset-insights` | Historical benchmarks computed from `HousePricePrediction.xlsx` | Public |
| `GET` | `/api/market/fx` | Cached live USD to INR exchange rate | Public |
| `POST` | `/api/chat` | Context-aware AI Real Estate Advisor chat | Public / 45/hr |
| `GET`/`DELETE` | `/api/chat/history` | Retrieve or clear chat history | Public |
| `GET` | `/api/admin/stats` | Platform KPIs, 14-day activity, API telemetry, user list | Admin Only |
| `POST` | `/api/admin/cache/clear` | Flush cached external API entries | Admin Only |
| `POST` | `/api/admin/users/<id>/role` | Promote or demote user RBAC role | Admin Only |

---

## 8. Installation & Running Locally

### Windows (PowerShell)

The workspace already includes a configured `.venv` virtual environment with `scikit-learn==1.3.2` and all dependencies installed.

```powershell
# Run immediately using the existing virtual environment
.\.venv\Scripts\python app.py
```

If setting up from scratch on a fresh machine:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

### Default Development Admin Credentials
- **Email**: `admin@estateiq.ai`
- **Password**: `Admin@EstateIQ2026` *(change via `.env` before deploying to production)*

---

## 9. Environment Configuration (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `FLASK_ENV` | `development` | `development`, `testing`, or `production` |
| `SECRET_KEY` | Dev fallback | Set a strong 64-char random secret in production |
| `DATABASE_URL` | `sqlite:///instance/estateiq.db` | Swap to `postgresql://user:pass@host:5432/estateiq` for PostgreSQL |
| `ENABLE_PUBLIC_AI` | `true` | Enables zero-key Pollinations public AI endpoint |
| `GEMINI_API_KEY` | *(blank)* | Optional free-tier Google Gemini API key |
| `GROQ_API_KEY` | *(blank)* | Optional free-tier Groq API key |
| `OPENROUTER_API_KEY` | *(blank)* | Optional free-tier OpenRouter API key |
| `DEFAULT_USD_TO_INR` | `84.50` | Offline fallback reference exchange rate if FX APIs are unreachable |
| `NOMINATIM_USER_AGENT` | `EstateIQ-AI/1.0 (...)` | Custom User-Agent header required by OpenStreetMap policy |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | See above | Initial seeded administrator account credentials |

---

## 10. Production Deployment (Windows, Linux, Docker, PostgreSQL)

### Windows Server (Waitress)
```powershell
.\.venv\Scripts\waitress-serve --host=0.0.0.0 --port=5000 wsgi:app
```

### Linux / Render / Railway (Gunicorn)
```bash
pip install gunicorn
gunicorn --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT wsgi:app
```

### Docker
```bash
docker build -t estateiq-ai .
docker run -p 5000:5000 --env-file .env estateiq-ai
```

### Migrating from SQLite to PostgreSQL
1. Install `psycopg2-binary` (`pip install psycopg2-binary`).
2. Set `DATABASE_URL=postgresql://username:password@host:5432/estateiq` in `.env`.
3. Restart the app — SQLAlchemy automatically creates all normalized tables on startup.

---

## 11. Security & Performance Architecture

- **CSRF Protection**: Enabled globally via `Flask-WTF` (`X-CSRFToken` header for JSON APIs and hidden token fields for HTML forms).
- **Authentication & Passwords**: Salted cryptographic hashes via Werkzeug (`generate_password_hash` / `check_password_hash`), `HttpOnly` & `SameSite=Lax` session cookies, RBAC enforcement via `@admin_required`.
- **Rate Limiting**: Endpoint-specific limits via `Flask-Limiter` on auth, predictions, geocoding, Overpass, and AI chat.
- **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Zero Client-Side Secret Leakage**: All optional API keys stay strictly on the server inside environment variables.
- **Persistent API Caching**: External FX, Nominatim, Overpass, and Open-Meteo responses are cached in `ApiCache` to prevent rate-limit exhaustion and speed up repeat queries.

---

## 12. Automated Testing

Run the complete automated `pytest` suite covering routes, preserved ML inference, validation rules, PDF generation, property comparison, all 6 investment calculators, contextual AI fallback, auth/RBAC isolation, and zero-emoji compliance:

```powershell
.\.venv\Scripts\pytest -v
```

---

## 13. Disclaimers & Statistical Transparency

1. **Valuation Scope**: Estimates are produced by the preserved `RandomForestRegressor` trained on historical Ames Housing USD records (`HousePricePrediction.xlsx`) and converted to INR via transparent FX rates. They are not certified real estate appraisals or live local MLS listings.
2. **Uncertainty Methodology**: Displayed price ranges represent the empirical dispersion across all 10 decision trees in the Random Forest ensemble, reported alongside the verified out-of-sample validation MAPE (`18.50%`).
3. **Financial Simulators**: All EMI, rental yield, ROI, affordability, buy-vs-rent, and appreciation outputs are deterministic mathematical scenarios derived strictly from user assumptions and must not be construed as financial or investment advice.
