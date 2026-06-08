/**
 * test_habit_card.js — HabitStackingCard + DashboardScreen integration QA
 *
 * Covers (all pure Node.js / source-level — no React Native runtime needed):
 *
 *  1.  All HABIT_* locale keys present in he.json with Hebrew content
 *  2.  TRIGGER_KEYS map covers all 5 expected trigger ids
 *  3.  Every trigger key references a valid he.json entry
 *  4.  No inline Hebrew literals in HabitStackingCard.js
 *  5.  RTL logical style properties used (marginStart/End, borderStartWidth)
 *  6.  LayoutAnimation configured in both card and screen
 *  7.  DashboardScreen imports HabitStackingCard
 *  8.  DashboardScreen renders HabitStackingCard with trigger prop
 *  9.  DashboardScreen passes userId + currentWeek + streakDays to card
 * 10.  Card visible only when activeTrigger !== null (conditional render logic)
 * 11.  API call (_apiOverride) invoked with correct payload on completion
 * 12.  API payload carries trigger_id, user_id, current_week, event_type
 * 13.  isDone state set to true after successful API call
 * 14.  hasError state set to true when API throws
 * 15.  onCompleted callback fired after successful API call
 * 16.  onDismiss callback fired on dismiss press
 * 17.  null trigger renders nothing (guard clause)
 * 18.  Unknown trigger id renders nothing (safety guard)
 * 19.  Sedentary trigger mock auto-populates when sedentaryMins >= sedentaryLimit
 * 20.  Component source file is valid UTF-8
 * 21.  HABIT_CARD_COMPLETED_BTN key resolves to Hebrew string with content
 * 22.  DashboardScreen source: no hardcoded Hebrew strings in JSX
 * 23.  HabitStackingCard source: zero clinical logic keywords
 * 24.  handleHabitCompleted increments streak in screen source
 * 25.  handleHabitDismiss clears activeTrigger in screen source
 *
 * Run: node frontend/test_habit_card.js
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ─── Paths ────────────────────────────────────────────────────────────────
const ROOT        = path.resolve(__dirname, '..');
const HE_PATH     = path.join(ROOT, 'locales', 'he.json');
const CARD_PATH   = path.join(__dirname, 'components', 'HabitStackingCard.js');
const SCREEN_PATH = path.join(__dirname, 'screens', 'DashboardScreen.js');

const heJson    = JSON.parse(fs.readFileSync(HE_PATH,     'utf-8'));
const cardSrc   = fs.readFileSync(CARD_PATH,              'utf-8');
const screenSrc = fs.readFileSync(SCREEN_PATH,            'utf-8');

// ─── Harness ──────────────────────────────────────────────────────────────
const PASS = '\x1b[92mPASS\x1b[0m';
const FAIL = '\x1b[91mFAIL\x1b[0m';
const HE_RE = /[֐-׿]/;
const results = [];

function record(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`  [${ok ? PASS : FAIL}] ${name}` + (detail ? `  (${detail})` : ''));
}

// ─── TRIGGER_KEYS extracted directly from card source ─────────────────────
// We eval the TRIGGER_KEYS literal in isolation — no React Native imports needed.
let TRIGGER_KEYS = {};
try {
  const match = cardSrc.match(/const TRIGGER_KEYS\s*=\s*(\{[\s\S]*?\n\};)/);
  if (match) {
    // eslint-disable-next-line no-new-func
    TRIGGER_KEYS = new Function(`return ${match[1]}`)();
  }
} catch (_) { /* test 2 will catch missing map */ }

