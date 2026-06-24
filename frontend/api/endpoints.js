// @flow
/**
 * endpoints.js — Typed function wrappers for all Orchestrator API routes.
 *
 * ROUTE REGISTRY (matches backend/app/main.py + backend/app/sos.py):
 *
 *   POST /api/v1/evaluate          — EvaluationRequest  → EvaluationResponse
 *   POST /api/v1/sos/trigger       — SOSTriggerRequest  → SOSTriggerResponse
 *   POST /api/v1/sos/resolve       — SOSResolveRequest  → SOSResolveResponse
 *
 * NOTE ON ALIAS:
 *   The ROADMAP specifies `/api/v1/engine/evaluate` as the conceptual name.
 *   The live backend route is `/api/v1/evaluate`.
 *   Both names are exported here; `evaluateMetrics` uses the live route.
 *   When the backend path is updated in Sprint 2, change ROUTES.EVALUATE only.
 *
 * All callers receive the full Axios response.data object on success,
 * or a re-thrown Axios error (with .._dtx metadata attached by client.js).
 */

'use strict';

const { getInstance } = require('./client');

// ---------------------------------------------------------------------------
// Route constants — single source of truth for all backend paths
// ---------------------------------------------------------------------------
const ROUTES = {
  HEALTH:           '/health',
  EVALUATE:         '/api/v1/evaluate',              // live backend route
  EVALUATE_ALIAS:   '/api/v1/engine/evaluate',       // ROADMAP conceptual name (future)
  SOS_TRIGGER:      '/api/v1/sos/trigger',
  SOS_RESOLVE:      '/api/v1/sos/resolve',
  WEEKLY_SUMMARY:   '/api/v1/engine/weekly-summary', // Weekly aggregator
  MENTOR_CHAT:      '/api/v1/mentor/chat',           // AI Mentor Coach (Claude)
  MENTOR_HISTORY:   '/api/v1/mentor/history',        // Persisted conversation log
  HEALTH_METRICS:   '/api/v1/health/metrics',        // Wearable metrics persistence
  USER_STATE:       '/api/v1/user/state',            // Program state (computed week)
  PROGRAM_START:    '/api/v1/user/program-start',    // Set program start date
  CONTENT_TODAY:    '/api/v1/content/today',         // Daily curriculum lesson
  HEALTH_HISTORY:   '/api/v1/health/history',        // Last N days of stored metrics
};

// ---------------------------------------------------------------------------
// Health-check (used by network tests and app startup probe)
// ---------------------------------------------------------------------------

/**
 * Ping the Orchestrator health endpoint.
 * @returns {Promise<{ status: string, phase: string }>}
 */
async function healthCheck() {
  const res = await getInstance().get(ROUTES.HEALTH);
  return res.data;
}

// ---------------------------------------------------------------------------
// Core Orchestrator endpoints
// ---------------------------------------------------------------------------

/**
 * evaluateMetrics — POST /api/v1/evaluate
 *
 * Sends a daily health snapshot to the Orchestrator for clinical rule evaluation.
 * Corresponds to EvaluationRequest schema (backend/app/schemas.py).
 *
 * @param {{
 *   user_id:      string,
 *   current_week: number,
 *   sleep?:       { duration_hours: number },
 *   steps?:       { steps: number, idle_minutes: number },
 *   strength?:    { logged: boolean, duration_minutes?: number }
 * }} payload
 *
 * @returns {Promise<EvaluationResponse>}
 */
async function evaluateMetrics(payload) {
  const res = await getInstance().post(ROUTES.EVALUATE, payload);
  return res.data;
}

/**
 * triggerSOS — POST /api/v1/sos/trigger
 *
 * Fires the SOS craving protocol for a given user and week context.
 *
 * @param {{
 *   user_id:      string,
 *   week_context: number
 * }} payload
 *
 * @returns {Promise<SOSTriggerResponse>}
 */
async function triggerSOS(payload) {
  const res = await getInstance().post(ROUTES.SOS_TRIGGER, payload);
  return res.data;
}

/**
 * resolveSOS — POST /api/v1/sos/resolve
 *
 * Closes the loop on a craving event with a resolution status.
 * On LAPSE, the Orchestrator queues the morning intervention payload.
 *
 * @param {{
 *   user_id:              string,
 *   event_timestamp_utc:  string,
 *   status:               'SUCCESS' | 'LAPSE',
 *   week_context?:        number
 * }} payload
 *
 * @returns {Promise<SOSResolveResponse>}
 */
