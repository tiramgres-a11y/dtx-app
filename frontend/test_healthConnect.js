// test_healthConnect.js
/**
 * QA test suite — Worker 1 Health Data Fetcher (healthConnectService.js)
 *
 * Tests transformation correctness using fragmented mock SDK responses.
 * No native runtime, no React Native, no network calls.
 *
 * Run:  node frontend/test_healthConnect.js
 */

'use strict';

const path = require('path');
const {
  transformSleep,
  transformSteps,
  transformHeartRate,
  syncDailyMetrics,
  setSDK,
  _sourceHash,
  _toPayload,
  _dayRange,
  IDLE_STEPS_THRESHOLD,
  ACTIVE_WINDOW_START_HOUR,
  ACTIVE_WINDOW_END_HOUR,
} = require(path.join(__dirname, 'services', 'healthConnectService.js'));

const PASS = '\x1b[92mPASS\x1b[0m';
const FAIL = '\x1b[91mFAIL\x1b[0m';
const results = [];

function record(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`  [${ok ? PASS : FAIL}] ${name}` + (detail ? `  (${detail})` : ''));
}

function approx(a, b, tol = 0.01) {
  return Math.abs(a - b) <= tol;
}

// ─── Fixed test date — a Wednesday to keep getHours() stable ──────────────
const TEST_DATE = new Date('2026-06-03T12:00:00.000Z'); // noon UTC

// =========================================================================
// Test 1: transformSleep — basic fragmented session aggregation
// =========================================================================
console.log('\n=== Test 1: transformSleep — Fragmented Session Aggregation ===');

// Two fragments: 4h + 2h = 6h exactly
const sleepFragmented = [
  { startTime: '2026-06-02T22:00:00Z', endTime: '2026-06-03T02:00:00Z' }, // 4 h
  { startTime: '2026-06-03T02:30:00Z', endTime: '2026-06-03T04:30:00Z' }, // 2 h
];
const sleep1 = transformSleep(sleepFragmented);
record('Returns non-null for valid fragments',    sleep1 !== null);
record('duration_hours is a number',              typeof sleep1?.duration_hours === 'number');
record('duration_hours sums both fragments (6h)', approx(sleep1?.duration_hours, 6.0),
       `got ${sleep1?.duration_hours}`);

// Single full-night session: 7.5 h
const sleepSingle = [
  { startTime: '2026-06-02T23:00:00Z', endTime: '2026-06-03T06:30:00Z' }, // 7.5 h
];
const sleep2 = transformSleep(sleepSingle);
record('Single session: 7.5 h correct',          approx(sleep2?.duration_hours, 7.5),
       `got ${sleep2?.duration_hours}`);

// Very short session: 45 min = 0.75 h
const sleepShort = [
  { startTime: '2026-06-03T03:00:00Z', endTime: '2026-06-03T03:45:00Z' },
];
const sleep3 = transformSleep(sleepShort);
record('Short session: 0.75 h correct',           approx(sleep3?.duration_hours, 0.75),
       `got ${sleep3?.duration_hours}`);

// Three fragments: 2h + 1.5h + 30min = 4h
const sleepThree = [
  { startTime: '2026-06-02T21:00:00Z', endTime: '2026-06-02T23:00:00Z' }, // 2 h
  { startTime: '2026-06-03T01:00:00Z', endTime: '2026-06-03T02:30:00Z' }, // 1.5 h
  { startTime: '2026-06-03T03:00:00Z', endTime: '2026-06-03T03:30:00Z' }, // 0.5 h
];
const sleep4 = transformSleep(sleepThree);
record('Three fragments sum correctly (4 h)',     approx(sleep4?.duration_hours, 4.0),
       `got ${sleep4?.duration_hours}`);

// Edge: empty array → null
record('Empty records → null',                   transformSleep([]) === null);
record('Null input → null',                      transformSleep(null) === null);

// Edge: artifact guard — 19 h session should return null
const sleepArtifact = [
  { startTime: '2026-06-02T00:00:00Z', endTime: '2026-06-02T19:00:00Z' },
];
record('Artifact > 18 h → null',                 transformSleep(sleepArtifact) === null);

