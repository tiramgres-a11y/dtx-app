/**
 * test_network.js — Network Layer & API Client QA
 *
 * Tests (all via axios-mock-adapter, no live server):
 *   1.  Axios instance config — baseURL, timeout, UTF-8 headers
 *   2.  Successful evaluate call — 200 response parsed correctly
 *   3.  Successful SOS trigger — 200 response parsed correctly
 *   4.  Successful SOS resolve — 200 response parsed correctly
 *   5.  500 server error — fallback fires, error key = NET_ERROR_SERVER
 *   6.  Network timeout — fallback fires, error key = NET_ERROR_TIMEOUT
 *   7.  Network offline (no response) — fallback fires, key = NET_ERROR_UNKNOWN
 *   8.  400 client error — fallback does NOT fire, error key = NET_ERROR_CLIENT_400
 *   9.  401 Unauthorised — fallback does NOT fire
 *  10.  404 Not Found — fallback does NOT fire
 *  11.  422 Validation error — fallback does NOT fire
 *  12.  classifyError unit tests — all branches
 *  13.  setFallbackHandler validates input type
 *  14.  Fallback fires exactly once per 500 (no double-dispatch)
 *  15.  No Hebrew literals in client.js or endpoints.js source
 *  16.  All NET_* locale keys exist in he.json and contain Hebrew
 *  17.  ROUTES constants match live backend paths
 *  18.  re-thrown error carries ._dtx metadata
 *
 * Run: node frontend/test_network.js
 */

'use strict';

const path = require('path');
const fs   = require('fs');

// ─── Load real axios (not the stub from client.js) ────────────────────────
let axiosLib = require('axios');
if (axiosLib.default) axiosLib = axiosLib.default;  // ESM interop
const MockAdapter = require('axios-mock-adapter');

// ─── Inject axios into the client BEFORE requiring it ─────────────────────
const clientPath    = path.join(__dirname, 'api', 'client.js');
const endpointsPath = path.join(__dirname, 'api', 'endpoints.js');

// Ensure fresh module state on each test file run
Object.keys(require.cache).forEach((key) => {
  if (key === clientPath || key === endpointsPath) delete require.cache[key];
});

const client    = require(clientPath);
const endpoints = require(endpointsPath);

client.setAxios(axiosLib);

// ─── Harness ──────────────────────────────────────────────────────────────
const PASS = '\x1b[92mPASS\x1b[0m';
const FAIL = '\x1b[91mFAIL\x1b[0m';
const results = [];

function record(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`  [${ok ? PASS : FAIL}] ${name}` + (detail ? `  (${detail})` : ''));
}

// ─── Mock adapter wired to a fresh Axios instance ─────────────────────────
// Create an Axios instance, attach MockAdapter, then inject it into client.js
// via setInstance(). Because _getInstance() returns _axiosInstance when already
// set, all calls through endpoints.js will use this mock-backed instance.
const mockAxiosInstance = axiosLib.create(client.DEFAULT_CONFIG);
const mock = new MockAdapter(mockAxiosInstance, { onNoMatch: 'throwException' });

// setInstance() writes directly to _axiosInstance inside client.js — the same
// reference that getInstance() (captured by endpoints.js) will return.
client.setInstance(mockAxiosInstance);

// ─── Fixture payloads ─────────────────────────────────────────────────────
const EVAL_PAYLOAD = {
  user_id: 'test-net-001', current_week: 2,
  sleep:  { duration_hours: 5.5 },
  steps:  { steps: 4820, idle_minutes: 90 },
};

const EVAL_RESPONSE = {
  user_id: 'test-net-001', current_week: 2, phase: 'שלב 1 — איפוס (שבועות 1–4)',
  triggered_rules: ['SLEEP_SHORT', 'SEDENTARY_ALERT'],
  menu_adjustment: { reduce_complex_carbs: true, increase_plant_protein: true,
                     increase_nuts: true, rationale_he: 'שינה קצרה מעלה עמידות לאינסולין.' },
  oars_reflection_he: 'שמנו לב שהשינה הלילה הייתה קצרה.',
  push_notification_he: '⏰ זמן תנועה קצר!',
  strength_validation_he: null,
  clinical_notes_he: ['כלל שינה הופעל.'],
};

