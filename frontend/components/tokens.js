// @flow
/**
 * Design tokens and RTL layout helpers.
 * RTL.row  / RTL.rowReverse flip flexDirection for Hebrew reading order.
 * All spacing, color, and radius decisions live here — not in screen files.
 */

import { I18nManager, StyleSheet, Platform } from 'react-native';

// forceRTL is a native-only API — crashes silently on web
if (Platform.OS !== 'web') {
  I18nManager.forceRTL(true);
}

// ─── Colors ────────────────────────────────────────────────────────────────
export const COLORS = {
  primary:      '#2563EB',  // brand blue
  primaryLight: '#EFF6FF',
  success:      '#16A34A',
  warning:      '#D97706',
  danger:       '#DC2626',
  surface:      '#FFFFFF',
  surfaceAlt:   '#F8FAFC',
  border:       '#E2E8F0',
  textPrimary:  '#0F172A',
  textSecondary:'#64748B',
  textDisabled: '#CBD5E1',
  trackBg:      '#E2E8F0',
  sleepFill:    '#6366F1',  // indigo
  stepsFill:    '#2563EB',  // blue
  sedentaryFill:'#EF4444',  // red — alert colour
  checkboxOn:     '#2563EB',
  checkboxOff:    '#E2E8F0',
  strengthFill:   '#7C3AED',  // purple — Phase 2 strength sessions
};

// ─── Typography ────────────────────────────────────────────────────────────
export const FONT = {
  xxs: 11,
  xs:  12,
  sm:  14,
  md:  16,
  lg:  18,
  xl:  22,
  xxl: 28,
};

// ─── Spacing ───────────────────────────────────────────────────────────────
export const SPACING = {
  xxs: 4,
  xs:  8,
  sm:  12,
  md:  16,
  lg:  24,
  xl:  32,
};

// ─── Border radius ─────────────────────────────────────────────────────────
export const RADIUS = {
  sm:   6,
  md:   10,
  lg:   16,
  pill: 999,
};

// ─── RTL layout helpers ────────────────────────────────────────────────────
// React Native respects I18nManager.isRTL for most flex layouts automatically,
// but these explicit helpers make RTL intent unambiguous in every component.
export const RTL = StyleSheet.create({
  // Primary reading-direction row: items flow right-to-left
  row: {
    flexDirection: 'row',
    writingDirection: 'rtl',
  },
  // Text alignment — always end-aligned for Hebrew
  text: {
    textAlign: 'right',
    writingDirection: 'rtl',
  },
  // Container alignment — start = right in RTL
  container: {
    alignItems: 'flex-start',
  },
});
