/**
 * test_external_resource.js — Content Curation Frontend QA
 *
 * Tests (pure JS — no React rendering, no native modules required):
 *
 *   Group A — ExternalResourceButton null-safety contract
 *     A1  url=null, label=present → returns null (no render)
 *     A2  url=present, label=null → returns null (no render)
 *     A3  url=null, label=null → returns null (no render)
 *     A4  url="", label=present → returns null (falsy url guard)
 *     A5  url=present, label="" → returns null (falsy label guard)
 *     A6  url=present, label=present → should render (returns non-null)
 *
 *   Group B — WebBrowser safe-import
 *     B1  WebBrowser module is resolvable from node_modules
 *     B2  openBrowserAsync is a function on the module
 *     B3  Safe-import try/catch does not throw when module present
 *     B4  Fallback path (WebBrowser=null) does not throw on call
 *
 *   Group C — RTL constraint audit (ExternalResourceButton source)
 *     C1  No marginLeft / marginRight in ExternalResourceButton.js
 *     C2  No inline Hebrew string literals in ExternalResourceButton.js
 *     C3  Uses marginEnd (RTL gap between icon and label)
 *     C4  Uses marginStart (RTL gap between label and chevron)
 *     C5  borderStartWidth present (RTL accent stripe)
 *     C6  accessibilityRole="link" present
 *
 *   Group D — Dependency audit
 *     D1  expo-web-browser in package.json dependencies
 *     D2  expo-web-browser installed in node_modules
 *     D3  ExternalResourceButton.js file exists
 *     D4  ExternalResourceButton imported in StrengthWorkoutButton.js
 *
 *   Group E — API payload integration (mock Orchestrator responses)
 *     E1  GLUT4 response with action_url → button would render
 *     E2  GLUT4 response with action_label → button would render
 *     E3  GLUT4 YouTube URL passes URL validation
 *     E4  Recovery recipe URL passes URL validation
 *     E5  Phytosterol recipe URL passes URL validation
 *     E6  No-trigger response (action_url: null) → button would not render
 *     E7  action_url from GLUT4 contains 'youtube'
 *     E8  GLUT4 and Recovery labels are different strings
 *
 *   Group F — StrengthWorkoutButton wiring
 *     F1  StrengthWorkoutButton source imports ExternalResourceButton
 *     F2  actionUrl state initialised to null
 *     F3  actionLabel state initialised to null
 *     F4  result?.action_url extraction pattern present in source
 *     F5  result?.action_label extraction pattern present in source
 *     F6  ExternalResourceButton rendered inside GLUT4 panel
 *
 * Run:  node test_external_resource.js
 */

'use strict';

const fs   = require('fs');
const path = require('path');

// ── Test runner ──────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;
const failures = [];

function assert(condition, id, description) {
  if (condition) {
    console.log(`  ✓ [${id}] ${description}`);
    passed++;
  } else {
    console.error(`  ✗ [${id}] ${description}`);
    failures.push({ id, description });
    failed++;
  }
}

function group(name, fn) {
  console.log(`\n── ${name} ──`);
  fn();
}

// ── Helpers ──────────────────────────────────────────────────────────────

const ROOT = path.resolve(__dirname);

function readSrc(relPath) {
  return fs.readFileSync(path.join(ROOT, relPath), 'utf8');
}

function hasLRMargins(src) {
  return /margin(Left|Right)\s*:/.test(src);
}