// Edge: zero-duration segment is ignored
const sleepZero = [
  { startTime: '2026-06-03T03:00:00Z', endTime: '2026-06-03T03:00:00Z' },
  { startTime: '2026-06-03T03:00:00Z', endTime: '2026-06-03T06:00:00Z' }, // 3 h valid
];
const sleep5 = transformSleep(sleepZero);
record('Zero-duration segment ignored; valid segment = 3 h', approx(sleep5?.duration_hours, 3.0),
       `got ${sleep5?.duration_hours}`);


// =========================================================================
// Test 2: transformSteps — daily aggregation + idle_minutes
// =========================================================================
console.log('\n=== Test 2: transformSteps — Aggregation & Idle Detection ===');

/**
 * Helper: build a Steps record with a midpoint at a given local hour.
 * UTC offset is assumed 0 (tests run in UTC).
 */
function makeStepsRecord(hourLocal, durationMinutes, count) {
  // hourLocal may be fractional (e.g. 10.5 = 10:30) — build via epoch arithmetic
  const dayBase  = new Date('2026-06-03T00:00:00.000Z').getTime();
  const startMs  = dayBase + hourLocal * 3_600_000;
  const endMs    = startMs + durationMinutes * 60_000;
  return {
    startTime: new Date(startMs).toISOString(),
    endTime:   new Date(endMs).toISOString(),
    count,
  };
}

// Scenario A: 4 records totalling 6 000 steps, no idle block >= 60 min
const stepsA = [
  makeStepsRecord(9,  15, 1500),   // active (100/min)
  makeStepsRecord(11, 15, 2000),   // active
  makeStepsRecord(14, 30, 1800),   // active
  makeStepsRecord(17, 15,  700),   // active
];
const r_A = transformSteps(stepsA);
record('Total steps = 6000',       r_A?.steps === 6000, `got ${r_A?.steps}`);
record('No long idle → 0 min',     r_A?.idle_minutes === 0, `got ${r_A?.idle_minutes}`);

// Scenario B: 90-min idle block (3 × 30-min idle intervals back-to-back)
const stepsB = [
  makeStepsRecord(9,   30, 2000),  // active
  makeStepsRecord(10,  30,   0),   // idle  — 30 min
  makeStepsRecord(10.5,30,   2),   // idle  — 30 min (count < threshold)
  makeStepsRecord(11,  30,   0),   // idle  — 30 min  → total 90 min contiguous
  makeStepsRecord(14,  30, 3000),  // active (breaks streak)
];
const r_B = transformSteps(stepsB);
record('Total steps includes idle intervals', r_B?.steps === 5002, `got ${r_B?.steps}`);
record('Longest idle block = 90 min',        r_B?.idle_minutes === 90, `got ${r_B?.idle_minutes}`);

// Scenario C: Interrupted idle — two separate idle blocks (40 min + 30 min)
// Longest should be 40 min
const stepsC = [
  makeStepsRecord(9,  40,   0),   // idle 40 min
  makeStepsRecord(10, 20, 500),   // active — breaks streak
  makeStepsRecord(11, 30,   0),   // idle 30 min
  makeStepsRecord(12, 30, 800),   // active
];
const r_C = transformSteps(stepsC);
record('Interrupted idle: longest block = 40 min', r_C?.idle_minutes === 40,
       `got ${r_C?.idle_minutes}`);

// Scenario D: All outside active window (01:00–03:00 UTC = 04:00–06:00 Israel local)
// These are safely before 08:00 in any timezone up to UTC+7.
const stepsD = [
  { startTime: '2026-06-03T01:00:00Z', endTime: '2026-06-03T02:00:00Z', count: 0 },
  { startTime: '2026-06-03T02:00:00Z', endTime: '2026-06-03T03:00:00Z', count: 0 },
];
const r_D = transformSteps(stepsD);
record('Records outside active window → 0 idle min', r_D?.idle_minutes === 0,
       `got ${r_D?.idle_minutes}`);

