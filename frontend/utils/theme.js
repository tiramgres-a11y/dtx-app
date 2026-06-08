// @flow
/**
 * theme.js — Dynamic Time-of-Day Theming
 *
 * Derives a theme palette from the current hour so the Dashboard
 * feels energetic in the morning and calming / "Engine Shutdown" by evening.
 *
 * Periods:
 *   dawn    05:00–08:59  — soft sunrise (light amber + sky blue)
 *   day     09:00–16:59  — energetic / bright (full blue + white)
 *   dusk    17:00–19:59  — warm golden-hour tones
 *   evening 20:00–22:59  — "Engine Shutdown" (deep indigo + warm slate)
 *   night   23:00–04:59  — darkest rest tones (deep navy)
 *
 * All colours chosen to maintain WCAG AA contrast on white text.
 * No clinical meaning — purely ambient / motivational UX.
 */

import { COLORS } from '../components/tokens';

// ── Period definitions ────────────────────────────────────────────────────

export const TIME_PERIODS = {
  dawn:    'dawn',
  day:     'day',
  dusk:    'dusk',
  evening: 'evening',
  night:   'night',
};

/**
 * Returns which time-period the given hour (0–23) falls into.
 * @param {number} hour
 * @returns {string} TIME_PERIODS key
 */
export function getPeriod(hour) {
  if (hour >= 5  && hour <= 8)  return TIME_PERIODS.dawn;
  if (hour >= 9  && hour <= 16) return TIME_PERIODS.day;
  if (hour >= 17 && hour <= 19) return TIME_PERIODS.dusk;
  if (hour >= 20 && hour <= 22) return TIME_PERIODS.evening;
  return TIME_PERIODS.night;
}

// ── Theme palettes ────────────────────────────────────────────────────────

const THEMES = {
  dawn: {
    background:     '#FFF7ED',   // warm white-orange
    headerBg:       '#FFFBF5',
    accent:         '#F59E0B',   // amber
    accentLight:    '#FEF3C7',
    cardBg:         '#FFFFFF',
    cardShadow:     '#F59E0B22',
    greeting:       COLORS.textPrimary,
    weekLabel:      '#92400E',
    progressAccent: '#F59E0B',
    statusBarStyle: 'dark',
    isDark:         false,
  },
  day: {
    background:     COLORS.surfaceAlt,  // #F8FAFC — standard bright
    headerBg:       COLORS.surface,
    accent:         COLORS.primary,     // #2563EB — brand blue
    accentLight:    COLORS.primaryLight,
    cardBg:         COLORS.surface,
    cardShadow:     '#00000015',
    greeting:       COLORS.textPrimary,
    weekLabel:      COLORS.textSecondary,
    progressAccent: COLORS.primary,
    statusBarStyle: 'dark',
    isDark:         false,
  },
  dusk: {
    background:     '#FFF8F0',   // warm cream
    headerBg:       '#FFF1E0',
    accent:         '#EA580C',   // orange
    accentLight:    '#FFEDD5',
    cardBg:         '#FFFFFF',
    cardShadow:     '#EA580C18',
    greeting:       '#7C2D12',
    weekLabel:      '#9A3412',
    progressAccent: '#EA580C',
    statusBarStyle: 'dark',
    isDark:         false,
  },
  evening: {
    // "Engine Shutdown" — deep indigo, warm slate, restful
    background:     '#1E1B4B',   // deep indigo
    headerBg:       '#312E81',
    accent:         '#818CF8',   // light indigo
    accentLight:    '#3730A3',
    cardBg:         '#2E2A5E',
    cardShadow:     '#00000040',
    greeting:       '#E0E7FF',
    weekLabel:      '#A5B4FC',
    progressAccent: '#818CF8',
    statusBarStyle: 'light',
    isDark:         true,
  },
  night: {
    background:     '#0F172A',   // deep navy
    headerBg:       '#1E293B',
    accent:         '#6366F1',   // indigo
    accentLight:    '#1E1B4B',
    cardBg:         '#1E293B',
    cardShadow:     '#00000060',
    greeting:       '#CBD5E1',
    weekLabel:      '#94A3B8',
    progressAccent: '#6366F1',
    statusBarStyle: 'light',
    isDark:         true,
  },
};

// ── Public API ────────────────────────────────────────────────────────────

/**
 * Returns the theme object for the current system time.
 * Pass a custom hour in tests to verify all branches.
 * @param {number} [overrideHour]
 * @returns {{ background, headerBg, accent, accentLight, cardBg, cardShadow,
 *             greeting, weekLabel, progressAccent, statusBarStyle, isDark, period }}
 */
export function getTheme(overrideHour) {
  const hour   = overrideHour !== undefined ? overrideHour : new Date().getHours();
  const period = getPeriod(hour);
  return { ...THEMES[period], period };
}

export default getTheme;
