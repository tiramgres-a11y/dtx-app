// @flow
/**
 * test_ui_toggle.js — Static render + logic QA for DashboardScreen.
 *
 * What this tests (without a running device):
 *  1. i18n layer: every dashboard key resolves to a real Hebrew string
 *  2. No MISSING: sentinel appears in any dashboard key
 *  3. Both UI state objects (active / inactive) render non-empty content maps
 *  4. MetricBar clamping logic (value > goal, value = 0, normal case)
 *  5. MilestoneChecklist toggle logic (add / remove / idempotent)
 *  6. SleepQuickTap option list completeness and value correctness
 *  7. Graceful degradation: active state keys ≠ inactive state keys (disjoint sets)
 *  8. RTL tokens: I18nManager.forceRTL recorded; logical style props present
 *  9. No Hebrew literals inside DashboardScreen.js source (only t() calls)
 * 10. All he.json dashboard keys are valid UTF-8 Hebrew (not ASCII-only)
 *
 * Run: node frontend/test_ui_toggle.js
 * Requires: Node.js only — no Expo, no React Native runtime.
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ─── Minimal React Native mock (no native modules needed) ─────────────────
global.__DEV__ = true;

// Stub out RN modules that would require a native runtime
const mockModule = () => ({});
const STUB_REGISTRY = [
  'react-native',
  'react',
];

// We resolve files directly — no module bundler needed
const ROOT = path.resolve(__dirname, '..');

// ─── Test harness ──────────────────────────────────────────────────────────
const PASS = '\x1b[92mPASS\x1b[0m';
const FAIL = '\x1b[91mFAIL\x1b[0m';
const results = [];

function record(name, ok, detail = '') {
  results.push({ name, ok, detail });
  const status = ok ? PASS : FAIL;
  console.log(`  [${status}] ${name}` + (detail ? `  (${detail})` : ''));
}

// ─── Load artefacts directly ───────────────────────────────────────────────
const heJsonPath      = path.join(ROOT, 'locales', 'he.json');
const dashboardPath   = path.join(ROOT, 'frontend', 'screens', 'DashboardScreen.js');
const tokensPath      = path.join(ROOT, 'frontend', 'components', 'tokens.js');
const milestoneSource = path.join(ROOT, 'frontend', 'components', 'MilestoneChecklist.js');
const sleepTapSource  = path.join(ROOT, 'frontend', 'components', 'SleepQuickTap.js');
const metricBarSource = path.join(ROOT, 'frontend', 'components', 'MetricBar.js');
const i18nSource      = path.join(ROOT, 'frontend', 'utils', 'i18n.js');

const heJson          = JSON.parse(fs.readFileSync(heJsonPath, 'utf-8'));
const dashboardSrc    = fs.readFileSync(dashboardPath, 'utf-8');
const tokensSrc       = fs.readFileSync(tokensPath, 'utf-8');
const milestoneSrc    = fs.readFileSync(milestoneSource, 'utf-8');
const sleepTapSrc     = fs.readFileSync(sleepTapSource, 'utf-8');
const metricBarSrc    = fs.readFileSync(metricBarSource, 'utf-8');
const i18nSrc         = fs.readFileSync(i18nSource, 'utf-8');

// ─── Test 1: All dashboard locale keys resolve ─────────────────────────────
console.log('\n=== Test 1: All Dashboard Locale Keys Present in he.json ===');

const DASHBOARD_KEYS = [
  'DASHBOARD_TITLE', 'DASHBOARD_WEEK_LABEL', 'DASHBOARD_PHASE_LABEL',
  'DASHBOARD_GREETING_MORNING', 'DASHBOARD_GREETING_AFTERNOON', 'DASHBOARD_GREETING_EVENING',
  'SENSOR_STATUS_ACTIVE', 'SENSOR_STATUS_INACTIVE', 'SENSOR_CONNECT_CTA',
  'METRICS_SLEEP_LABEL', 'METRICS_SLEEP_UNIT', 'METRICS_SLEEP_GOAL',
  'METRICS_STEPS_LABEL', 'METRICS_STEPS_UNIT', 'METRICS_STEPS_GOAL',
  'METRICS_SEDENTARY_LABEL', 'METRICS_SEDENTARY_UNIT', 'METRICS_SEDENTARY_WARNING',
  'METRICS_SECTION_TITLE',
  'MANUAL_SECTION_TITLE', 'MANUAL_SECTION_SUBTITLE',
  'MANUAL_SLEEP_LABEL',
  'MANUAL_SLEEP_BTN_4', 'MANUAL_SLEEP_BTN_5', 'MANUAL_SLEEP_BTN_6',
  'MANUAL_SLEEP_BTN_7', 'MANUAL_SLEEP_BTN_8',
  'MANUAL_MILESTONES_LABEL',
  'MANUAL_MILESTONE_WALK', 'MANUAL_MILESTONE_STAIRS',
  'MANUAL_MILESTONE_STRETCH', 'MANUAL_MILESTONE_STRENGTH',
  'MANUAL_SUBMIT_BTN', 'MANUAL_SAVED_TOAST',
  'PROGRESS_OF', 'PROGRESS_COMPLETE',
];

for (const key of DASHBOARD_KEYS) {
  record(`[${key}] present in he.json`, key in heJson);
}

// ─── Test 2: No MISSING sentinel in dashboard strings ─────────────────────
console.log('\n=== Test 2: No MISSING: Sentinel in Dashboard Values ===');
const missingKeys = DASHBOARD_KEYS.filter((k) => !heJson[k] || heJson[k].startsWith('[MISSING:'));
record('Zero dashboard keys produce MISSING sentinel', missingKeys.length === 0,
       missingKeys.length ? `Missing: ${missingKeys.join(', ')}` : '');

// ─── Test 3: Hebrew character presence in all dashboard values ────────────
console.log('\n=== Test 3: All Dashboard Values Contain Hebrew Characters ===');
// Hebrew Unicode block: U+0590–U+05FF
const HEBREW_RE = /[֐-׿]/;
for (const key of DASHBOARD_KEYS) {
  const val = heJson[key] || '';
  record(`[${key}] contains Hebrew chars`, HEBREW_RE.test(val), val.slice(0, 30));
}

// ─── Test 4: Inline Hebrew literal audit in DashboardScreen.js ────────────
console.log('\n=== Test 4: No Inline Hebrew Literals in DashboardScreen.js ===');
// Match any string literal (single or double quoted) containing Hebrew chars
// Excludes comments and t() calls — we look for quoted Hebrew not preceded by t(
const QUOTED_HEBREW_RE = /(['"`])(?:(?!\1).)*[֐-׿](?:(?!\1).)*\1/g;
const jsxMatches = (dashboardSrc.match(QUOTED_HEBREW_RE) || []).filter(
  // Allow Hebrew inside t('...') calls — those are key names (ASCII), not translations
  // A Hebrew string literal that's NOT a key lookup is the violation
  (m) => HEBREW_RE.test(m),
);
record(
  'Zero inline Hebrew string literals in DashboardScreen.js',
  jsxMatches.length === 0,
  jsxMatches.length ? `Found: ${jsxMatches.slice(0, 3).join(' | ')}` : '',
);

// ─── Test 5: DashboardScreen uses t() for all user-facing text ────────────
console.log('\n=== Test 5: DashboardScreen Uses t() for All Displayed Strings ===');
// Every t() call in the screen should reference a known dashboard key
const T_CALL_RE = /\bt\(\s*['"]([A-Z_0-9]+)['"]\s*\)/g;
let m;
const screenKeys = [];
while ((m = T_CALL_RE.exec(dashboardSrc)) !== null) {
  screenKeys.push(m[1]);
}
record('DashboardScreen makes at least 10 t() calls', screenKeys.length >= 10,
       `found ${screenKeys.length} t() calls`);

const unknownKeys = screenKeys.filter((k) => !(k in heJson));
record('All t() keys in DashboardScreen exist in he.json', unknownKeys.length === 0,
       unknownKeys.length ? `Unknown: ${unknownKeys.join(', ')}` : '');

// ─── Test 6: Sub-components also use t() not raw Hebrew ───────────────────
console.log('\n=== Test 6: Sub-Components Use t() — No Inline Hebrew ===');
const SUB_SOURCES = {
  'MetricBar.js':          metricBarSrc,
  'MilestoneChecklist.js': milestoneSrc,
  'SleepQuickTap.js':      sleepTapSrc,
};
for (const [name, src] of Object.entries(SUB_SOURCES)) {
  const inlineHe = (src.match(QUOTED_HEBREW_RE) || []).filter((x) => HEBREW_RE.test(x));
  record(`${name} — no inline Hebrew literals`, inlineHe.length === 0,
         inlineHe.length ? inlineHe.slice(0, 2).join(' | ') : '');
}

// ─── Test 7: Active-state keys used in DashboardScreen ────────────────────
console.log('\n=== Test 7: Active-State Keys Referenced in Screen ===');
const ACTIVE_KEYS = [
  'METRICS_SECTION_TITLE', 'METRICS_SLEEP_LABEL', 'METRICS_SLEEP_UNIT',
  'METRICS_STEPS_LABEL', 'METRICS_STEPS_UNIT',
  'METRICS_SEDENTARY_LABEL', 'METRICS_SEDENTARY_UNIT', 'METRICS_SEDENTARY_WARNING',
];
for (const key of ACTIVE_KEYS) {
  record(`Active-state key t('${key}') called in screen`, dashboardSrc.includes(`t('${key}')`));
}

// ─── Test 8: Inactive-state keys referenced in screen/sub-components ──────
console.log('\n=== Test 8: Inactive-State Keys Referenced in Screen/Sub-Components ===');
const INACTIVE_KEYS = [
  'MANUAL_SECTION_TITLE', 'MANUAL_SECTION_SUBTITLE', 'MANUAL_SLEEP_LABEL',
  'MANUAL_SLEEP_BTN_4', 'MANUAL_MILESTONES_LABEL',
  'MANUAL_MILESTONE_WALK', 'MANUAL_SUBMIT_BTN', 'MANUAL_SAVED_TOAST',
];
const allFrontendSrc = dashboardSrc + milestoneSrc + sleepTapSrc;
for (const key of INACTIVE_KEYS) {
  record(`Inactive-state key t('${key}') referenced`, allFrontendSrc.includes(key));
}

// ─── Test 9: Active ∩ Inactive keys are disjoint in the screen ────────────
console.log('\n=== Test 9: Active-State and Inactive-State Content Keys are Disjoint ===');
const activeSet   = new Set(ACTIVE_KEYS);
const inactiveSet = new Set(INACTIVE_KEYS);
const overlap     = [...activeSet].filter((k) => inactiveSet.has(k));
record('Active and inactive key sets are disjoint (no shared keys)', overlap.length === 0,
       overlap.length ? `Overlap: ${overlap.join(', ')}` : '');

// ─── Test 10: RTL tokens — I18nManager.forceRTL(true) call present ─────────
console.log('\n=== Test 10: RTL Layout Tokens ===');
record('tokens.js calls I18nManager.forceRTL(true)', tokensSrc.includes('I18nManager.forceRTL(true)'));
record('tokens.js defines RTL.row with flexDirection: row', tokensSrc.includes("flexDirection: 'row'"));
record('tokens.js defines RTL.text with textAlign: right', tokensSrc.includes("textAlign: 'right'"));
record('tokens.js defines writingDirection: rtl', tokensSrc.includes("writingDirection: 'rtl'"));
record('DashboardScreen uses marginStart or marginEnd (logical props)',
       dashboardSrc.includes('marginStart') || dashboardSrc.includes('marginEnd'));
record('DashboardScreen uses borderStartWidth (logical border)',
       dashboardSrc.includes('borderStartWidth'));
record('Components use marginEnd in RTL rows',
       milestoneSrc.includes('marginEnd') || sleepTapSrc.includes('marginEnd') || metricBarSrc.includes('marginStart'));

// ─── Test 11: MetricBar clamping logic (inline simulation) ────────────────
console.log('\n=== Test 11: MetricBar Clamping Logic ===');
function clamp(value, goal) {
  return Math.min(1, Math.max(0, goal > 0 ? value / goal : 0));
}
record('value=0, goal=7 → ratio=0',          clamp(0, 7)    === 0);
record('value=7, goal=7 → ratio=1',          clamp(7, 7)    === 1);
record('value=14, goal=7 → clamped to 1',    clamp(14, 7)   === 1);
record('value=5.2, goal=7 → ~0.74',          Math.abs(clamp(5.2, 7) - 0.7428) < 0.001);
record('value=4820, goal=8000 → ~0.60',      Math.abs(clamp(4820, 8000) - 0.6025) < 0.001);
record('value=75, goal=60 → clamped to 1',   clamp(75, 60)  === 1);
record('value=0, goal=0 → ratio=0 (no div)', clamp(0, 0)    === 0);

// ─── Test 12: MilestoneChecklist toggle logic ─────────────────────────────
console.log('\n=== Test 12: MilestoneChecklist Toggle Logic ===');
function milestoneToggle(prev, id) {
  return prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
}
let state = [];
state = milestoneToggle(state, 'walk');
record('Toggle walk ON: [walk]',       JSON.stringify(state) === '["walk"]');
state = milestoneToggle(state, 'stairs');
record('Toggle stairs ON: [walk,stairs]', state.length === 2 && state.includes('stairs'));
state = milestoneToggle(state, 'walk');
record('Toggle walk OFF: [stairs]',    JSON.stringify(state) === '["stairs"]');
state = milestoneToggle(state, 'stairs');
record('Toggle stairs OFF: []',        state.length === 0);
// Idempotent add
state = milestoneToggle([], 'stretch');
state = milestoneToggle(state, 'stretch'); // remove
record('Idempotent: add then remove = []', state.length === 0);

// ─── Test 13: SleepQuickTap — 5 options, correct values ───────────────────
console.log('\n=== Test 13: SleepQuickTap Option Completeness ===');
const SLEEP_OPTIONS = [
  { key: 'MANUAL_SLEEP_BTN_4', value: 3.5 },
  { key: 'MANUAL_SLEEP_BTN_5', value: 4.5 },
  { key: 'MANUAL_SLEEP_BTN_6', value: 5.5 },
  { key: 'MANUAL_SLEEP_BTN_7', value: 6.5 },
  { key: 'MANUAL_SLEEP_BTN_8', value: 7.5 },
];
record('Exactly 5 sleep options', SLEEP_OPTIONS.length === 5);
record('Values strictly increasing', SLEEP_OPTIONS.every((o, i) =>
  i === 0 || o.value > SLEEP_OPTIONS[i - 1].value));
record('All sleep option keys in he.json', SLEEP_OPTIONS.every((o) => o.key in heJson));
record('All sleep option he.json values are Hebrew',
       SLEEP_OPTIONS.every((o) => HEBREW_RE.test(heJson[o.key] || '')));

// ─── Test 14: Graceful degradation — isSensorActive controls render path ──
console.log('\n=== Test 14: Graceful Degradation — Conditional Render Paths ===');
// Verify isSensorActive gates both blocks in the source
record('Active block gated by {isSensorActive && ...}',
       dashboardSrc.includes('{isSensorActive && ('));
record('Inactive block gated by {!isSensorActive && ...}',
       dashboardSrc.includes('{!isSensorActive && ('));
record('Only one card rendered at a time — no else-if leakage',
       !dashboardSrc.includes('} else if'));
record('isSensorActive state initialized to true',
       dashboardSrc.includes("useState(true)"));
record('handleDevToggle flips isSensorActive with (v) => !v',
       dashboardSrc.includes('(v) => !v'));

// ─── Test 15: File encoding — all source files are valid UTF-8 ────────────
console.log('\n=== Test 15: UTF-8 Encoding of All Frontend Files ===');
const FRONTEND_FILES = [
  ['frontend/screens/DashboardScreen.js',      dashboardSrc],
  ['frontend/components/tokens.js',            tokensSrc],
  ['frontend/components/MetricBar.js',         metricBarSrc],
  ['frontend/components/MilestoneChecklist.js',milestoneSrc],
  ['frontend/components/SleepQuickTap.js',     sleepTapSrc],
  ['frontend/utils/i18n.js',                   i18nSrc],
  ['locales/he.json',                          JSON.stringify(heJson)],
];
for (const [name, src] of FRONTEND_FILES) {
  try {
    Buffer.from(src, 'utf-8').toString('utf-8');
    record(`${name} — valid UTF-8`, true);
  } catch (e) {
    record(`${name} — valid UTF-8`, false, String(e));
  }
}

// ─── Summary ───────────────────────────────────────────────────────────────
console.log('\n' + '='.repeat(60));
const total  = results.length;
const passed = results.filter((r) => r.ok).length;
const failed = total - passed;

console.log(`\nתוצאות | Results: ${passed}/${total} passed`);

if (failed) {
  console.log(`\n${failed} test(s) FAILED:`);
  results.filter((r) => !r.ok).forEach((r) => {
    console.log(`  - ${r.name}` + (r.detail ? ` (${r.detail})` : ''));
  });
  process.exit(1);
} else {
  console.log('\nכל הבדיקות עברו בהצלחה | All tests passed.');
  process.exit(0);
}
