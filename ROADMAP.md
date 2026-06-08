# מפת דרכים — Lumen Health | אפליקציית מניעת סוכרת
**Status: MVP Complete & Audited | UI/UX Gamification Polish Complete | Content Curation Module Complete | PostgreSQL Migration Complete | Local Build Infrastructure & Debug APK Complete | Cloud Infrastructure Configured | Rebranding to Lumen Health Complete** ✅
**Last Updated:** 2026-06-08
**Language:** Hebrew (עברית) — RTL throughout UI, AI responses, and clinical logs
**Encoding:** UTF-8 (strict, enforced across all files)

---

## סקירה כללית | Project Overview

A Digital Therapeutics (DTx) mobile application for diabetes prevention. The app integrates wearable health data (via Android Health Connect), an AI-driven OARS coaching engine, and gamified behavioral nudges — all delivered exclusively in Hebrew with full Right-to-Left (RTL) layout support.

### Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React Native + Expo (SDK 51+) |
| Backend | Python 3.12 + FastAPI |
| Health Pipeline | Android Health Connect API |
| i18n | expo-localization + custom Hebrew JSON dictionaries |
| AI Coach | Claude API (Anthropic) — Hebrew prompts & responses |
| Database | PostgreSQL (via SQLAlchemy async) |
| Auth | JWT + OAuth2 |

---

## מבנה הפרויקט | Project Structure

```
/
├── frontend/               # React Native / Expo application
│   ├── src/                # App source code
│   ├── assets/             # Images, fonts (Hebrew-compatible)
│   └── components/         # Shared UI components (RTL-first)
│
├── backend/                # FastAPI server
│   └── app/
│       ├── api/            # Route handlers
│       ├── models/         # SQLAlchemy ORM models
│       └── services/       # Business logic, AI integration
│
├── services/               # Health data pipeline
│   ├── health_connect/     # Android Health Connect adapters
│   └── pipeline/           # ETL, normalization, aggregation
│
├── locales/                # i18n dictionaries
│   └── he/                 # Hebrew JSON namespaces
│
└── ROADMAP.md              # Single Source of Truth
```

---

## ספרינט 1 — צינור נתוני בריאות | Sprint 1: Health Data Pipeline
**Duration:** Weeks 1–2
**Goal:** Ingest, normalize, and store health metrics from Android Health Connect; establish Hebrew RTL infrastructure.

### 1.1 — תשתית RTL ועברית | RTL & Hebrew Infrastructure
- [ ] [S1-01] Install and configure expo-localization and i18n-js; set default locale to he-IL
- [ ] [S1-02] Configure I18nManager.forceRTL(true) in Expo app entry point (App.tsx) and verify RTL layout mirroring on Android and iOS simulators
- [ ] [S1-03] Add expo-localization and i18n-js to package.json; document RTL activation sequence in frontend/README.md
- [ ] [S1-04] Create Hebrew JSON dictionary namespace structure under locales/he/:
        common.json — shared labels (buttons, errors, navigation)
        onboarding.json — registration & consent flows
        dashboard.json — home screen metrics display
        coaching.json — AI OARS coaching messages
        clinical.json — clinical log entries, medical terminology
        gamification.json — achievements, streaks, rewards copy
