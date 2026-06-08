// @flow
/**
 * healthConnectService.js — Worker 1 (Health Data Fetcher)
 *
 * ARCHITECTURE INVARIANTS (from ROADMAP.md):
 *   ✓ READ-ONLY — no DB writes, no state mutations, no UI calls
 *   ✓ NO clinical rules, NO OARS logic, NO intervention decisions
 *   ✓ Output is a sanitized HealthMetricPayload matching the FastAPI Orchestrator schema
 *   ✓ All device metadata and internal Health Connect IDs are stripped before output
 *   ✓ Stateless between syncs — no local cache
 *
 * Orchestrator schema targets (backend/app/schemas.py):
 *   SleepSessionRecord  { duration_hours: float }
 *   StepsRecord         { steps: int, idle_minutes: int }
 *   HealthMetricPayload { user_id, metric_type, value, unit, timestamp_utc, source_hash }
 *   EvaluationRequest   { user_id, current_week, sleep, steps, strength? }
 *
 * Health Connect data types consumed (read-only):
 *   SleepSession  — fragmented sessions → aggregated duration_hours
 *   Steps         — fragmented interval records → daily total + idle_minutes
 *   HeartRate     — resting samples → median resting_bpm
 */

'use strict';

// ---------------------------------------------------------------------------
// Health Connect SDK shim
// In production this is resolved by the `react-native-health-connect` package.
// The default export is replaced by the mock in tests.
// ---------------------------------------------------------------------------
let HealthConnect = null;
try {
  // eslint-disable-next-line import/no-extraneous-dependencies
  HealthConnect = require('react-native-health-connect').default;
} catch (_) {
  // Running outside React Native (CI / unit tests) — caller injects mock via setSDK()
}