// Scenario E: Empty → null
record('Empty records → null',     transformSteps([]) === null);
record('Null input → null',        transformSteps(null) === null);

// Scenario F: Single record with fractional steps — rounds to int
const stepsF = [makeStepsRecord(10, 60, 4820.7)];
const r_F = transformSteps(stepsF);
record('Steps value is integer (Math.round)', Number.isInteger(r_F?.steps),
       `got ${r_F?.steps}`);

// Scenario G: Schema fields present
const stepsG = [makeStepsRecord(10, 60, 5000)];
const r_G = transformSteps(stepsG);
record('Output has steps field',        'steps' in (r_G ?? {}));
record('Output has idle_minutes field', 'idle_minutes' in (r_G ?? {}));
record('Output has exactly 2 fields',   Object.keys(r_G ?? {}).length === 2);


// =========================================================================
// Test 3: transformHeartRate — resting BPM derivation
// =========================================================================
console.log('\n=== Test 3: transformHeartRate — Resting BPM Derivation ===');

// Scenario A: Tagged resting samples preferred
const hrTagged = [
  {
    samples: [
      { beatsPerMinute: 72, measurementLocation: 'MEASUREMENT_LOCATION_WRIST_TEMPERATURE' },
      { beatsPerMinute: 130, measurementLocation: null }, // exercise — ignored
      { beatsPerMinute: 68, measurementLocation: 'MEASUREMENT_LOCATION_WRIST_TEMPERATURE' },
    ],
  },
];
const hr_A = transformHeartRate(hrTagged);
record('Tagged resting samples used', hr_A !== null);
record('Resting median of [68,72] = 70', hr_A?.resting_bpm === 70, `got ${hr_A?.resting_bpm}`);

// Scenario B: No tags — fallback to lowest quartile
const hrNoTags = [
  {
    samples: [
      { beatsPerMinute: 58,  measurementLocation: null },
      { beatsPerMinute: 62,  measurementLocation: null },
      { beatsPerMinute: 140, measurementLocation: null },
      { beatsPerMinute: 155, measurementLocation: null },
    ],
  },
];
const hr_B = transformHeartRate(hrNoTags);
record('Fallback Q1 of [58,62,140,155] = 58', hr_B?.resting_bpm === 58,
       `got ${hr_B?.resting_bpm}`);

// Scenario C: Multiple records with samples
const hrMulti = [
  { samples: [{ beatsPerMinute: 60, measurementLocation: null }] },
  { samples: [{ beatsPerMinute: 65, measurementLocation: null }] },
  { samples: [{ beatsPerMinute: 155, measurementLocation: null }] },
  { samples: [{ beatsPerMinute: 162, measurementLocation: null }] },
];
const hr_C = transformHeartRate(hrMulti);
// Q1 of [60,65,155,162] = first 1 value = [60], median = 60
record('Multi-record Q1 fallback = 60', hr_C?.resting_bpm === 60, `got ${hr_C?.resting_bpm}`);

// Scenario D: Out-of-range values filtered (< 20 or > 250)
const hrBad = [
  { samples: [
      { beatsPerMinute: 5,   measurementLocation: null }, // too low
      { beatsPerMinute: 300, measurementLocation: null }, // too high
      { beatsPerMinute: 63,  measurementLocation: null }, // valid
  ]},
];
const hr_D = transformHeartRate(hrBad);
record('OOB samples filtered, valid 63 returned', hr_D?.resting_bpm === 63,
       `got ${hr_D?.resting_bpm}`);

// Scenario E: Empty
record('Empty records → null',  transformHeartRate([]) === null);
record('Null input → null',     transformHeartRate(null) === null);

// Scenario F: All samples OOB → null
const hrAllBad = [{ samples: [{ beatsPerMinute: 999, measurementLocation: null }] }];
record('All OOB → null',        transformHeartRate(hrAllBad) === null);