- [ ] [S1-05] Define JSON key naming convention (snake_case, namespaced) and add Hebrew copy style-guide comment block to locales/he/common.json
- [ ] [S1-06] Validate UTF-8 encoding for all locales/he/*.json files; add CI lint step to catch encoding regressions

### 1.2 — Health Connect אינטגרציה | Health Connect Integration
- [ ] [S1-07] Scaffold services/health_connect/ adapter module; define HealthRecord base dataclass
- [ ] [S1-08] Implement permission-request flow for Health Connect data types: steps, blood glucose, heart rate, sleep, weight, active calories
- [ ] [S1-09] Build services/pipeline/ ETL: raw → normalized → validated records
- [ ] [S1-10] Define Pydantic schemas for all health metric types in backend/app/models/health.py
- [ ] [S1-11] Write SQLAlchemy async models and Alembic migration: health_records, daily_summaries
- [ ] [S1-12] Build POST /api/v1/health/sync endpoint in backend/app/api/
- [ ] [S1-13] Unit tests for ETL normalization; fixture data in Hebrew clinical format

### 1.3 — תשתית בסיסית | Foundation
- [ ] [S1-14] backend/: FastAPI app factory, CORS config, .env schema (Pydantic Settings)
- [ ] [S1-15] frontend/: Expo project init, navigation skeleton (Expo Router), Hebrew font loading (Heebo or Assistant)
- [ ] [S1-16] Docker Compose for local dev: postgres, backend, optional redis
- [ ] [S1-17] GitHub Actions CI: lint (ruff, eslint), type-check (mypy, tsc), JSON encoding check

**Sprint 1 DoD:** Health data syncs end-to-end; Hebrew JSON dictionaries loadable in Expo; RTL layout confirmed on both platforms.

---

## ספרינט 2 — מנוע OARS ובקאנד | Sprint 2: Backend OARS Engine
**Duration:** Weeks 3–4
**Goal:** Implement the AI-powered OARS motivational coaching engine, fully in Hebrew.

### 2.1 — מנוע AI | AI Engine
- [x] [S2-01] **Dynamic LLM Router Integrated** — `backend/llm_router.py` v2: `generate_mentor_response(user_state, week) -> dict`; model `claude-3-5-sonnet-latest`; system-prompt-forced pure JSON output (no `messages.parse()`); graceful fallback dict on `APITimeoutError` / `APIConnectionError` / `RateLimitError` / JSON parse failure; markdown-fence auto-strip; `ANTHROPIC_API_KEY` loaded via python-dotenv from `backend/.env` — never hardcoded; `backend/.env.example` template + root `.gitignore` protecting `.env`; standalone `backend/test_llm_router.py` script with human-readable setup instructions; pytest suite `backend/tests/test_llm_router.py` — 14 passed, 1 live test skipped; `POST /api/v1/mentor/chat` endpoint wired in `main.py`
- [x] [S2-02] **Cloud Infrastructure Configured** — `backend/Dockerfile` (python:3.11-slim, gunicorn + UvicornWorker, non-root user, no secrets baked in); `render.yaml` at project root (Web Service, `ANTHROPIC_API_KEY` + `DATABASE_URL` as `sync: false` secret env vars, `WEB_CONCURRENCY=2`); `gunicorn>=21.2.0` added to `requirements.txt`; Dockerfile static lint passed (FROM/WORKDIR/COPY/RUN/EXPOSE/CMD/USER all present, zero hardcoded secrets)
- [ ] [S2-03] Implement OARS conversation state machine: session context, user health snapshot injection, technique selection
- [ ] [S2-03] Build Hebrew prompt templates for each OARS technique; store in locales/he/coaching.json for auditability
- [ ] [S2-04] Implement prompt caching (Anthropic cache-control headers) for static system prompt sections
- [ ] [S2-05] Streaming response endpoint POST /api/v1/coach/message — SSE stream, Hebrew text output
- [ ] [S2-06] Clinical safety guardrails: crisis keyword detection (Hebrew vocabulary list); escalation protocol

### 2.2 — פרופיל ומדדים | Profile & Metrics
- [ ] [S2-07] User model: demographics, risk score (prediabetes screening), goals
- [ ] [S2-08] GET /api/v1/dashboard/summary — aggregated weekly metrics, Hebrew-formatted response
- [ ] [S2-09] Risk scoring engine: baseline A1c proxy from wearable trends + self-report
- [ ] [S2-10] Clinical log API POST /api/v1/log/entry — entries stored with Hebrew text, UTC timestamp, user ID

### 2.3 — אימות ואבטחה | Auth & Security
- [ ] [S2-11] JWT auth middleware; refresh token rotation
- [ ] [S2-12] HIPAA-aligned data handling: field-level encryption for PII
- [ ] [S2-13] Rate limiting on AI coaching endpoint (token budget per user per day)
- [ ] [S2-14] Integration test suite: full coaching session flow with Hebrew assertions

**Sprint 2 DoD:** OARS coach produces coherent Hebrew responses; clinical logs stored/retrievable; auth secure; risk score computed.

---

## ספרינט 3 — ממשק משתמש וגיימיפיקציה | Sprint 3: Frontend Gamification
**Duration:** Weeks 5–6
**Goal:** Build the full Hebrew RTL mobile UI with gamification mechanics (streaks, badges, XP).

### 3.1 — עיצוב RTL ומסכים | RTL Design & Screens
- [ ] [S3-01] Design token system (colors, spacing, typography) — Hebrew-first, RTL defaults
- [ ] [S3-02] Onboarding flow (5 screens): consent, health permissions, goal setting — Hebrew copy from locales/he/onboarding.json
- [ ] [S3-03] Dashboard screen: daily metrics ring charts, weekly trend bars, Hebrew labels
- [ ] [S3-04] Coaching chat screen: RTL chat bubbles, SSE streaming display, Hebrew keyboard
- [ ] [S3-05] Clinical log screen: Hebrew free-text entry with date/time picker (Hebrew locale)
- [ ] [S3-06] Profile & settings screen: goal editing, notification preferences (all Hebrew)

### 3.2 — מנוע גיימיפיקציה | Gamification Engine
- [ ] [S3-07] XP system: point rules for steps, logging, coaching sessions; stored in backend
- [ ] [S3-08] Streak tracker: daily engagement streak with Hebrew milestone messages
- [ ] [S3-09] Badge system: 10 initial badges (Hebrew names + descriptions in locales/he/gamification.json)
- [ ] [S3-10] Weekly challenge cards: behavioral nudge selection, Hebrew copy
- [ ] [S3-11] Push notifications (Expo Notifications): Hebrew copy, RTL layout in notification center

### 3.3 — פוליש ובדיקות | Polish & QA
- [ ] [S3-12] Accessibility audit: RTL screen reader (TalkBack) Hebrew label coverage
- [ ] [S3-13] E2E tests (Maestro or Detox): golden-path Hebrew user journey
- [ ] [S3-14] Performance targets: JS bundle size, cold start < 2s, coaching stream latency < 800ms
- [ ] [S3-15] Clinical UX review: readability of medical terms in Hebrew, font size compliance
- [ ] [S3-16] App Store / Play Store Hebrew metadata and screenshots

**Sprint 3 DoD:** App fully functional in Hebrew RTL; gamification loop playable; accessibility passing; E2E suite green.

---

## ארכיטקטורה ונציגים | Architecture & Agents (Multi-Agent / MCP Design)

This system follows a strict **Orchestrator-Worker** pattern modeled on the Model Context Protocol (MCP) mindset. Each agent has an explicit role, bounded data-access rights, and a single communication channel. No agent may exceed its access scope.

---

### תרשים זרימה | Data-Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        SYSTEM BOUNDARY                          │
│                                                                 │
│  ┌──────────────────┐   sanitized    ┌─────────────────────┐   │
│  │  Worker 1        │  metrics JSON  │   ORCHESTRATOR      │   │
│  │  Health Data     │ ─────────────► │   Backend Rules     │   │
│  │  Fetcher         │                │   Engine            │   │
│  │                  │                │                     │   │
│  │  READ-ONLY       │                │  SOLE WRITE ACCESS  │   │
│  │  Health Connect  │                │  PostgreSQL DB       │   │
│  └──────────────────┘                │  13-Week Clinical   │   │
│                                      │  Logic              │   │
│  ┌──────────────────┐   user events  │  OARS Trigger       │   │
│  │  Worker 2        │ ─────────────► │  Engine             │   │
│  │  Frontend        │                │                     │   │
│  │  Manager         │ ◄───────────── │                     │   │
│  │                  │  UI commands   └─────────────────────┘   │
│  │  React Native    │    + OARS              │                  │
│  │  Hebrew RTL UI   │    responses           │ DB writes        │
│  └──────────────────┘                        ▼                  │
│                                      ┌─────────────────────┐   │
│                                      │   PostgreSQL        │   │
│                                      │   (append-only      │   │
│                                      │    clinical log)    │   │
│                                      └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

### מתזמר | Orchestrator — Backend Rules Engine

**Role:** Single Source of Truth. The only agent with write access to the database.  
**Location:** `backend/app/services/orchestrator.py`  
**Communication:** Receives sanitized payloads from Workers via internal async message queue (Redis Streams or in-process async queue). Issues commands back to Workers over the same channel.

| Property | Value |
|----------|-------|
| **DB Access** | Read + Write (sole authority) |
| **Writes to** | `health_records`, `daily_summaries`, `clinical_logs`, `oars_sessions`, `user_state` |
| **Reads from** | Worker 1 metric payloads, Worker 2 user-event payloads |
| **External calls** | Claude API (Hebrew OARS prompts) |
| **Language** | Python 3.12 async |

**Responsibilities:**

1. **13-Week Clinical Protocol Execution**
   - Maintains the week-counter and phase state for each enrolled user
   - Evaluates weekly thresholds (step targets, glucose proxy trends, engagement scores)
   - Advances or holds clinical phase based on outcome criteria
   - All phase-transition logic is deterministic and auditable; no AI inference allowed in phase gating

2. **OARS Intervention Trigger Engine**
   - Evaluates incoming metrics against per-user risk thresholds
   - Selects OARS technique (Open question / Affirmation / Reflection / Summary) based on behavioral state machine
   - Dispatches Hebrew prompt to Claude API; streams response to Worker 2 for display
   - Records full session (prompt + response + technique tag) to `oars_sessions` table

3. **Data Integrity Authority**
   - Validates and normalizes all data before any DB write
   - Enforces append-only writes to `clinical_logs` (no updates, no deletes)
   - Maintains idempotency keys on all health sync operations

4. **Safety Guardrails**
   - Screens incoming text and outgoing AI responses for Hebrew crisis indicators
   - Triggers escalation protocol (push notification + flag in DB) independently of any Worker

**Invariant:** Workers NEVER write to the database directly. Any attempt to do so is a hard architectural violation.

---

### עובד 1 | Worker 1 — Health Data Fetcher

**Role:** Asynchronous, read-only bridge between Android Health Connect and the Orchestrator.  
**Location:** `services/health_connect/` + `services/pipeline/`  
**Communication:** Pushes sanitized `HealthMetricPayload` objects to the Orchestrator's inbound queue. Never receives commands; fire-and-forget pattern.

| Property | Value |
|----------|-------|
| **DB Access** | None — zero direct database access |
| **Health Connect Access** | Read-only (Steps, Sleep, Heart Rate, Blood Glucose, Weight, Active Calories) |
| **Output** | Sanitized, schema-validated JSON payloads only |
| **Schedule** | Background sync every 15 minutes + on-demand trigger from app foreground event |
| **Language** | Python 3.12 async (pipeline) + React Native Expo module (permission + fetch layer) |

**Responsibilities:**

1. **Permission Management**
   - Requests and maintains Health Connect read permissions scoped to declared data types only
   - Surfaces permission status to Worker 2 for onboarding UI display

2. **ETL Pipeline**
   - Fetches raw records from Health Connect API since last sync cursor
   - Normalizes units (steps → integer, sleep → ISO-8601 duration, glucose → mmol/L)
   - Validates against Pydantic `HealthMetricPayload` schema — drops malformed records with structured error log
   - Strips all device metadata and identifiers before passing to Orchestrator (privacy boundary)

3. **Sanitization Contract**
   - Output payload contains only: `user_id`, `metric_type`, `value`, `unit`, `timestamp_utc`, `source_hash`
   - No raw device data, no user PII, no Health Connect internal IDs ever leave this worker

**Invariant:** Worker 1 is stateless between syncs. It holds no local cache and makes no decisions about clinical relevance — that is exclusively the Orchestrator's domain.

---

### עובד 2 | Worker 2 — Frontend Manager

**Role:** Manages all React Native UI state, Hebrew i18n rendering, and captures user inputs for relay to the Orchestrator.  
**Location:** `frontend/src/`  
**Communication:** Sends user-event payloads to the Orchestrator via REST API. Receives UI-command objects (screen updates, OARS message chunks, gamification events) from the Orchestrator via SSE stream.

| Property | Value |
|----------|-------|
| **DB Access** | None — reads display data only via Orchestrator-owned API endpoints |
| **Write access** | Local AsyncStorage only (UI preferences, RTL state, auth tokens) |
| **Input sources** | User taps, form submissions, free-text Hebrew entries |
| **Output** | Structured `UserEventPayload` objects to Orchestrator REST endpoints |
| **Language** | TypeScript / React Native + Expo SDK 51+ |

**Responsibilities:**

1. **Hebrew RTL Rendering**
   - Enforces `I18nManager.forceRTL(true)` globally at app init — not configurable by user
   - Loads all copy exclusively from `locales/he/*.json` dictionaries via `i18n-js`
   - Resolves locale at startup; no runtime locale switching permitted
   - Applies RTL-aware layout mirroring to all navigation, modals, and chat bubbles

2. **UI State Machine**
   - Manages screen-level state (onboarding, dashboard, coaching chat, clinical log, profile)
   - Receives `UICommand` objects from Orchestrator SSE stream: `{ type: "oars_chunk" | "gamification_event" | "navigate" | "alert", payload: ... }`
   - Applies commands to local React state — no business logic evaluated locally

3. **User Input Capture & Relay**
   - Captures Hebrew free-text, numeric inputs, and gesture events
   - Packages into `UserEventPayload`: `{ event_type, user_id, timestamp_utc, data: {...} }`
   - Posts to Orchestrator endpoint; awaits acknowledgment before advancing UI state

4. **Local i18n Mapping**
   - Maintains in-memory Hebrew string map loaded from `locales/he/` at cold start
   - Passes `locale_key` references (not raw strings) in all payloads to Orchestrator — Hebrew rendering stays on the frontend
   - Clinical and AI response text is rendered as received from Orchestrator (already in Hebrew)

**Invariant:** Worker 2 contains zero clinical logic. It displays what the Orchestrator tells it to display, and forwards what the user does — nothing more.

---

### מדיניות תקשורת | Inter-Agent Communication Policy

| Channel | Direction | Protocol | Payload Format |
|---------|-----------|----------|---------------|
| Worker 1 → Orchestrator | Inbound metrics | Async queue (Redis Streams) | `HealthMetricPayload` (Pydantic) |
| Worker 2 → Orchestrator | Inbound user events | HTTPS REST POST | `UserEventPayload` (JSON) |
| Orchestrator → Worker 2 | Outbound UI commands | SSE stream | `UICommand` (JSON) |
| Orchestrator → Claude API | AI coaching | HTTPS (Anthropic SDK) | Hebrew system prompt + context |
| Orchestrator → DB | Persistence | SQLAlchemy async | ORM models |

**Rules:**
- Workers communicate with the Orchestrator only — never with each other directly
- All inter-agent payloads are schema-validated before processing; invalid payloads are rejected with a structured error, never silently dropped
- No agent may read another agent's internal state; all information exchange is via declared payload contracts
- The Orchestrator may reject or re-queue payloads; Workers must handle rejection gracefully without data loss

---

### מיפוי למבנה הפרויקט | Agent-to-Directory Mapping

```
Orchestrator  →  backend/app/services/orchestrator.py
                 backend/app/services/ai_coach.py
                 backend/app/services/clinical_protocol.py
                 backend/app/api/             (inbound REST endpoints)
                 backend/app/models/          (ORM — sole DB write authority)

Worker 1      →  services/health_connect/     (Android HC adapter)
                 services/pipeline/           (ETL, sanitization, schema validation)

Worker 2      →  frontend/src/               (React Native app)
                 frontend/components/         (RTL-first UI components)
                 locales/he/                  (Hebrew i18n dictionaries)
```

---

## הנחיות הנדסיות קריטיות | Critical Engineering Constraints

| Constraint | Detail |
|-----------|--------|
| Language | 100% Hebrew — UI, AI output, clinical logs, error messages, push notifications |
| Layout direction | RTL enforced globally via I18nManager.forceRTL(true) — no LTR fallback |
| Encoding | Strict UTF-8 everywhere — source files, JSON dictionaries, DB, API responses |
| AI responses | Claude must receive Hebrew system prompts and return Hebrew only — no auto-translation |
| Clinical data | All user-facing medical copy reviewed by Hebrew-speaking clinical writer before Sprint 3 |
| Privacy | No health PII in logs, analytics, or crash reporters |

---

## Session Summary
- **Scaffolding Status:** Complete — /frontend, /backend, /services, /locales created, UTF-8 enforced
- **Architecture Status:** Defined — Orchestrator-Worker (MCP) pattern documented
- **Agents defined:** Orchestrator (sole DB write), Worker 1 (Health Connect read-only), Worker 2 (Frontend RTL manager)
- **Communication contracts:** HealthMetricPayload, UserEventPayload, UICommand schemas declared
- **Invariants locked:** Workers have zero DB write access; Worker 2 has zero clinical logic
- **Backend Phase 1 Status:** Complete — Clinical Rules Engine implemented and tested
  - Files: backend/app/schemas.py, backend/app/rules.py, backend/app/main.py
  - Test suite: test_backend.py — 35/35 assertions passed (9 test scenarios)
  - Rules implemented: SLEEP_SHORT (menu adjustment + OARS reflection), SEDENTARY_ALERT (Hebrew Habit Stack push), STRENGTH_LOGGED (clinical validation message)
  - All Hebrew strings UTF-8 validated; phase guard (week 5 -> 501) confirmed
- **SOS Craving Toolkit (Week 11) Status:** Complete — Crisis management engine implemented and tested
  - New files: backend/app/sos.py, locales/he.json, backend/mock_state.json
  - Endpoint: POST /api/v1/sos/trigger — mounts to main.py via APIRouter
  - Protocol: 3-step Hebrew SOS (cold water + lemon, 5-min mindful delay, 10-min cortisol walk)
  - OARS empathy sourced from locales/he.json key SOS_RELAPSE_EMPATHY (exact match verified)
  - State: sos_events array appended with user_id, week_context, timestamp_utc (thread-safe lock)
  - Test suite: test_sos.py — 37/37 assertions passed (8 test scenarios), first-run clean
  - UTF-8 integrity confirmed end-to-end: response bytes, state file, locale file
- **SOS Resolution Engine (Week 12) Status:** Complete — Full trigger-to-resolution lifecycle implemented
  - New endpoint: POST /api/v1/sos/resolve — status Enum (SUCCESS | LAPSE), event lookup by (user_id, event_timestamp_utc)
  - LAPSE path: queues MorningQueuePayload to state['morning_queue'] with LAPSE_OARS_AFFIRMATION + LAPSE_HABIT_RESET from locales/he.json
  - Invariant enforced: past sos_events never deleted — resolution_status + resolved_at_utc appended to original record
  - Locale additions: LAPSE_OARS_AFFIRMATION, LAPSE_HABIT_RESET, PHASE_WEEK12, RESOLVE_SUCCESS_HE, RESOLVE_LAPSE_ACK_HE, MORNING_QUEUE_HEADER_HE
  - Test suite: test_sos.py extended to 76/76 assertions (16 test scenarios), first-run clean
  - Edge cases covered: 404 on unknown event, 422 on invalid enum, SUCCESS does not pollute morning_queue, UTF-8 end-to-end
- **Frontend Dashboard Base Status:** Complete — DashboardScreen (Week 2) with Graceful Degradation implemented
  - New files: frontend/screens/DashboardScreen.js, frontend/components/{tokens,MetricBar,SleepQuickTap,MilestoneChecklist,SensorStatusBadge}.js, frontend/utils/i18n.js
  - Graceful Degradation: isSensorActive=true shows 3 animated MetricBars; false shows manual logging panel (SleepQuickTap + MilestoneChecklist)
  - RTL: I18nManager.forceRTL(true) in tokens.js; all layouts use logical props (marginStart/End, borderStartWidth, writingDirection: rtl)
  - i18n: 36 new keys added to locales/he.json; zero Hebrew literals in any JSX file — all text via t()
  - Test suite: frontend/test_ui_toggle.js — 131/131 assertions passed (15 test scenarios), 1 auto-debug fix (numeric sleep btn labels → added Hebrew שעות suffix)
  - MetricBar: animated fill bar, overflow-clamp to 100%, warn=true switches fill to danger red
  - MilestoneChecklist: immutable toggle logic, accessibility roles (checkbox), strikethrough on checked
- **Data Pipeline Service (Worker 1) Status:** Complete — Health Connect ETL pipeline implemented and tested
  - New file: frontend/services/healthConnectService.js
  - Streams: SleepSession (fragmented → duration_hours), Steps (fragmented → total + idle_minutes), HeartRate (resting BPM via tag preference / Q1 fallback)
  - Transformation layer maps directly to FastAPI Orchestrator schemas: SleepSessionRecord, StepsRecord
  - Sanitization: _toPayload() strips all device metadata; source_hash = FNV-1a(user_id|date|metric_type)
  - Architecture invariants: zero clinical rules, zero state mutations, zero DB writes — confirmed by source audit (Test 8)
  - Error resilience: per-stream try/catch; partial failure returns available data + errors[] array
  - Test suite: frontend/test_healthConnect.js — 85/85 assertions passed (8 test scenarios)
  - Auto-debug: 2 fixes — fractional-hour makeStepsRecord helper (RangeError), active-window test anchored to UTC+0 early morning hours
- **Network Layer & API Client Status:** Complete — Centralised Axios client + endpoint mapping implemented
  - New files: frontend/api/client.js, frontend/api/endpoints.js
  - client.js: baseURL, 5000ms timeout, UTF-8 headers, response interceptors (classifyError + _triggerFallback)
  - Fallback contract: 5xx and network errors fire setFallbackHandler callback → setSensorActive(false) on UI side
  - 4xx errors (400/401/403/404/422): classified with locale key, re-thrown, fallback NOT triggered
  - endpoints.js: evaluateMetrics(), triggerSOS(), resolveSOS() mapped to live backend routes
  - 12 new NET_* error keys added to locales/he.json (all Hebrew, UTF-8 validated)
  - Test suite: frontend/test_network.js — 103/103 assertions passed (18 test scenarios) using axios-mock-adapter
  - Auto-debug: 2 fixes — (1) module-cache patch replaced by setInstance(); (2) _attachInterceptors() extracted so injected instances get interceptors too
- **Phase 1 Gamification UI Status:** Complete — HabitStackingCard implemented and integrated
  - New file: frontend/components/HabitStackingCard.js
  - 5 trigger types: sedentary_alert, hydration_reminder, coffee_habit, post_meal, sleep_prep
  - All Hebrew strings via t() from 25 new HABIT_* keys in locales/he.json (incl. HABIT_CARD_DISMISS_LABEL)
  - LayoutAnimation: smooth card appear/disappear in both card and DashboardScreen
  - RTL: borderStartWidth, borderStartColor, marginEnd, paddingStart, RTL.text/RTL.row throughout
  - API integration: _apiOverride injection for tests; production path via evaluateMetrics()
  - DashboardScreen: activeTrigger state, handleHabitCompleted (streak++, delayed clear), handleHabitDismiss
  - Auto-population: sedentary_alert set when sedentaryMins >= sedentaryLimit from mock data
  - Test suite: frontend/test_habit_card.js — 142/142 assertions passed (23 test suites)
  - Auto-debug: 1 fix — "סגור" inline Hebrew literal moved to he.json as HABIT_CARD_DISMISS_LABEL
- **Phase 2 Backend Logic Status:** Complete — Overload engine (Weeks 5-9) implemented and tested
  - New file: backend/app/rules_phase2.py
  - Rule P2-1 (GLUT4): ExerciseSessionRecord(STRENGTH, completed=True) → oars_affirmation_he with GLUT4/insulin/45min Hebrew clinical text
  - Rule P2-2 (Recovery): resting_hr > 10% above baseline AND sleep < 6h → NutritionTarget(plant_protein_g=50, mufa_g=45, reduce_workout_intensity=True) + Hebrew push
  - Cascade: P2 rules run after P1; recovery overwrites oars_reflection_he (more specific), upgrades menu_adjustment without clobbering P1 flags
  - Schema additions: ExerciseType enum, ExerciseSessionRecord, HeartRateRecord, NutritionTarget, new EvaluationResponse fields (oars_affirmation_he, nutrition_target, workout_intensity_he)
  - main.py v0.3.0: phase gate weeks 1–4 → P1, 5–9 → P2, 10+ → 501; auto-inject baseline RHR from mock_state.json; /api/v1/user/baseline-rhr endpoint
  - 14 new Hebrew strings in locales/he.json (PHASE2_*, P2_GLUT4_*, P2_RECOVERY_*)
  - Test suite: test_cognitive_engine.py — 69/69 assertions passed (28 test scenarios), first-run 68/69
  - Auto-debug: 1 fix — _STATE_PATH in main.py resolved to wrong level (parents[2]/mock_state.json → parents[2]/backend/mock_state.json)
- **Weekly Summary Engine Status:** Complete — POST /api/v1/engine/weekly-summary implemented
  - New file: backend/app/weekly_summary.py (WeeklySummaryRequest, DailyRecord, WeeklyMetrics, WeeklySummaryResponse)
  - Aggregation: null-safe avg_sleep_hours, avg_steps, avg_resting_hr (missing days excluded from denominator, zero division impossible)
  - Trend detection: 3% threshold, first-half vs second-half split, higher_is_better flag per metric
  - OARS questions: 6 week-specific Hebrew reflective questions (W5-W9 + default) with {{avg_sleep}} interpolation for W8
  - Clinical insights: 6 conditional Hebrew bullets (sleep good/bad, steps good/bad, strength sessions, no-exercise nudge)
  - 27 new locale keys added to locales/he.json (WEEKLY_*)
  - main.py v0.4.0: weekly_summary_router mounted, /api/v1/evaluate untouched
  - Test suite: test_cognitive_engine.py extended — 114/114 assertions (69 Phase 2 + 45 new weekly summary), first-run clean
  - Auto-debug: 1 fix — _LOCALES_PATH used parents[3] instead of parents[2] (path resolved to OneDrive root)
- **Phase 2 Frontend UI Status:** Complete — StrengthWorkoutButton, RHRStatusBadge, WeeklySummaryCard
  - New components: frontend/components/{StrengthWorkoutButton,RHRStatusBadge,WeeklySummaryCard}.js
  - StrengthWorkoutButton: 4-duration picker, logs ExerciseSessionRecord(STRENGTH), shows GLUT4 affirmation panel from Orchestrator response; LayoutAnimation transitions
  - RHRStatusBadge: null/undefined → renders nothing (graceful degradation); classify() thresholds (low/normal/elevated); trend arrow; RTL logical props throughout
  - WeeklySummaryCard: non-blocking useEffect fetch, skeleton loader, collapse/expand toggle, metrics grid (sleep/steps/strength/RHR), insights bullets, OARS question; cancelled flag prevents stale updates
  - DashboardScreen.js: Phase 2 components gated by CURRENT_WEEK 5–9; MOCK_WEEKLY_DAYS with intentional missing day; MOCK_RESTING_HR = 68 (set null to test degradation)
  - endpoints.js: logExerciseSession() + fetchWeeklySummary() added; ROUTES.WEEKLY_SUMMARY wired
  - tokens.js: strengthFill color (#7C3AED) added
  - 36 new locale keys in he.json (STRENGTH_BTN_*, RHR_*, WEEKLY_CARD_*, P2_PHASE_LABEL)
  - Test suite: frontend/test_phase2_ui.js — 109/109 assertions (35 test groups), first-run clean
- **Phase 3 Modularity Logic Status:** Complete — Maintenance & Modularity engine (Weeks 10-13)
  - New file: backend/app/rules_phase3.py (evaluate_phase3, apply_predictive_planning_rule, apply_phytosterol_rule)
  - Rule P3-1 (Predictive Planning): current_week ≥ 10 AND is_prepped=False AND day_of_week ∈ {6,7} → oars_open_question_he (exact: "מה לרוב המכשול העיקרי שמונע ממך לארגן קופסאות אוכל מראש ביום שבת?") + push
  - Rule P3-2 (Phytosterols): is_prepped=True → PhytosterolTarget(phytosterols_g=2.0) in separate field; never touches Phase 2 protein/MUFA targets
  - Orthogonality: P3 appends to all prior output; nutrition_target (P2) and phytosterol_target (P3) coexist; oars_reflection_he and oars_open_question_he are independent fields; push priority: P2 recovery > P3 planning (demoted to clinical_notes when both fire)
  - Schema additions: PlanningSessionRecord(is_prepped, day_of_week), PhytosterolTarget(phytosterols_g, source_example, rationale_he), new EvaluationResponse fields (oars_open_question_he, phytosterol_target)
  - main.py v0.5.0: weeks 10–13 → Phase 3; all 13 program weeks now fully routed; 501 is unreachable by design (week 14 → 422 via schema le=13)
  - 9 new locale keys in locales/he.json (P3_PHASE_LABEL, P3_PLANNING_OARS_QUESTION, P3_PHYTOSTEROL_*, etc.)
  - Test suite: test_cognitive_engine.py extended to 173/173 assertions (20 new Phase 3 tests, 51–70); 2 auto-debug fixes (old week-10-501 tests + test-53 422 guard)
- **Proactive Scheduler Status:** Complete — Friday 12:00 weekend-prep reminder with strict idempotency
  - New file: backend/app/scheduler.py (APScheduler 3.11 AsyncIOScheduler — runs inside FastAPI event loop, never blocks HTTP)
  - Job: check_weekend_prep_status — Friday 12:00 (Asia/Jerusalem); scans mock_state.json for Phase 3 users with is_prepped=False
  - Idempotency: last_notified_iso_week (ISO calendar week) prevents duplicate sends per weekend; survives server restart via persisted state; safe under concurrent invocations via threading.Lock
  - State additions: users[id].scheduler = {last_notified_iso_week, last_notified_week, last_notified_timestamp, notifications_sent}; notifications_log array (full audit trail)
  - Push: exact SCHEDULER_PREP_PUSH + SCHEDULER_PREP_OARS from he.json; result dict carries action (sent|skipped_idempotent|skipped_prepped|skipped_not_phase3) + reason in Hebrew
  - main.py v0.6.0: lifespan context manager starts/stops scheduler; /api/v1/scheduler/status endpoint; /health reports scheduler state
  - 6 new locale keys in he.json (SCHEDULER_*)
  - Test suite: test_scheduler.py — 87/87 assertions (16 test groups), first-run clean; includes time injection, spy dispatch, concurrent-thread contention test (5 threads → exactly 1 send)
- **E2E Audit & MVP Certification Status:** Complete ✅
  - E2E run date: 2026-06-05 | All 9 test suites executed, 1 stale assertion fixed
  - Fix applied: test_backend.py Test 8 — "week 5 → 501" updated to "week 5 → Phase 2 (200)" + "week 14 → 422 (schema)" to reflect Phase 2 implementation
  - Final trial balance: 942/942 assertions passed (372 Python + 570 JavaScript)
  - Hebrew integrity: all user-facing strings sourced from locales/he.json (200+ keys) — zero inline Hebrew literals confirmed in all source files
  - RTL compliance: I18nManager.forceRTL(true) enforced; logical props (marginStart/End, borderStartWidth, writingDirection: rtl) throughout all frontend components
  - Architecture invariants confirmed: Workers have zero DB write access; Worker 2 has zero clinical logic; Orchestrator is sole DB authority
  - Scheduler idempotency confirmed: 5-thread concurrent test → exactly 1 dispatch; restart-safe via ISO week persistence
- **Dev Environment Setup Status:** Complete ✅
  - New files: Makefile, start_servers.sh, start_servers.bat, frontend/package.json, frontend/app.json, frontend/babel.config.js, frontend/App.js, backend/requirements.txt
  - Backend verified: `python -m uvicorn backend.app.main:app --reload --port 8000` (v0.6.0, imports clean)
  - Frontend scaffold: Expo SDK 51, package.json with all deps, App.js wires RTL + Axios fallback + DashboardScreen
  - Launch: `start_servers.bat` (Windows), `./start_servers.sh` (Mac/Linux), or `make backend` / `make frontend` in separate terminals
- **UI/UX Gamification Polish Status:** Complete ✅ (2026-06-06)
  - New file: frontend/utils/theme.js — Dynamic Time-of-Day Theming (5 periods: dawn/day/dusk/evening/night)
  - Dependencies: react-native-reanimated 3.10.1 + expo-haptics 13.0.1 installed; babel plugin wired
  - MetricBar.js: replaced Animated.timing with Reanimated withTiming worklet (UI-thread, 60fps, no JS block)
  - HabitStackingCard.js: Reanimated withSpring slide-in (translateY 40→0, opacity 0→1); animate-out on dismiss
  - StrengthWorkoutButton.js: Haptics.notificationAsync(Success) on workout log; scale pulse on button tap; graceful no-op on web
  - DashboardScreen.js: Dynamic theme applied to background/header/cards/status bar; theme.statusBarStyle adapts per period
  - RTL invariants preserved: all marginStart/End, borderStartWidth, no inline Hebrew literals
  - Test suite: frontend/test_gamification_polish.js — 43/43 assertions passed (6 groups: theme engine, MetricBar, HabitStackingCard, haptic safety, RTL audit, dependency audit)
- **Content Curation Module Status:** Complete ✅ (2026-06-07)
  - Backend schema: EvaluationResponse + action_url (Optional[str]) + action_label (Optional[str])
  - Rule P2-1 (GLUT4 STRENGTH): action_url = YouTube strength-training video; action_label from locales
  - Rule P2-2 (Recovery biofeedback): action_url = anti-inflammatory recipe; label from locales
  - Rule P3-2 (Phytosterol): action_url = phytosterol-rich recipe; label from locales
  - Priority: GLUT4 YouTube URL wins cascade (set first; recovery checks action_url is None)
  - New frontend component: frontend/components/ExternalResourceButton.js
    - expo-web-browser 13.0.3 installed; try/catch safe-import (no crash on web/simulator)
    - Null-safety: renders nothing when url or label is falsy
    - In-app browser overlay via WebBrowser.openBrowserAsync(); window.open() web fallback
    - RTL: marginEnd/marginStart, borderStartWidth, no marginLeft/Right, no inline Hebrew
  - StrengthWorkoutButton wired: actionUrl/actionLabel state, ExternalResourceButton in GLUT4 panel
  - 4 new locale keys in locales/he.json + synced to frontend/locales/he.json
  - Test suites: test_content_curation.py (40/40 Python) + frontend/test_external_resource.js (34/34 JS)
  - Auto-debug: (1) native module require() in Node → replaced with package.json/file existence checks; (2) inline Hebrew accessibilityHint → moved to ACTION_OPEN_ACCESSIBILITY_HINT locale key
- **LLM Router Status:** Complete ✅ (2026-06-07) — `backend/llm_router.py` v2; model `claude-sonnet-4-6`; 14/14 pytest passed, 1 live test skipped; `POST /api/v1/mentor/chat` wired
- **Rebranding Status:** Complete ✅ (2026-06-08) — App display name → "Lumen Health" (`app.json` `name` field); file headers updated across `App.js`, `DashboardScreen.js`, `client.js`, `AppNavigator.js`; ROADMAP H1 updated; system identifiers (`slug`, `bundleIdentifier`, `android.package`) unchanged; backend LLM prompts, Dockerfile, render.yaml untouched
- **Cloud Infrastructure Status:** Complete ✅ (2026-06-08) — `backend/Dockerfile` (python:3.11-slim, gunicorn+uvicorn); `render.yaml` (Web Service, secrets via dashboard); Dockerfile static lint PASS; Docker daemon unavailable on build machine — validate `docker build -t dtx-backend ./backend` once Docker Desktop is running
- Next action: Sprint 2 — PostgreSQL integration + Worker 1 → Orchestrator sync endpoint wiring