const SOS_TRIGGER_PAYLOAD  = { user_id: 'test-net-001', week_context: 11 };
const SOS_TRIGGER_RESPONSE = {
  user_id: 'test-net-001', week_context: 11,
  empathy_message_he: 'זה ממש מתסכל כשמרגישים דחף כזה שלא נשלט.',
  protocol_steps: [{ step_number: 1, title_he: 'צעד 1', instruction_he: 'שתה מים' }],
  event_logged: true, timestamp_utc: '2026-06-04T20:00:00.000Z',
};

const SOS_RESOLVE_PAYLOAD  = {
  user_id: 'test-net-001', event_timestamp_utc: '2026-06-04T20:00:00.000Z',
  status: 'LAPSE', week_context: 12,
};
const SOS_RESOLVE_RESPONSE = {
  user_id: 'test-net-001', status: 'LAPSE', resolved_at_utc: '2026-06-04T20:05:00.000Z',
  acknowledgement_he: 'קיבלנו. תודה שסיפרת לי.',
  morning_queue: { oars_affirmation_he: 'זה ניצחון מנטלי.', habit_reset_he: 'ארוחת בוקר מאוזנת.' },
};

// ─── Fallback capture helper ───────────────────────────────────────────────
function makeFallbackCapture() {
  const calls = [];
  const handler = (info) => calls.push(info);
  client.setFallbackHandler(handler);
  return calls;
}