async function resolveSOS(payload) {
  const res = await getInstance().post(ROUTES.SOS_RESOLVE, payload);
  return res.data;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
/**
 * logExerciseSession — POST /api/v1/evaluate (Phase 2 exercise path)
 *
 * Logs a completed exercise session and returns Orchestrator evaluation
 * (may include GLUT4 affirmation for STRENGTH sessions).
 *
 * @param {{
 *   user_id:      string,
 *   current_week: number,
 *   exercise:     { type: 'STRENGTH'|'CARDIO', duration_minutes: number, completed: boolean }
 * }} payload
 *
 * @returns {Promise<EvaluationResponse>}
 */
async function logExerciseSession(payload) {
  const res = await getInstance().post(ROUTES.EVALUATE, payload);
  return res.data;
}

/**
 * fetchWeeklySummary — POST /api/v1/engine/weekly-summary
 *
 * Submits a batch of DailyRecord objects and receives aggregated weekly
 * statistics + an OARS reflective question in Hebrew.
 *
 * @param {{
 *   user_id:      string,
 *   current_week: number,
 *   days:         Array<DailyRecord>
 * }} payload
 *
 * @returns {Promise<WeeklySummaryResponse>}
 */
async function fetchWeeklySummary(payload) {
  const res = await getInstance().post(ROUTES.WEEKLY_SUMMARY, payload);
  return res.data;
}

/**
 * sendMentorMessage — POST /api/v1/mentor/chat
 *
 * Sends a free-text question (plus optional physiological context) to the
 * AI Mentor Coach and receives an OARS-compliant Hebrew response, optionally
 * with an action_url/action_label deep-link (recipe / exercise).
 *
 * Uses an extended 45s timeout: the LLM round-trip plus a Render free-tier
 * cold start can exceed the default 10s client timeout.
 *
 * @param {{
 *   user_id:        string,
 *   current_week:   number,
 *   free_text?:     string,
 *   sleep_hours?:   number,
 *   steps?:         number,
 *   resting_hr?:    number,
 *   baseline_rhr?:  number
 * }} payload
 *
 * @returns {Promise<{ mentor_text: string, action_url: string|null, action_label: string|null }>}
 */
async function sendMentorMessage(payload) {
  const res = await getInstance().post(ROUTES.MENTOR_CHAT, payload, { timeout: 45000 });
  return res.data;
}

/**
 * fetchMentorHistory — GET /api/v1/mentor/history
 *
 * Restores the persisted Coach conversation so the chat survives app
 * restarts. Messages come back in chronological order.
 *
 * @param {string} userId
 * @param {number} [limit=30]
 * @returns {Promise<{ user_id: string, messages: Array<{
 *   role: 'user'|'coach', content: string,
 *   action_url: string|null, action_label: string|null,
 *   created_at_utc: string }> }>}
 */
async function fetchMentorHistory(userId, limit = 30) {
  const res = await getInstance().get(ROUTES.MENTOR_HISTORY, {
    params: { user_id: userId, limit },
  });
  return res.data;
}

/**
 * saveHealthMetrics — POST /api/v1/health/metrics
 *
 * Persists the latest Health Connect sync server-side so the AI mentor can
 * read the user's sleep/steps/HR even when the chat is opened directly.
 * All metric fields optional — a partial sync only updates what it has.
 *
 * @param {{
 *   user_id:       string,
 *   metric_date?:  string,
 *   sleep_hours?:  number,
 *   steps?:        number,
 *   idle_minutes?: number,
 *   resting_hr?:   number
 * }} payload
 * @returns {Promise<Object>}
 */
async function saveHealthMetrics(payload) {
  const res = await getInstance().post(ROUTES.HEALTH_METRICS, payload);
  return res.data;
}

/**
 * fetchUserState — GET /api/v1/user/state
 * Returns program state with the current week computed live from the start date.
 * @param {string} userId
 * @returns {Promise<{ user_id: string, program_start_date: string|null,
 *   current_week: number, baseline_rhr: number|null }>}
 */
async function fetchUserState(userId) {
  const res = await getInstance().get(ROUTES.USER_STATE, { params: { user_id: userId } });
  return res.data;
}

/**
 * setProgramStart — POST /api/v1/user/program-start
 * Stores the program start date (YYYY-MM-DD); the week advances on its own.
 * @param {string} userId
 * @param {string} startDate  YYYY-MM-DD
 * @returns {Promise<{ current_week: number, program_start_date: string, stored: boolean }>}
 */
async function setProgramStart(userId, startDate) {
  const res = await getInstance().post(ROUTES.PROGRAM_START, null, {
    params: { user_id: userId, start_date: startDate },
  });
  return res.data;
}

/**
 * fetchTodayContent — GET /api/v1/content/today
 * Returns the day's curriculum lesson (text + mission + resolved image),
 * based on the user's program day. Pass a day to preview a specific one.
 * 30s timeout: the first image resolution may hit Unsplash + Render cold start.
 * @param {string} userId
 * @param {number} [day]  optional 1-91 to preview a specific day
 * @returns {Promise<Object>}
 */
async function fetchTodayContent(userId, day) {
  const params = { user_id: userId };
  if (day != null) params.day = day;
  const res = await getInstance().get(ROUTES.CONTENT_TODAY, { params, timeout: 30000 });
  return res.data;
}

/**
 * fetchHealthHistory — GET /api/v1/health/history
 * Returns the last N days of stored metrics as DailyRecord-shaped objects,
 * ready to feed the weekly summary card.
 * @param {string} userId
 * @param {number} [days=7]
 * @returns {Promise<{ user_id: string, days: Array<Object> }>}
 */
async function fetchHealthHistory(userId, days = 7) {
  const res = await getInstance().get(ROUTES.HEALTH_HISTORY, {
    params: { user_id: userId, days },
  });
  return res.data;
}

module.exports = {
  healthCheck,
  evaluateMetrics,
  logExerciseSession,
  fetchWeeklySummary,
  triggerSOS,
  resolveSOS,
  sendMentorMessage,
  fetchMentorHistory,
  saveHealthMetrics,
  fetchUserState,
  setProgramStart,
  fetchTodayContent,
  fetchHealthHistory,
  ROUTES,
};