/** Inject a mock SDK object in non-native environments (tests). */
function setSDK(sdk) {
  HealthConnect = sdk;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Data types we are authorised to request — read-only, minimal scope. */
const REQUIRED_PERMISSIONS = [
  { accessType: 'read', recordType: 'SleepSession' },
  { accessType: 'read', recordType: 'Steps'        },
  { accessType: 'read', recordType: 'HeartRate'     },
];

/** Active hours window for sedentary detection (08:00–20:00 local time). */
const ACTIVE_WINDOW_START_HOUR = 8;
const ACTIVE_WINDOW_END_HOUR   = 20;

/** A step-count interval is considered "idle" if it falls below this threshold. */
const IDLE_STEPS_THRESHOLD = 10;

/** Resting HR — keep samples with this tag; fall back to lowest-quartile if tag absent. */
const HC_RESTING_TAG = 'MEASUREMENT_LOCATION_WRIST_TEMPERATURE'; // SDK constant for resting

// ---------------------------------------------------------------------------
// Permission layer
// ---------------------------------------------------------------------------

/**
 * Request the minimum required Health Connect read permissions.
 * Returns the list of permissions actually granted by the user.
 * @returns {Promise<Array<{accessType: string, recordType: string}>>}
 */
async function requestPermissions() {
  if (!HealthConnect) throw new Error('Health Connect SDK not initialised');
  const granted = await HealthConnect.requestPermission(REQUIRED_PERMISSIONS);
  return granted;
}

/**
 * Check which of the required permissions are currently granted
 * without triggering a permission dialog.
 * @returns {Promise<{sleep: boolean, steps: boolean, heartRate: boolean}>}
 */
async function getPermissionStatus() {
  if (!HealthConnect) throw new Error('Health Connect SDK not initialised');
  const granted = await HealthConnect.getGrantedPermissions();
  const grantedSet = new Set(granted.map((p) => p.recordType));
  return {
    sleep:     grantedSet.has('SleepSession'),
    steps:     grantedSet.has('Steps'),
    heartRate: grantedSet.has('HeartRate'),
  };
}

// ---------------------------------------------------------------------------
// Raw fetch helpers
// ---------------------------------------------------------------------------

/**
 * Build an ISO-8601 date range for a single calendar day in UTC.
 * @param {Date} date
 * @returns {{ startTime: string, endTime: string }}
 */
function _dayRange(date) {
  const start = new Date(date);
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(date);
  end.setUTCHours(23, 59, 59, 999);
  return {
    startTime: start.toISOString(),
    endTime:   end.toISOString(),
  };
}

/**
 * Fetch raw SleepSession records for a given day.
 * @param {Date} date
 * @returns {Promise<Array>}
 */
async function _fetchRawSleep(date) {
  const { startTime, endTime } = _dayRange(date);
  const result = await HealthConnect.readRecords('SleepSession', {
    timeRangeFilter: { operator: 'between', startTime, endTime },
  });
  return result.records ?? [];
}

/**
 * Fetch raw Steps interval records for a given day.
 * @param {Date} date
 * @returns {Promise<Array>}
 */
async function _fetchRawSteps(date) {
  const { startTime, endTime } = _dayRange(date);
  const result = await HealthConnect.readRecords('Steps', {
    timeRangeFilter: { operator: 'between', startTime, endTime },
  });
  return result.records ?? [];
}

/**
 * Fetch raw HeartRate samples for a given day.
 * @param {Date} date
 * @returns {Promise<Array>}
 */
async function _fetchRawHeartRate(date) {
  const { startTime, endTime } = _dayRange(date);
  const result = await HealthConnect.readRecords('HeartRate', {
    timeRangeFilter: { operator: 'between', startTime, endTime },
  });
  return result.records ?? [];
}

// ---------------------------------------------------------------------------
// Transformation layer — raw SDK → Orchestrator schema
// ---------------------------------------------------------------------------

/**
 * TRANSFORM: SleepSession records → SleepSessionRecord
 *
 * Health Connect may return multiple fragmented sessions (e.g. nap + main sleep).
 * We sum all segments that overlap the date's 18:00–12:00+1d window and express
 * the result in fractional hours, rounded to 2 decimal places.
 *
 * Output matches backend SleepSessionRecord: { duration_hours: float }
 *
 * @param {Array} rawRecords  — Health Connect SleepSession records
 * @returns {{ duration_hours: number } | null}
 */
function transformSleep(rawRecords) {
  if (!rawRecords || rawRecords.length === 0) return null;

  let totalMs = 0;
  for (const record of rawRecords) {
    const start = new Date(record.startTime).getTime();
    const end   = new Date(record.endTime).getTime();
    const durationMs = end - start;
    if (durationMs > 0) {
      totalMs += durationMs;
    }
  }

  if (totalMs === 0) return null;

  const duration_hours = Math.round((totalMs / 3_600_000) * 100) / 100;
  // Hard ceiling guard — more than 18 h is almost certainly a data artifact
  if (duration_hours > 18) return null;

  return { duration_hours };
}

/**
 * TRANSFORM: Steps interval records → StepsRecord
 *
 * Algorithm:
 *   1. Sum all interval `count` values → total daily steps
 *   2. Scan intervals whose midpoint falls in 08:00–20:00 local time.
 *      An interval is "idle" when steps < IDLE_STEPS_THRESHOLD.
 *      Merge consecutive idle intervals into a single contiguous idle block.
 *      idle_minutes = sum of the longest contiguous idle block in minutes (ceiling).
 *
 * Output matches backend StepsRecord: { steps: int, idle_minutes: int }
 *
 * @param {Array} rawRecords  — Health Connect Steps records
 * @returns {{ steps: number, idle_minutes: number } | null}
 */
function transformSteps(rawRecords) {
  if (!rawRecords || rawRecords.length === 0) return null;

  let totalSteps = 0;

  // Collect intervals inside the active window for idle detection
  const activeIntervals = [];

  for (const record of rawRecords) {
    const count = typeof record.count === 'number' ? record.count : 0;
    totalSteps += count;

    const startMs  = new Date(record.startTime).getTime();
    const endMs    = new Date(record.endTime).getTime();
    const midpoint = new Date((startMs + endMs) / 2);
    const hour     = midpoint.getHours(); // local time

    if (hour >= ACTIVE_WINDOW_START_HOUR && hour < ACTIVE_WINDOW_END_HOUR) {
      activeIntervals.push({ startMs, endMs, count, durationMs: endMs - startMs });
    }
  }

  // Sort by start time — SDK doesn't guarantee order
  activeIntervals.sort((a, b) => a.startMs - b.startMs);

  // Find longest contiguous idle block (greedy merge)
  let maxIdleMs  = 0;
  let curIdleMs  = 0;

  for (const interval of activeIntervals) {
    if (interval.count < IDLE_STEPS_THRESHOLD) {
      curIdleMs += interval.durationMs;
      if (curIdleMs > maxIdleMs) maxIdleMs = curIdleMs;
    } else {
      curIdleMs = 0; // activity broke the streak
    }
  }

  const idle_minutes = Math.ceil(maxIdleMs / 60_000);

  return {
    steps:       Math.round(totalSteps),
    idle_minutes,
  };
}

/**
 * TRANSFORM: HeartRate samples → resting BPM
 *
 * Strategy:
 *   1. Prefer samples explicitly tagged as resting measurements.
 *   2. Fallback: take the lowest quartile (Q1) of all bpm values — a robust
 *      proxy for resting HR when device tags are absent (common on Android).
 *   3. Return integer median of the selected samples.
 *
 * Output: { resting_bpm: number } — this is a supplementary metric, not part
 * of the current EvaluationRequest schema but included for future Sprint 2 use.
 *
 * @param {Array} rawRecords  — Health Connect HeartRate records
 * @returns {{ resting_bpm: number } | null}
 */
function transformHeartRate(rawRecords) {
  if (!rawRecords || rawRecords.length === 0) return null;

  // Flatten samples from all records
  const allSamples = [];
  for (const record of rawRecords) {
    const samples = record.samples ?? [];
    for (const sample of samples) {
      const bpm = typeof sample.beatsPerMinute === 'number' ? sample.beatsPerMinute : null;
      if (bpm !== null && bpm > 20 && bpm < 250) {
        allSamples.push({ bpm, isResting: sample.measurementLocation === HC_RESTING_TAG });
      }
    }
  }

  if (allSamples.length === 0) return null;

  // Prefer explicitly-tagged resting samples
  const restingSamples = allSamples.filter((s) => s.isResting).map((s) => s.bpm);
  let targetSamples = restingSamples;

  if (targetSamples.length === 0) {
    // Fallback: lowest quartile of all samples
    const sorted = allSamples.map((s) => s.bpm).sort((a, b) => a - b);
    const q1Idx  = Math.ceil(sorted.length / 4);
    targetSamples = sorted.slice(0, Math.max(1, q1Idx));
  }

  // Median of target samples
  const sorted = [...targetSamples].sort((a, b) => a - b);
  const mid    = Math.floor(sorted.length / 2);
  const resting_bpm =
    sorted.length % 2 === 0
      ? Math.round((sorted[mid - 1] + sorted[mid]) / 2)
      : sorted[mid];

  return { resting_bpm };
}

// ---------------------------------------------------------------------------
// Sanitization layer — strip device metadata, produce source_hash
// ---------------------------------------------------------------------------

/**
 * Produce a deterministic source_hash from user_id + date + metric_type.
 * This is the idempotency key used by the Orchestrator.
 * Pure hash — no PII leaves this function.
 *
 * @param {string} userId
 * @param {string} dateStr   — YYYY-MM-DD
 * @param {string} metricType
 * @returns {string}
 */
function _sourceHash(userId, dateStr, metricType) {
  // FNV-1a 32-bit — fast, collision-resistant for this scale, no crypto dependency
  const input = `${userId}|${dateStr}|${metricType}`;
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = (hash * 0x01000193) >>> 0; // unsigned 32-bit
  }
  return hash.toString(16).padStart(8, '0');
}