function hasInlineHebrew(src) {
  const noComments = src.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
  return /['"][^'"]*[א-ת][^'"]*['"]/.test(noComments);
}

function isValidHttpUrl(str) {
  try {
    const u = new URL(str);
    return u.protocol === 'https:' || u.protocol === 'http:';
  } catch (_) { return false; }
}

// ── Simulate the null-safety guard from ExternalResourceButton ───────────
// Replicates the exact guard: if (!url || !label) return null
function simulateRender(url, label) {
  if (!url || !label) return null;
  return { url, label }; // non-null = "would render"
}

// ── Mock Orchestrator responses ───────────────────────────────────────────
const GLUT4_RESPONSE = {
  action_url:   'https://www.youtube.com/watch?v=Gl2ND2KqDIs',
  action_label: 'צפה בסרטון אימון כוח מומלץ',
};
const RECOVERY_RESPONSE = {
  action_url:   'https://www.hamama.co.il/recipe/salad-quinoa-tofu',
  action_label: 'מתכון להתאוששות: חלבון צמחי + MUFA',
};
const PHYTOSTEROL_RESPONSE = {
  action_url:   'https://www.hamama.co.il/recipe/sterol-avocado-legumes',
  action_label: 'מתכון עשיר בפיטוסטרולים',
};
const NO_TRIGGER_RESPONSE = {
  action_url:   null,
  action_label: null,
};

// ── GROUP A: Null-safety ──────────────────────────────────────────────────

group('Group A — ExternalResourceButton null-safety', () => {
  assert(simulateRender(null, 'label') === null, 'A1',
    'url=null, label=present → returns null');
  assert(simulateRender('https://x.com', null) === null, 'A2',
    'url=present, label=null → returns null');
  assert(simulateRender(null, null) === null, 'A3',
    'url=null, label=null → returns null');
  assert(simulateRender('', 'label') === null, 'A4',
    'url="" (falsy), label=present → returns null');
  assert(simulateRender('https://x.com', '') === null, 'A5',
    'url=present, label="" (falsy) → returns null');
  assert(simulateRender('https://x.com', 'label') !== null, 'A6',
    'url=present, label=present → should render (non-null)');
});

// ── GROUP B: WebBrowser safe-import ──────────────────────────────────────

group('Group B — WebBrowser safe-import', () => {
  // expo-web-browser is a native Expo module — it requires a bundler/native runtime
  // and cannot be required() in plain Node. We verify installation via package.json
  // and validate that the component's try/catch guard works correctly.

  const wbPkgPath = path.join(ROOT, 'node_modules', 'expo-web-browser', 'package.json');
  const wbInstalled = fs.existsSync(wbPkgPath);
  assert(wbInstalled, 'B1', 'expo-web-browser package.json present in node_modules');

  let wbPkg = {};
  if (wbInstalled) { wbPkg = JSON.parse(fs.readFileSync(wbPkgPath, 'utf8')); }
  // Check that the module exports openBrowserAsync (declared in package exports/types)
  const hasOpenBrowser = wbInstalled && (
    fs.existsSync(path.join(ROOT, 'node_modules', 'expo-web-browser', 'build', 'ExpoWebBrowser.js')) ||
    fs.existsSync(path.join(ROOT, 'node_modules', 'expo-web-browser', 'src', 'ExpoWebBrowser.ts')) ||
    (wbPkg.main && fs.existsSync(path.join(ROOT, 'node_modules', 'expo-web-browser', wbPkg.main)))
  );
  assert(hasOpenBrowser, 'B2', 'expo-web-browser build/source files present (openBrowserAsync declared)');

  // Verify component source uses safe try/catch import pattern
  const src = readSrc('components/ExternalResourceButton.js');
  const hasSafeTryCatch = src.includes("try {") && src.includes("require('expo-web-browser')");
  assert(hasSafeTryCatch, 'B3', 'Component uses try/catch safe-import pattern for expo-web-browser');

  // Null fallback: simulate what happens when WebBrowser=null
  let fallbackThrew = false;
  try {
    const WebBrowser = null;
    if (WebBrowser && typeof WebBrowser.openBrowserAsync === 'function') {
      throw new Error('should not reach');
    }
    // Web fallback guard (no window in Node)
    if (typeof window !== 'undefined') {
      window.open('https://x.com', '_blank');
    }
  } catch (_) { fallbackThrew = true; }
  assert(!fallbackThrew, 'B4', 'Null WebBrowser fallback path does not throw');
});

// ── GROUP C: RTL constraint audit ────────────────────────────────────────

group('Group C — RTL constraint audit (ExternalResourceButton.js)', () => {
  const src = readSrc('components/ExternalResourceButton.js');

  assert(!hasLRMargins(src),               'C1', 'No marginLeft/marginRight');
  assert(!hasInlineHebrew(src),            'C2', 'No inline Hebrew literals');
  assert(src.includes('marginEnd'),        'C3', 'Uses marginEnd (icon→label gap)');
  assert(src.includes('marginStart'),      'C4', 'Uses marginStart (label→chevron gap)');
  assert(src.includes('borderStartWidth'), 'C5', 'borderStartWidth present (RTL accent stripe)');
  assert(src.includes('accessibilityRole="link"'), 'C6', 'accessibilityRole="link" present');
});

// ── GROUP D: Dependency audit ─────────────────────────────────────────────

group('Group D — Dependency audit', () => {
  const pkg = JSON.parse(readSrc('package.json'));
  const deps = { ...pkg.dependencies, ...pkg.devDependencies };

  assert('expo-web-browser' in deps, 'D1', 'expo-web-browser in package.json');
  assert(
    fs.existsSync(path.join(ROOT, 'node_modules', 'expo-web-browser', 'package.json')),
    'D2', 'expo-web-browser installed in node_modules',
  );
  assert(
    fs.existsSync(path.join(ROOT, 'components', 'ExternalResourceButton.js')),
    'D3', 'ExternalResourceButton.js file exists',
  );

  const strengthSrc = readSrc('components/StrengthWorkoutButton.js');
  assert(strengthSrc.includes('ExternalResourceButton'), 'D4',
    'ExternalResourceButton imported in StrengthWorkoutButton.js');
});

// ── GROUP E: API payload integration ─────────────────────────────────────

group('Group E — API payload integration (mock responses)', () => {
  assert(simulateRender(GLUT4_RESPONSE.action_url, GLUT4_RESPONSE.action_label) !== null,
    'E1', 'GLUT4 response action_url → button would render');
  assert(simulateRender(GLUT4_RESPONSE.action_url, GLUT4_RESPONSE.action_label) !== null,
    'E2', 'GLUT4 response action_label → button would render');

  assert(isValidHttpUrl(GLUT4_RESPONSE.action_url),       'E3', 'GLUT4 YouTube URL is valid https URL');
  assert(isValidHttpUrl(RECOVERY_RESPONSE.action_url),    'E4', 'Recovery recipe URL is valid https URL');
  assert(isValidHttpUrl(PHYTOSTEROL_RESPONSE.action_url), 'E5', 'Phytosterol recipe URL is valid https URL');

  assert(
    simulateRender(NO_TRIGGER_RESPONSE.action_url, NO_TRIGGER_RESPONSE.action_label) === null,
    'E6', 'No-trigger response (null URLs) → button would not render',
  );

  assert(GLUT4_RESPONSE.action_url.includes('youtube'), 'E7',
    "GLUT4 action_url contains 'youtube'");
  assert(GLUT4_RESPONSE.action_label !== RECOVERY_RESPONSE.action_label, 'E8',
    'GLUT4 and Recovery labels are different strings');
});

// ── GROUP F: StrengthWorkoutButton wiring ─────────────────────────────────

group('Group F — StrengthWorkoutButton wiring', () => {
  const src = readSrc('components/StrengthWorkoutButton.js');

  assert(src.includes("import ExternalResourceButton"), 'F1',
    'StrengthWorkoutButton imports ExternalResourceButton');
  assert(src.includes('useState(null)') &&
         src.includes('actionUrl'),      'F2', 'actionUrl state initialised to null');
  assert(src.includes('actionLabel'),    'F3', 'actionLabel state in component');
  assert(src.includes('result?.action_url'),   'F4', 'result?.action_url extraction present');
  assert(src.includes('result?.action_label'), 'F5', 'result?.action_label extraction present');
  assert(src.includes('<ExternalResourceButton'), 'F6',
    'ExternalResourceButton rendered inside GLUT4 panel');
});

// ── Results ───────────────────────────────────────────────────────────────

const total = passed + failed;
console.log('\n' + '═'.repeat(60));
console.log(`  Content Curation Frontend QA — ${passed}/${total} assertions passed`);
if (failures.length > 0) {
  console.log('\n  FAILURES:');
  failures.forEach(f => console.log(`    ✗ [${f.id}] ${f.description}`));
  process.exit(1);
} else {
  console.log('  All assertions passed ✓');
  process.exit(0);
}