// =========================================================================
// Test 4: _sourceHash — idempotency key properties
// =========================================================================
console.log('\n=== Test 4: _sourceHash — Idempotency Key ===');

const h1 = _sourceHash('user-1', '2026-06-03', 'sleep');
const h2 = _sourceHash('user-1', '2026-06-03', 'sleep');
const h3 = _sourceHash('user-1', '2026-06-03', 'steps');
const h4 = _sourceHash('user-2', '2026-06-03', 'sleep');
const h5 = _sourceHash('user-1', '2026-06-04', 'sleep');

record('Same inputs → same hash (deterministic)',         h1 === h2);
record('Different metric_type → different hash',          h1 !== h3);
record('Different user_id → different hash',              h1 !== h4);
record('Different date → different hash',                 h1 !== h5);
record('Hash is 8-char hex string',                       /^[0-9a-f]{8}$/.test(h1), h1);
record('Hash is string type',                             typeof h1 === 'string');


// =========================================================================
// Test 5: _toPayload — sanitization envelope
// =========================================================================
console.log('\n=== Test 5: _toPayload — Sanitization Envelope ===');

const payload = _toPayload('u-001', 'sleep', { duration_hours: 6.5 }, 'hours', TEST_DATE);

record('user_id present',        payload.user_id === 'u-001');
record('metric_type present',    payload.metric_type === 'sleep');
record('value.duration_hours',   payload.value?.duration_hours === 6.5);
record('unit is hours',          payload.unit === 'hours');
record('timestamp_utc is ISO',   typeof payload.timestamp_utc === 'string' && payload.timestamp_utc.includes('T'));
record('source_hash is 8-char hex', /^[0-9a-f]{8}$/.test(payload.source_hash));

// Ensure no extra keys sneak in (PII guard)
const ALLOWED_KEYS = new Set(['user_id', 'metric_type', 'value', 'unit', 'timestamp_utc', 'source_hash']);
const extraKeys = Object.keys(payload).filter((k) => !ALLOWED_KEYS.has(k));
record('No extra fields in payload (PII guard)', extraKeys.length === 0,
       extraKeys.length ? `Extra: ${extraKeys.join(', ')}` : '');


// =========================================================================
// Test 6: syncDailyMetrics — full integration with mock SDK
// =========================================================================
console.log('\n=== Test 6: syncDailyMetrics — Full Integration with Mock SDK ===');

// Build a mock SDK that returns realistic fragmented data
const mockSDK = {
  requestPermission: async () => [
    { accessType: 'read', recordType: 'SleepSession' },
    { accessType: 'read', recordType: 'Steps'        },
    { accessType: 'read', recordType: 'HeartRate'     },
  ],
  getGrantedPermissions: async () => [
    { recordType: 'SleepSession' },
    { recordType: 'Steps'        },
    { recordType: 'HeartRate'    },
  ],
  readRecords: async (type, _opts) => {
    if (type === 'SleepSession') {
      return {
        records: [
          { startTime: '2026-06-02T23:00:00Z', endTime: '2026-06-03T03:00:00Z' }, // 4 h
          { startTime: '2026-06-03T03:30:00Z', endTime: '2026-06-03T05:00:00Z' }, // 1.5 h
        ],
      };
    }
    if (type === 'Steps') {
      return {
        records: [
          makeStepsRecord(9,  30, 1200),
          makeStepsRecord(10, 60,    0),  // idle 60 min inside active window
          makeStepsRecord(11, 60,    5),  // idle 60 min (count < threshold)
          makeStepsRecord(14, 30, 3800),
          makeStepsRecord(17, 15,  750),
        ],
      };
    }
    if (type === 'HeartRate') {
      return {
        records: [
          {
            samples: [
              { beatsPerMinute: 61, measurementLocation: null },
              { beatsPerMinute: 145, measurementLocation: null },
              { beatsPerMinute: 58, measurementLocation: null },
              { beatsPerMinute: 140, measurementLocation: null },
            ],
          },
        ],
      };
    }
    return { records: [] };
  },
};

setSDK(mockSDK);