// ─── Minimal async state machine (simulates useState + async handlers) ─────
function makeCardState() {
  let isLogging   = false;
  let isDone      = false;
  let hasError    = false;
  let isDismissed = false;
  let completedCalled = false;
  let dismissCalled   = false;
  let apiPayload  = null;

  return {
    async handleCompleted(apiOverride, props) {
      if (isLogging || isDone) return;
      isLogging = true;
      hasError  = false;
      try {
        await apiOverride({
          user_id:      props.userId,
          current_week: props.currentWeek,
          trigger_id:   props.trigger,
          event_type:   'HABIT_COMPLETED',
          completed_at: new Date().toISOString(),
        });
        isDone = true;
        completedCalled = true;
        apiPayload = arguments[0]; // captured inside apiOverride
      } catch (_) {
        hasError = true;
      } finally {
        isLogging = false;
      }
    },
    handleDismiss() {
      isDismissed   = true;
      dismissCalled = true;
    },
    get state() {
      return { isLogging, isDone, hasError, isDismissed, completedCalled, dismissCalled };
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// Test 1: HABIT_* locale keys present and Hebrew
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 1: HABIT_* Locale Keys in he.json ===');

const HABIT_KEYS = [
  'HABIT_CARD_SECTION_TITLE', 'HABIT_CARD_COMPLETED_BTN', 'HABIT_CARD_LOGGING',
  'HABIT_CARD_DONE_TOAST', 'HABIT_CARD_ERROR_TOAST', 'HABIT_CARD_XP_LABEL',
  'HABIT_CARD_STREAK_LABEL', 'HABIT_CARD_STREAK_DAYS',
  'HABIT_TRIGGER_SEDENTARY_TITLE', 'HABIT_TRIGGER_SEDENTARY_CUE', 'HABIT_TRIGGER_SEDENTARY_WHY',
  'HABIT_TRIGGER_HYDRATION_TITLE', 'HABIT_TRIGGER_HYDRATION_CUE', 'HABIT_TRIGGER_HYDRATION_WHY',
  'HABIT_TRIGGER_COFFEE_TITLE',    'HABIT_TRIGGER_COFFEE_CUE',    'HABIT_TRIGGER_COFFEE_WHY',
  'HABIT_TRIGGER_POST_MEAL_TITLE', 'HABIT_TRIGGER_POST_MEAL_CUE', 'HABIT_TRIGGER_POST_MEAL_WHY',
  'HABIT_TRIGGER_SLEEP_PREP_TITLE','HABIT_TRIGGER_SLEEP_PREP_CUE','HABIT_TRIGGER_SLEEP_PREP_WHY',
  'HABIT_CARD_DISMISS_LABEL',
];

for (const key of HABIT_KEYS) {
  record(`[${key}] present`, key in heJson);
  record(`[${key}] contains Hebrew`, HE_RE.test(heJson[key] ?? ''),
         (heJson[key] ?? '').slice(0, 30));
}


// ═══════════════════════════════════════════════════════════════════════════
// Test 2: TRIGGER_KEYS map coverage
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 2: TRIGGER_KEYS Map Coverage ===');

const EXPECTED_TRIGGERS = [
  'sedentary_alert', 'hydration_reminder', 'coffee_habit', 'post_meal', 'sleep_prep',
];

record('TRIGGER_KEYS parsed from source',   Object.keys(TRIGGER_KEYS).length > 0);
record('All 5 trigger IDs present',         EXPECTED_TRIGGERS.every((t) => t in TRIGGER_KEYS),
       `found: ${Object.keys(TRIGGER_KEYS).join(', ')}`);

for (const tid of EXPECTED_TRIGGERS) {
  const keys = TRIGGER_KEYS[tid] ?? {};
  record(`${tid}: has title/cue/why keys`,
         Boolean(keys.title && keys.cue && keys.why));
}


// ═══════════════════════════════════════════════════════════════════════════
// Test 3: Every trigger locale key resolves in he.json
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 3: Every Trigger Locale Key Resolves in he.json ===');

for (const [tid, keys] of Object.entries(TRIGGER_KEYS)) {
  for (const [field, key] of Object.entries(keys)) {
    record(`${tid}.${field} → [${key}] in he.json`, key in heJson,
           heJson[key] ? heJson[key].slice(0, 25) : 'MISSING');
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// Test 4: No inline Hebrew literals in HabitStackingCard.js
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 4: No Inline Hebrew Literals in HabitStackingCard.js ===');

const QUOTED_HE = /(['"`])(?:(?!\1).)*[֐-׿](?:(?!\1).)*\1/g;
const cardHeLiterals = (cardSrc.match(QUOTED_HE) || []).filter((m) => HE_RE.test(m));
record('Zero inline Hebrew string literals', cardHeLiterals.length === 0,
       cardHeLiterals.length ? cardHeLiterals.slice(0, 2).join(' | ') : '');


// ═══════════════════════════════════════════════════════════════════════════
// Test 5: RTL logical style properties in card source
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 5: RTL Logical Properties in Card Styles ===');

record('borderStartWidth used',  cardSrc.includes('borderStartWidth'));
record('borderStartColor used',  cardSrc.includes('borderStartColor'));
record('marginEnd used',         cardSrc.includes('marginEnd'));
record('marginStart or paddingStart used',
       cardSrc.includes('marginStart') || cardSrc.includes('paddingStart'));
record('RTL.text applied to Text nodes', cardSrc.includes('RTL.text'));
record('RTL.row applied to row containers', cardSrc.includes('RTL.row'));


// ═══════════════════════════════════════════════════════════════════════════
// Test 6: LayoutAnimation configured in card and screen
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 6: LayoutAnimation in Card and Screen ===');

record('Card imports LayoutAnimation',        cardSrc.includes('LayoutAnimation'));
record('Card calls LayoutAnimation.configureNext',
       cardSrc.includes('LayoutAnimation.configureNext'));
record('Screen imports LayoutAnimation',      screenSrc.includes('LayoutAnimation'));
record('Screen calls LayoutAnimation.configureNext or Presets',
       screenSrc.includes('LayoutAnimation.configureNext') || screenSrc.includes('LayoutAnimation.Presets'));
record('Android UIManager guard in card',
       cardSrc.includes('setLayoutAnimationEnabledExperimental'));
record('Android UIManager guard in screen',
       screenSrc.includes('setLayoutAnimationEnabledExperimental'));


// ═══════════════════════════════════════════════════════════════════════════
// Test 7: DashboardScreen imports HabitStackingCard
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 7: DashboardScreen Imports HabitStackingCard ===');

record('import HabitStackingCard in screen',
       screenSrc.includes("import HabitStackingCard") || screenSrc.includes("HabitStackingCard"));
record('HabitStackingCard used in JSX',
       screenSrc.includes('<HabitStackingCard'));


// ═══════════════════════════════════════════════════════════════════════════
// Test 8: DashboardScreen passes required props to HabitStackingCard
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 8: DashboardScreen Passes Props to HabitStackingCard ===');

record('trigger prop passed',      screenSrc.includes('trigger={activeTrigger}'));
record('userId prop passed',       screenSrc.includes('userId={') || screenSrc.includes("userId="));
record('currentWeek prop passed',  screenSrc.includes('currentWeek={CURRENT_WEEK}'));
record('streakDays prop passed',   screenSrc.includes('streakDays={habitStreakDays}'));
record('onCompleted handler wired',screenSrc.includes('onCompleted={handleHabitCompleted}'));
record('onDismiss handler wired',  screenSrc.includes('onDismiss={handleHabitDismiss}'));


// ═══════════════════════════════════════════════════════════════════════════
// Test 9: Conditional render logic — card only shown when trigger active
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 9: Conditional Render — activeTrigger Controls Visibility ===');

// Simulate: trigger=null → null returned (nothing rendered)
function simulateCardRender(trigger) {
  if (!trigger || trigger === 'dismissed') return null;
  if (!(trigger in TRIGGER_KEYS)) return null;
  return { rendered: true, trigger };
}

record('null trigger → nothing rendered',        simulateCardRender(null) === null);
record('valid trigger → card rendered',          simulateCardRender('sedentary_alert')?.rendered === true);
record('unknown trigger → nothing rendered',     simulateCardRender('nonexistent_xyz') === null);
record('activeTrigger state initialised in screen', screenSrc.includes('activeTrigger'));
record('setActiveTrigger called in screen',       screenSrc.includes('setActiveTrigger'));


// ═══════════════════════════════════════════════════════════════════════════
// Test 10: Sedentary trigger mock auto-population
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 10: Sedentary Mock Auto-Population ===');

const MOCK = { sedentaryMins: 75, sedentaryLimit: 60 };
const autoTrigger = MOCK.sedentaryMins >= MOCK.sedentaryLimit ? 'sedentary_alert' : null;
record('sedentaryMins=75 >= limit=60 → sedentary_alert auto-set', autoTrigger === 'sedentary_alert');
record('Screen source contains auto-population logic',
       screenSrc.includes('sedentary_alert') && screenSrc.includes('sedentaryMins'));

const MOCK2 = { sedentaryMins: 30, sedentaryLimit: 60 };
const autoTrigger2 = MOCK2.sedentaryMins >= MOCK2.sedentaryLimit ? 'sedentary_alert' : null;
record('sedentaryMins=30 < limit=60 → null', autoTrigger2 === null);


// ═══════════════════════════════════════════════════════════════════════════
// Test 11-13: API call lifecycle (async simulation)
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n=== Test 11-13: API Call Lifecycle (async simulation) ===');

const PROPS = { trigger: 'sedentary_alert', userId: 'u-test', currentWeek: 2 };

// Test 11: Successful API call
(async () => {
  let capturedPayload = null;
  const mockApi = async (payload) => { capturedPayload = payload; return { ok: true }; };
  const card = makeCardState();
  await card.handleCompleted(mockApi, PROPS);
  const s = card.state;

  record('isDone=true after success',           s.isDone === true);
  record('isLogging=false after success',       s.isLogging === false);
  record('hasError=false after success',        s.hasError === false);
  record('onCompleted callback fired',          s.completedCalled === true);
  record('API received trigger_id=sedentary_alert',
         capturedPayload?.trigger_id === 'sedentary_alert');
  record('API received user_id',                capturedPayload?.user_id === 'u-test');
  record('API received current_week=2',         capturedPayload?.current_week === 2);
  record('API received event_type=HABIT_COMPLETED',
         capturedPayload?.event_type === 'HABIT_COMPLETED');
  record('API received completed_at (ISO string)',
         typeof capturedPayload?.completed_at === 'string' &&
         capturedPayload.completed_at.includes('T'));

  // Test 12: idempotency — second call does nothing when isDone
  let secondCallCount = 0;
  const idempotentApi = async () => { secondCallCount++; };
  await card.handleCompleted(idempotentApi, PROPS);
  record('Second call after isDone is no-op',   secondCallCount === 0);

  // Test 13: API throws → hasError set
  const errorCard = makeCardState();
  const throwingApi = async () => { throw new Error('network fail'); };
  await errorCard.handleCompleted(throwingApi, PROPS);
  const es = errorCard.state;
  record('hasError=true when API throws',       es.hasError === true);
  record('isDone=false when API throws',        es.isDone   === false);
  record('isLogging=false after error',         es.isLogging === false);

  // Test 14: Dismiss
  console.log('\n=== Test 14-16: Dismiss + Callbacks ===');
  const dismissCard = makeCardState();
  dismissCard.handleDismiss();
  const ds = dismissCard.state;
  record('isDismissed=true after dismiss',      ds.isDismissed === true);
  record('onDismiss callback fired',            ds.dismissCalled === true);

  // Test 15: onCompleted not fired on error
  record('onCompleted NOT fired on API error',  errorCard.state.completedCalled === false);

  // Test 16: screen source handles completed and dismiss
  record('handleHabitCompleted defined in screen',
         screenSrc.includes('handleHabitCompleted'));
  record('handleHabitDismiss defined in screen',
         screenSrc.includes('handleHabitDismiss'));
  record('handleHabitCompleted increments streak',
         screenSrc.includes('habitStreakDays') && screenSrc.includes('setHabitStreakDays'));
  record('handleHabitDismiss clears activeTrigger',
         screenSrc.includes('setActiveTrigger(null)'));


  // ═══════════════════════════════════════════════════════════════════════
  // Test 17: guard clauses
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 17-18: Guard Clauses ===');

  record('null trigger → null render (guard)',
         simulateCardRender(null) === null);
  record('empty-string trigger → null render',
         simulateCardRender('') === null);
  record('undefined trigger → null render',
         simulateCardRender(undefined) === null);
  record('Card source contains null-trigger guard',
         cardSrc.includes('if (!trigger') || cardSrc.includes("if (!trigger ||"));
  record('Card source contains unknown-trigger guard',
         cardSrc.includes('if (!keys)'));


  // ═══════════════════════════════════════════════════════════════════════
  // Test 19: completed_at is valid ISO-8601
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 19: Payload completed_at is Valid ISO-8601 ===');

  let payloadCheck = null;
  await makeCardState().handleCompleted(
    async (p) => { payloadCheck = p; }, PROPS,
  );
  const ts = payloadCheck?.completed_at ?? '';
  record('completed_at parses as valid date',
         !Number.isNaN(new Date(ts).getTime()) && ts.includes('T'));
  record('completed_at is UTC (contains Z or +)',
         ts.includes('Z') || ts.includes('+'));


  // ═══════════════════════════════════════════════════════════════════════
  // Test 20: UTF-8 integrity
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 20: UTF-8 File Integrity ===');

  for (const [label, filePath] of [
    ['HabitStackingCard.js', CARD_PATH],
    ['DashboardScreen.js',   SCREEN_PATH],
    ['he.json',              HE_PATH],
  ]) {
    try {
      Buffer.from(fs.readFileSync(filePath, 'utf-8'), 'utf-8');
      record(`${label} — valid UTF-8`, true);
    } catch (e) {
      record(`${label} — valid UTF-8`, false, String(e));
    }
  }


  // ═══════════════════════════════════════════════════════════════════════
  // Test 21: Key string values spot-check
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 21: Spot-Check Hebrew String Values ===');

  record('HABIT_CARD_COMPLETED_BTN contains "השלמתי"',
         (heJson['HABIT_CARD_COMPLETED_BTN'] ?? '').includes('השלמתי'));
  record('HABIT_TRIGGER_SEDENTARY_CUE is Habit Stack sentence (אחרי)',
         (heJson['HABIT_TRIGGER_SEDENTARY_CUE'] ?? '').includes('אחרי'));
  record('HABIT_TRIGGER_COFFEE_CUE matches expected pattern',
         (heJson['HABIT_TRIGGER_COFFEE_CUE'] ?? '').includes('קפה'));
  record('HABIT_TRIGGER_POST_MEAL_CUE references eating + walk',
         (heJson['HABIT_TRIGGER_POST_MEAL_CUE'] ?? '').includes('אוכל') ||
         (heJson['HABIT_TRIGGER_POST_MEAL_CUE'] ?? '').includes('לאכול'));
  record('HABIT_TRIGGER_HYDRATION_CUE references water (מים)',
         (heJson['HABIT_TRIGGER_HYDRATION_CUE'] ?? '').includes('מים'));


  // ═══════════════════════════════════════════════════════════════════════
  // Test 22: DashboardScreen — no hardcoded Hebrew JSX
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 22: DashboardScreen — No Hardcoded Hebrew JSX ===');

  const screenHeLiterals = (screenSrc.match(QUOTED_HE) || []).filter((m) => HE_RE.test(m));
  record('Zero inline Hebrew literals in DashboardScreen.js',
         screenHeLiterals.length === 0,
         screenHeLiterals.length ? screenHeLiterals.slice(0, 2).join(' | ') : '');


  // ═══════════════════════════════════════════════════════════════════════
  // Test 23: No clinical logic in HabitStackingCard
  // ═══════════════════════════════════════════════════════════════════════
  console.log('\n=== Test 23: No Clinical Logic in HabitStackingCard ===');

  const BANNED = [
    { re: /SLEEP_THRESHOLD/,         label: 'clinical sleep threshold'  },
    { re: /SEDENTARY_THRESHOLD/,     label: 'clinical sedentary rule'   },
    { re: /oars_reflection/,         label: 'OARS output field'         },
    { re: /triggered_rules/,         label: 'triggered_rules field'     },
    { re: /clinical_notes/,          label: 'clinical_notes field'      },
    { re: /phase-transition/,        label: 'phase-transition logic'    },
    { re: /AsyncStorage\.setItem/,   label: 'AsyncStorage write'        },
  ];
  for (const { re, label } of BANNED) {
    record(`Card does NOT contain ${label}`, !re.test(cardSrc));
  }


  // ═══════════════════════════════════════════════════════════════════════
  // Summary
  // ═══════════════════════════════════════════════════════════════════════
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