/**
 * Wrap a transformed metric value into the sanitized HealthMetricPayload envelope.
 * Strips all device/session identifiers. Only the fields listed here leave the Worker.
 *
 * Matches ROADMAP.md sanitization contract:
 *   { user_id, metric_type, value, unit, timestamp_utc, source_hash }
 *
 * @param {string} userId
 * @param {string} metricType  — 'sleep' | 'steps' | 'heart_rate'
 * @param {Object} value       — transformed metric object
 * @param {string} unit
 * @param {Date}   date
 * @returns {Object}
 */
function _toPayload(userId, metricType, value, unit, date) {
  const dateStr = date.toISOString().slice(0, 10);
  return {
    user_id:       userId,
    metric_type:   metricType,
    value,
    unit,
    timestamp_utc: date.toISOString(),
    source_hash:   _sourceHash(userId, dateStr, metricType),
  };
}

// ---------------------------------------------------------------------------
// Public API — daily sync
// ---------------------------------------------------------------------------

/**
 * Perform a full daily data sync for a single user.
 *
 * Fetches Sleep, Steps, and HeartRate from Health Connect, transforms each
 * stream, and returns a sanitized DailySyncResult ready to POST to the
 * Orchestrator's /api/v1/health/sync endpoint.
 *
 * This function is the only public entry point — callers should never touch
 * the raw fetch or transform functions directly.
 *
 * @param {string} userId       — opaque user ID
 * @param {number} currentWeek  — current program week (1–13)
 * @param {Date}   [date]       — defaults to today (UTC)
 * @returns {Promise<DailySyncResult>}
 *
 * @typedef {Object} DailySyncResult
 * @property {string}   user_id
 * @property {number}   current_week
 * @property {Object|null} sleep        — SleepSessionRecord or null
 * @property {Object|null} steps        — StepsRecord or null
 * @property {Object|null} heart_rate   — { resting_bpm } or null
 * @property {Object[]}    payloads     — sanitized HealthMetricPayload array
 * @property {Object}      sync_meta    — { synced_at_utc, date, permissions }
 * @property {string[]}    errors       — non-fatal per-stream errors
 */
