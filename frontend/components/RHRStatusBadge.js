// @flow
/**
 * RHRStatusBadge.js — Resting Heart Rate subtle visual indicator
 *
 * Graceful Degradation contract:
 *   restingHr = null | undefined → renders nothing (hidden smoothly, no broken UI)
 *   restingHr = number           → shows value, status label, optional trend arrow
 *
 * Status thresholds (display only — zero clinical logic here):
 *   < 55           → low    (positive signal)
 *   55–74          → normal
 *   ≥ 75           → elevated (yellow warning)
 *
 * All Hebrew strings via t(). RTL logical properties throughout.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { t }    from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';

// ─── Display thresholds (pure UI — no clinical gating) ───────────────────
const RHR_LOW_THRESHOLD      = 55;
const RHR_ELEVATED_THRESHOLD = 75;

function _classify(hr) {
  if (hr < RHR_LOW_THRESHOLD)      return 'low';
  if (hr >= RHR_ELEVATED_THRESHOLD) return 'elevated';
  return 'normal';
}

const STATUS_COLORS = {
  low:      COLORS.success,
  normal:   COLORS.primary,
  elevated: COLORS.warning,
};

const STATUS_KEYS = {
  low:      'RHR_STATUS_LOW',
  normal:   'RHR_STATUS_NORMAL',
  elevated: 'RHR_STATUS_ELEVATED',
};

const TREND_KEYS = {
  up:     'RHR_TREND_UP',
  down:   'RHR_TREND_DOWN',
  stable: 'RHR_TREND_STABLE',
};

// ─── Component ────────────────────────────────────────────────────────────
export default function RHRStatusBadge({
  restingHr,        // number | null | undefined — null = sensor off, render nothing
  trend = 'stable', // 'up' | 'down' | 'stable'
}) {
  // ── Graceful degradation: no data → render nothing ──────────────────────
  if (restingHr == null) return null;

  const status     = _classify(restingHr);
  const accentColor = STATUS_COLORS[status];

  return (
    <View
      style={[styles.badge, { borderStartColor: accentColor }]}
      accessibilityRole="text"
      accessibilityLabel={`${t('RHR_LABEL')} ${restingHr} ${t('RHR_UNIT')}`}
    >
      {/* Left: label + value ─────────────────────────────────────────── */}
      <View style={[styles.left, RTL.row]}>
        {/* Coloured dot */}
        <View style={[styles.dot, { backgroundColor: accentColor }]} />

        <View style={RTL.container}>
          <Text style={[styles.label, RTL.text]}>{t('RHR_LABEL')}</Text>
          <View style={[styles.valueRow, RTL.row]}>
            <Text style={[styles.value, { color: accentColor }]}>{restingHr}</Text>
            <Text style={[styles.unit, RTL.text]}> {t('RHR_UNIT')}</Text>
          </View>
        </View>
      </View>

      {/* Right: status chip + trend ──────────────────────────────────── */}
      <View style={[styles.right, RTL.container]}>
        <View style={[styles.statusChip, { backgroundColor: accentColor + '22' }]}>
          <Text style={[styles.statusText, { color: accentColor }]}>
            {t(STATUS_KEYS[status])}
          </Text>
        </View>
        <Text style={[styles.trendText, RTL.text]}>
          {t(TREND_KEYS[trend] ?? 'RHR_TREND_STABLE')}
        </Text>
      </View>
    </View>
  );
}

// Export thresholds for tests
RHRStatusBadge.RHR_LOW_THRESHOLD      = RHR_LOW_THRESHOLD;
RHRStatusBadge.RHR_ELEVATED_THRESHOLD = RHR_ELEVATED_THRESHOLD;
RHRStatusBadge._classify              = _classify;

// ─── Styles ──────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  badge: {
    flexDirection:    'row',
    alignItems:       'center',
    justifyContent:   'space-between',
    backgroundColor:  COLORS.surfaceAlt,
    borderRadius:     RADIUS.md,
    paddingHorizontal: SPACING.sm,
    paddingVertical:  SPACING.xs,
    borderStartWidth: 3,
    borderStartColor: COLORS.primary,   // overridden inline
    marginTop:        SPACING.sm,
  },
  left: {
    alignItems: 'center',
    flex:       1,
  },
  dot: {
    width:        8,
    height:       8,
    borderRadius: 4,
    marginEnd:    SPACING.xs,
    flexShrink:   0,
  },
  label: {
    fontSize: FONT.xs,
    color:    COLORS.textSecondary,
  },
  valueRow: {
    alignItems: 'baseline',
  },
  value: {
    fontSize:   FONT.lg,
    fontWeight: '700',
  },
  unit: {
    fontSize: FONT.xs,
    color:    COLORS.textSecondary,
  },
  right: {
    alignItems: 'flex-end',
    paddingStart: SPACING.sm,
  },
  statusChip: {
    borderRadius:      RADIUS.pill,
    paddingHorizontal: SPACING.xs,
    paddingVertical:   2,
    marginBottom:      2,
  },
  statusText: {
    fontSize:   FONT.xs,
    fontWeight: '700',
  },
  trendText: {
    fontSize: FONT.xs,
    color:    COLORS.textDisabled,
  },
});