let syncResult;
(async () => {
  try {
    syncResult = await syncDailyMetrics('test-user-w1', 2, TEST_DATE);

    // ── Top-level structure ──────────────────────────────────────────────
    record('syncResult is an object',                typeof syncResult === 'object' && syncResult !== null);
    record('user_id matches',                        syncResult.user_id === 'test-user-w1');
    record('current_week = 2',                       syncResult.current_week === 2);

    // ── Sleep field (EvaluationRequest.sleep = SleepSessionRecord) ───────
    record('sleep field is non-null',                syncResult.sleep !== null);
    record('sleep.duration_hours is a number',       typeof syncResult.sleep?.duration_hours === 'number');
    record('sleep.duration_hours = 5.5 h (4+1.5)',   approx(syncResult.sleep?.duration_hours, 5.5),
           `got ${syncResult.sleep?.duration_hours}`);
    record('sleep has exactly 1 key (schema match)', Object.keys(syncResult.sleep ?? {}).length === 1);

    // ── Steps field (EvaluationRequest.steps = StepsRecord) ──────────────
    record('steps field is non-null',                syncResult.steps !== null);
    record('steps.steps = 5755',                     syncResult.steps?.steps === 5755,
           `got ${syncResult.steps?.steps}`);
    record('steps.idle_minutes = 120',               syncResult.steps?.idle_minutes === 120,
           `got ${syncResult.steps?.idle_minutes}`);
    record('steps has exactly 2 keys (schema match)',Object.keys(syncResult.steps ?? {}).length === 2);

    // ── HeartRate field ───────────────────────────────────────────────────
    record('heart_rate field is non-null',           syncResult.heart_rate !== null);
    record('heart_rate.resting_bpm is integer',      Number.isInteger(syncResult.heart_rate?.resting_bpm),
           `got ${syncResult.heart_rate?.resting_bpm}`);
    // Q1 of [58,61,140,145] = first 1 = [58], median = 58
    record('heart_rate.resting_bpm = 58',            syncResult.heart_rate?.resting_bpm === 58,
           `got ${syncResult.heart_rate?.resting_bpm}`);

    // ── Payloads array (sanitized HealthMetricPayload) ────────────────────
    record('payloads array has 3 entries',           syncResult.payloads?.length === 3,
           `got ${syncResult.payloads?.length}`);
    const payloadTypes = syncResult.payloads?.map((p) => p.metric_type).sort();
    record('payload types: sleep, steps, heart_rate', JSON.stringify(payloadTypes) === '["heart_rate","sleep","steps"]',
           JSON.stringify(payloadTypes));

    for (const p of (syncResult.payloads ?? [])) {
      const keys = Object.keys(p).sort().join(',');
      record(`${p.metric_type} payload has correct fields`,
             keys === 'metric_type,source_hash,timestamp_utc,unit,user_id,value', keys);
    }

    // ── No PII in payloads ─────────────────────────────────────────────────
    const PII_FIELDS = ['deviceId', 'recordId', 'clientRecordId', 'metadata'];
    const piiLeak = syncResult.payloads?.some((p) =>
      PII_FIELDS.some((f) => f in p),
    );
    record('No PII/device fields in any payload', !piiLeak);

    // ── sync_meta ──────────────────────────────────────────────────────────
    record('sync_meta.date = 2026-06-03',            syncResult.sync_meta?.date === '2026-06-03',
           `got ${syncResult.sync_meta?.date}`);
    record('sync_meta.synced_at_utc is ISO-8601',    typeof syncResult.sync_meta?.synced_at_utc === 'string');

    // ── Errors array ────────────────────────────────────────────────────────
    record('errors array is empty (clean sync)',     syncResult.errors?.length === 0,
           `got ${JSON.stringify(syncResult.errors)}`);

    // ── Architecture invariant — no clinical keys in result ────────────────
    const CLINICAL_KEYS = ['triggered_rules', 'oars_reflection_he', 'push_notification_he',
                           'menu_adjustment', 'phase', 'clinical_notes_he'];
    const clinicalLeak = CLINICAL_KEYS.some((k) => k in syncResult);
    record('No clinical/OARS keys in sync result (read-only invariant)', !clinicalLeak);

  } catch (err) {
    record(`syncDailyMetrics threw: ${err.message}`, false, err.stack?.split('\n')[1] ?? '');
  }


  // =========================================================================
  // Test 7: Error resilience — one stream fails, others succeed
  // =========================================================================
  console.log('\n=== Test 7: Error Resilience — Partial Failure ===');

  const flakySDK = {
    ...mockSDK,
    readRecords: async (type, _opts) => {
      if (type === 'SleepSession') throw new Error('SDK timeout');
      if (type === 'Steps') return {
        records: [makeStepsRecord(10, 60, 5000)],
      };
      if (type === 'HeartRate') return {
        records: [{ samples: [{ beatsPerMinute: 65, measurementLocation: null }] }],
      };
      return { records: [] };
    },
  };
  setSDK(flakySDK);

  const flakyResult = await syncDailyMetrics('user-flaky', 3, TEST_DATE);
  record('sleep is null when stream fails',        flakyResult.sleep === null);
  record('steps still returns data',               flakyResult.steps !== null);
  record('heart_rate still returns data',          flakyResult.heart_rate !== null);
  record('errors array contains sleep error',      flakyResult.errors?.some((e) => e.includes('sleep')),
         JSON.stringify(flakyResult.errors));
  record('payloads has 2 entries (sleep skipped)', flakyResult.payloads?.length === 2,
         `got ${flakyResult.payloads?.length}`);


  // =========================================================================
  // Test 8: Architecture invariants — source audit
  // =========================================================================
  console.log('\n=== Test 8: Architecture Invariant Audit (Source-Level) ===');

  const fs  = require('fs');
  const src = fs.readFileSync(path.join(__dirname, 'services', 'healthConnectService.js'), 'utf-8');

  // Must NOT contain clinical logic
  const BANNED_PATTERNS = [
    { pattern: /SLEEP_THRESHOLD/,             label: 'clinical sleep threshold' },
    { pattern: /SEDENTARY_THRESHOLD/,         label: 'clinical sedentary threshold' },
    { pattern: /oars_reflection/,             label: 'OARS output field' },
    { pattern: /push_notification_he/,        label: 'push notification field' },
    { pattern: /menu_adjustment/,             label: 'menu adjustment' },
    { pattern: /triggered_rules/,             label: 'triggered rules' },
    { pattern: /clinical_notes/,              label: 'clinical notes' },
    { pattern: /AsyncStorage\.setItem/,       label: 'UI/AsyncStorage write (state mutation)' },
    { pattern: /setState\s*\(/,               label: 'React state mutation' },
    { pattern: /import.*useState/,            label: 'React hook import' },
  ];

  for (const { pattern, label } of BANNED_PATTERNS) {
    record(`Does NOT contain ${label}`, !pattern.test(src));
  }

  // Must contain read-only permission scope
  record('Declares REQUIRED_PERMISSIONS with read-only accessType',
         src.includes("accessType: 'read'"));
  record('Exports transformSleep, transformSteps, transformHeartRate',
         src.includes('transformSleep') && src.includes('transformSteps') && src.includes('transformHeartRate'));
  record('Exports setSDK for test injection',
         src.includes('setSDK'));


  // =========================================================================
  // Summary
  // =========================================================================
  console.log('\n' + '='.repeat(60));
  const total  = results.length;
  const passed = results.filter((r) => r.ok).length;
  const failed = total - passed;

  console.log(`\nResults: ${passed}/${total} passed`);

  if (failed) {
    console.log(`\n${failed} test(s) FAILED:`);
    results.filter((r) => !r.ok).forEach((r) => {
      console.log(`  - ${r.name}` + (r.detail ? ` (${r.detail})` : ''));
    });
    process.exit(1);
  } else {
    console.log('\nAll tests passed.');
    process.exit(0);
  }
})();