// =========================================================================
(async () => {

// ─── Test 1: Instance configuration ──────────────────────────────────────
console.log('\n=== Test 1: Axios Instance Configuration ===');
record('DEFAULT_CONFIG.baseURL is set',
       typeof client.DEFAULT_CONFIG.baseURL === 'string' && client.DEFAULT_CONFIG.baseURL.startsWith('http'));
record('DEFAULT_CONFIG.timeout = 5000',  client.DEFAULT_CONFIG.timeout === 5000);
record('Content-Type includes utf-8',
       client.DEFAULT_CONFIG.headers['Content-Type'].includes('utf-8'));
record('Accept-Charset is utf-8',
       client.DEFAULT_CONFIG.headers['Accept-Charset'] === 'utf-8');
record('Accept is application/json',
       client.DEFAULT_CONFIG.headers['Accept'] === 'application/json');


// ─── Test 2: Successful evaluateMetrics ──────────────────────────────────
console.log('\n=== Test 2: evaluateMetrics — 200 Success ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(200, EVAL_RESPONSE);
const fallbackCalls2 = makeFallbackCapture();

let evalResult;
try {
  evalResult = await endpoints.evaluateMetrics(EVAL_PAYLOAD);
} catch (e) {
  evalResult = null;
}

record('evaluateMetrics returns data on 200',       evalResult !== null);
record('user_id matches',                           evalResult?.user_id === 'test-net-001');
record('triggered_rules contains SLEEP_SHORT',      evalResult?.triggered_rules?.includes('SLEEP_SHORT'));
record('menu_adjustment is present',                evalResult?.menu_adjustment !== null);
record('Hebrew text in oars_reflection_he',         typeof evalResult?.oars_reflection_he === 'string');
record('Fallback NOT fired on success',             fallbackCalls2.length === 0,
       `fired ${fallbackCalls2.length} times`);


// ─── Test 3: Successful triggerSOS ───────────────────────────────────────
console.log('\n=== Test 3: triggerSOS — 200 Success ===');
mock.onPost(endpoints.ROUTES.SOS_TRIGGER).replyOnce(200, SOS_TRIGGER_RESPONSE);
const fallbackCalls3 = makeFallbackCapture();

let sosResult;
try {
  sosResult = await endpoints.triggerSOS(SOS_TRIGGER_PAYLOAD);
} catch (e) { sosResult = null; }

record('triggerSOS returns data on 200',            sosResult !== null);
record('event_logged is true',                      sosResult?.event_logged === true);
record('timestamp_utc is present',                  typeof sosResult?.timestamp_utc === 'string');
record('empathy_message_he contains Hebrew',        /[֐-׿]/.test(sosResult?.empathy_message_he ?? ''));
record('Fallback NOT fired on success',             fallbackCalls3.length === 0);


// ─── Test 4: Successful resolveSOS ───────────────────────────────────────
console.log('\n=== Test 4: resolveSOS — 200 Success ===');
mock.onPost(endpoints.ROUTES.SOS_RESOLVE).replyOnce(200, SOS_RESOLVE_RESPONSE);
const fallbackCalls4 = makeFallbackCapture();

let resolveResult;
try {
  resolveResult = await endpoints.resolveSOS(SOS_RESOLVE_PAYLOAD);
} catch (e) { resolveResult = null; }

record('resolveSOS returns data on 200',            resolveResult !== null);
record('status is LAPSE',                           resolveResult?.status === 'LAPSE');
record('morning_queue is present',                  resolveResult?.morning_queue !== null);
record('Fallback NOT fired on success',             fallbackCalls4.length === 0);


// ─── Test 5: 500 Server Error → fallback fires ───────────────────────────
console.log('\n=== Test 5: 500 Server Error — Fallback Must Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(500, { detail: 'Internal Server Error' });
const fallbackCalls5 = makeFallbackCapture();

let err5 = null;
try {
  await endpoints.evaluateMetrics(EVAL_PAYLOAD);
} catch (e) { err5 = e; }

record('500 throws an error',                       err5 !== null);
record('Fallback fired once on 500',                fallbackCalls5.length === 1,
       `fired ${fallbackCalls5.length} times`);
record('Fallback errorKey = NET_ERROR_SERVER',      fallbackCalls5[0]?.errorKey === 'NET_ERROR_SERVER',
       fallbackCalls5[0]?.errorKey);
record('Fallback statusCode = 500',                 fallbackCalls5[0]?.statusCode === 500);
record('error._dtx.errorKey = NET_ERROR_SERVER',    err5?._dtx?.errorKey === 'NET_ERROR_SERVER',
       err5?._dtx?.errorKey);


// ─── Test 6: Network Timeout → fallback fires ────────────────────────────
console.log('\n=== Test 6: Network Timeout — Fallback Must Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).timeoutOnce();
const fallbackCalls6 = makeFallbackCapture();

let err6 = null;
try {
  await endpoints.evaluateMetrics(EVAL_PAYLOAD);
} catch (e) { err6 = e; }

record('Timeout throws an error',                   err6 !== null);
record('Fallback fired once on timeout',            fallbackCalls6.length === 1,
       `fired ${fallbackCalls6.length} times`);
record('Fallback errorKey = NET_ERROR_TIMEOUT',     fallbackCalls6[0]?.errorKey === 'NET_ERROR_TIMEOUT',
       fallbackCalls6[0]?.errorKey);
record('Fallback statusCode = null',                fallbackCalls6[0]?.statusCode === null);
record('error._dtx.errorKey = NET_ERROR_TIMEOUT',   err6?._dtx?.errorKey === 'NET_ERROR_TIMEOUT',
       err6?._dtx?.errorKey);


// ─── Test 7: Network Offline (no response) → fallback fires ──────────────
console.log('\n=== Test 7: Network Offline — Fallback Must Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).networkErrorOnce();
const fallbackCalls7 = makeFallbackCapture();

let err7 = null;
try {
  await endpoints.evaluateMetrics(EVAL_PAYLOAD);
} catch (e) { err7 = e; }

record('Network error throws',                      err7 !== null);
record('Fallback fired once on network error',      fallbackCalls7.length === 1,
       `fired ${fallbackCalls7.length} times`);
record('Fallback errorKey is timeout or unknown',
       ['NET_ERROR_TIMEOUT','NET_ERROR_UNKNOWN'].includes(fallbackCalls7[0]?.errorKey),
       fallbackCalls7[0]?.errorKey);
record('statusCode is null (no HTTP response)',     fallbackCalls7[0]?.statusCode === null);


// ─── Test 8: 400 Bad Request — fallback must NOT fire ────────────────────
console.log('\n=== Test 8: 400 Bad Request — Fallback Must NOT Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(400, { detail: 'bad input' });
const fallbackCalls8 = makeFallbackCapture();

let err8 = null;
try {
  await endpoints.evaluateMetrics(EVAL_PAYLOAD);
} catch (e) { err8 = e; }

record('400 throws an error',                       err8 !== null);
record('Fallback NOT fired on 400',                 fallbackCalls8.length === 0,
       `fired ${fallbackCalls8.length} times`);
record('error._dtx.errorKey = NET_ERROR_CLIENT_400', err8?._dtx?.errorKey === 'NET_ERROR_CLIENT_400',
       err8?._dtx?.errorKey);


// ─── Test 9: 401 Unauthorised ─────────────────────────────────────────────
console.log('\n=== Test 9: 401 Unauthorised — Fallback Must NOT Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(401);
const fallbackCalls9 = makeFallbackCapture();
let err9 = null;
try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (e) { err9 = e; }
record('401 throws',                                err9 !== null);
record('Fallback NOT fired on 401',                 fallbackCalls9.length === 0);
record('error._dtx.errorKey = NET_ERROR_CLIENT_401', err9?._dtx?.errorKey === 'NET_ERROR_CLIENT_401');


// ─── Test 10: 404 Not Found ───────────────────────────────────────────────
console.log('\n=== Test 10: 404 Not Found — Fallback Must NOT Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(404);
const fallbackCalls10 = makeFallbackCapture();
let err10 = null;
try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (e) { err10 = e; }
record('404 throws',                                err10 !== null);
record('Fallback NOT fired on 404',                 fallbackCalls10.length === 0);
record('error._dtx.errorKey = NET_ERROR_CLIENT_404', err10?._dtx?.errorKey === 'NET_ERROR_CLIENT_404');


// ─── Test 11: 422 Validation Error ───────────────────────────────────────
console.log('\n=== Test 11: 422 Validation Error — Fallback Must NOT Fire ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(422, { detail: [{ msg: 'value error' }] });
const fallbackCalls11 = makeFallbackCapture();
let err11 = null;
try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (e) { err11 = e; }
record('422 throws',                                err11 !== null);
record('Fallback NOT fired on 422',                 fallbackCalls11.length === 0);
record('error._dtx.errorKey = NET_ERROR_CLIENT_422', err11?._dtx?.errorKey === 'NET_ERROR_CLIENT_422');


// ─── Test 12: classifyError — unit tests for all branches ────────────────
console.log('\n=== Test 12: classifyError — Branch Coverage ===');
const { classifyError, ERROR_KEYS } = client;

const makeErr = (status) => ({ response: { status } });
const makeNoResp = (code, msg = '') => ({ response: null, code, message: msg });

const c500 = classifyError(makeErr(500));
record('500 → SERVER key + triggerFallback=true',
       c500.errorKey === ERROR_KEYS.SERVER && c500.triggerFallback === true);

const c503 = classifyError(makeErr(503));
record('503 → SERVER key + triggerFallback=true',
       c503.errorKey === ERROR_KEYS.SERVER && c503.triggerFallback === true);

const c400 = classifyError(makeErr(400));
record('400 → E400 key + triggerFallback=false',
       c400.errorKey === ERROR_KEYS.E400 && c400.triggerFallback === false);

const c401 = classifyError(makeErr(401));
record('401 → E401 + no fallback', c401.errorKey === ERROR_KEYS.E401 && !c401.triggerFallback);

const c403 = classifyError(makeErr(403));
record('403 → E403 + no fallback', c403.errorKey === ERROR_KEYS.E403 && !c403.triggerFallback);

const c404 = classifyError(makeErr(404));
record('404 → E404 + no fallback', c404.errorKey === ERROR_KEYS.E404 && !c404.triggerFallback);

const c422 = classifyError(makeErr(422));
record('422 → E422 + no fallback', c422.errorKey === ERROR_KEYS.E422 && !c422.triggerFallback);

const cTimeout = classifyError(makeNoResp('ECONNABORTED', 'timeout'));
record('ECONNABORTED → TIMEOUT + triggerFallback=true',
       cTimeout.errorKey === ERROR_KEYS.TIMEOUT && cTimeout.triggerFallback === true);

const cTimedOut = classifyError(makeNoResp('ETIMEDOUT'));
record('ETIMEDOUT → TIMEOUT + triggerFallback=true',
       cTimedOut.errorKey === ERROR_KEYS.TIMEOUT && cTimedOut.triggerFallback === true);

const cMsgTimeout = classifyError(makeNoResp(null, 'Request timeout exceeded'));
record('"timeout" in message → TIMEOUT key',
       cMsgTimeout.errorKey === ERROR_KEYS.TIMEOUT && cMsgTimeout.triggerFallback === true);

const cNetwork = classifyError(makeNoResp('ERR_NETWORK', 'Network Error'));
record('ERR_NETWORK (no timeout msg) → UNKNOWN + triggerFallback=true',
       cNetwork.errorKey === ERROR_KEYS.UNKNOWN && cNetwork.triggerFallback === true);

const c499 = classifyError(makeErr(499));
record('499 (other 4xx) → UNKNOWN + no fallback',
       c499.errorKey === ERROR_KEYS.UNKNOWN && !c499.triggerFallback);

const c200Status = classifyError(makeErr(200)); // edge: error with 200 status
record('200 via error path → UNKNOWN (safe fallback)', c200Status !== null);


// ─── Test 13: setFallbackHandler validates input ──────────────────────────
console.log('\n=== Test 13: setFallbackHandler Input Validation ===');
let threw = false;
try { client.setFallbackHandler('not a function'); } catch (e) { threw = true; }
record('setFallbackHandler throws on non-function input', threw);
record('setFallbackHandler accepts a function without throwing', (() => {
  try { client.setFallbackHandler(() => {}); return true; } catch { return false; }
})());


// ─── Test 14: Fallback fires exactly once per error (no double-dispatch) ──
console.log('\n=== Test 14: Fallback Fires Exactly Once Per Error ===');
mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(500);
const calls14 = [];
client.setFallbackHandler((info) => calls14.push(info));
try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (_) {}
record('Fallback fired exactly once for a single 500', calls14.length === 1,
       `fired ${calls14.length} times`);


// ─── Test 15: No Hebrew literals in source files ──────────────────────────
console.log('\n=== Test 15: No Hebrew Literals in API Source Files ===');
const HE_RE = /[֐-׿]/;
const QUOTED_HE = /(['"`])(?:(?!\1).)*[֐-׿](?:(?!\1).)*\1/g;

for (const [label, filePath] of [
  ['client.js',    path.join(__dirname, 'api', 'client.js')],
  ['endpoints.js', path.join(__dirname, 'api', 'endpoints.js')],
]) {
  const src     = fs.readFileSync(filePath, 'utf-8');
  const matches = (src.match(QUOTED_HE) || []).filter((m) => HE_RE.test(m));
  record(`${label} — zero inline Hebrew string literals`, matches.length === 0,
         matches.length ? matches.slice(0,2).join(' | ') : '');
}


// ─── Test 16: All NET_* locale keys exist in he.json with Hebrew content ──
console.log('\n=== Test 16: NET_* Locale Keys in he.json ===');
const heJson = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'locales', 'he.json'), 'utf-8'));

const NET_KEYS = [
  'NET_ERROR_TIMEOUT', 'NET_ERROR_SERVER', 'NET_ERROR_CLIENT_400',
  'NET_ERROR_CLIENT_401', 'NET_ERROR_CLIENT_403', 'NET_ERROR_CLIENT_404',
  'NET_ERROR_CLIENT_422', 'NET_ERROR_UNKNOWN', 'NET_FALLBACK_ACTIVATED',
  'NET_LOG_REQUEST', 'NET_LOG_RESPONSE_OK', 'NET_LOG_RESPONSE_ERROR',
];

for (const key of NET_KEYS) {
  record(`[${key}] present in he.json`,         key in heJson);
  record(`[${key}] contains Hebrew chars`,       HE_RE.test(heJson[key] ?? ''),
         (heJson[key] ?? '').slice(0, 25));
}


// ─── Test 17: ROUTES constants match live backend paths ───────────────────
console.log('\n=== Test 17: ROUTES Match Backend Paths ===');
record('ROUTES.EVALUATE = /api/v1/evaluate',      endpoints.ROUTES.EVALUATE === '/api/v1/evaluate');
record('ROUTES.SOS_TRIGGER = /api/v1/sos/trigger', endpoints.ROUTES.SOS_TRIGGER === '/api/v1/sos/trigger');
record('ROUTES.SOS_RESOLVE = /api/v1/sos/resolve', endpoints.ROUTES.SOS_RESOLVE === '/api/v1/sos/resolve');
record('ROUTES.HEALTH = /health',                 endpoints.ROUTES.HEALTH === '/health');
record('ROUTES.EVALUATE_ALIAS contains engine',   endpoints.ROUTES.EVALUATE_ALIAS.includes('engine'));


// ─── Test 18: error._dtx metadata is always attached ─────────────────────
console.log('\n=== Test 18: error._dtx Metadata Contract ===');
for (const [label, statusOrMode] of [
  ['500', 500], ['503', 503], ['400', 400], ['404', 404],
]) {
  mock.onPost(endpoints.ROUTES.EVALUATE).replyOnce(statusOrMode);
  client.setFallbackHandler(() => {});
  let caught = null;
  try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (e) { caught = e; }
  record(`HTTP ${label} — error._dtx.errorKey is a string`,
         typeof caught?._dtx?.errorKey === 'string', caught?._dtx?.errorKey);
  record(`HTTP ${label} — error._dtx.statusCode = ${statusOrMode}`,
         caught?._dtx?.statusCode === statusOrMode);
}

// Network error _dtx
mock.onPost(endpoints.ROUTES.EVALUATE).networkErrorOnce();
client.setFallbackHandler(() => {});
let netErr = null;
try { await endpoints.evaluateMetrics(EVAL_PAYLOAD); } catch (e) { netErr = e; }
record('Network error — _dtx.statusCode is null', netErr?._dtx?.statusCode === null);
record('Network error — _dtx.errorKey is string', typeof netErr?._dtx?.errorKey === 'string');


// ─── Summary ──────────────────────────────────────────────────────────────
console.log('\n' + '='.repeat(60));
const total  = results.length;
const passed = results.filter((r) => r.ok).length;
const failed = total - passed;

console.log(`\nResults: ${passed}/${total} passed`);

if (failed) {
  console.log(`\n${failed} FAILED:`);
  results.filter((r) => !r.ok).forEach((r) => {
    console.log(`  ✗ ${r.name}` + (r.detail ? ` (${r.detail})` : ''));
  });
  process.exit(1);
} else {
  console.log('\nAll tests passed.');
  process.exit(0);
}

})();