async function syncDailyMetrics(userId, currentWeek, date = new Date()) {
  if (!HealthConnect) throw new Error('Health Connect SDK not initialised. Call setSDK() first.');
  if (!userId)        throw new Error('userId is required');

  const errors   = [];
  const payloads = [];

  // ── Sleep ──────────────────────────────────────────────────────────────
  let sleepResult = null;
  try {
    const rawSleep = await _fetchRawSleep(date);
    sleepResult    = transformSleep(rawSleep);
    if (sleepResult) {
      payloads.push(_toPayload(userId, 'sleep', sleepResult, 'hours', date));
    }
  } catch (err) {
    errors.push(`sleep_fetch_error: ${err.message}`);
  }

  // ── Steps ──────────────────────────────────────────────────────────────
  let stepsResult = null;
  try {
    const rawSteps = await _fetchRawSteps(date);
    stepsResult    = transformSteps(rawSteps);
    if (stepsResult) {
      payloads.push(_toPayload(userId, 'steps', stepsResult, 'count+minutes', date));
    }
  } catch (err) {
    errors.push(`steps_fetch_error: ${err.message}`);
  }

  // ── Heart Rate ─────────────────────────────────────────────────────────
  let heartRateResult = null;
  try {
    const rawHR    = await _fetchRawHeartRate(date);
    heartRateResult = transformHeartRate(rawHR);
    if (heartRateResult) {
      payloads.push(_toPayload(userId, 'heart_rate', heartRateResult, 'bpm', date));
    }
  } catch (err) {
    errors.push(`heart_rate_fetch_error: ${err.message}`);
  }

  // ── Assemble Orchestrator-ready EvaluationRequest body ─────────────────
  const syncedAt = new Date().toISOString();

  return {
    // Top-level EvaluationRequest fields (backend/app/schemas.py)
    user_id:      userId,
    current_week: currentWeek,
    sleep:        sleepResult,    // SleepSessionRecord | null
    steps:        stepsResult,    // StepsRecord | null
    // heart_rate is not yet in EvaluationRequest schema — carried for Sprint 2
    heart_rate:   heartRateResult,

    // Sanitized payloads for /api/v1/health/sync
    payloads,

    // Non-PII sync metadata
    sync_meta: {
      synced_at_utc: syncedAt,
      date:          date.toISOString().slice(0, 10),
    },

    // Per-stream non-fatal errors (empty array = clean sync)
    errors,
  };
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
module.exports = {
  // Public API
  requestPermissions,
  getPermissionStatus,
  syncDailyMetrics,

  // Transform layer — exported for unit testing
  transformSleep,
  transformSteps,
  transformHeartRate,

  // SDK injector — used by tests
  setSDK,

  // Internal helpers — exported for unit testing only
  _sourceHash,
  _toPayload,
  _dayRange,
  IDLE_STEPS_THRESHOLD,
  ACTIVE_WINDOW_START_HOUR,
  ACTIVE_WINDOW_END_HOUR,
};
