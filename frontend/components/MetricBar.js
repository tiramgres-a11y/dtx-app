// @flow
/**
 * MetricBar — Animated progress bar (react-native-reanimated v3)
 *
 * Replaces the old Animated.timing with a Reanimated withTiming worklet
 * so the fill animation runs entirely on the UI thread at 60fps without
 * blocking JS. Falls back gracefully on web (Reanimated's web support).
 *
 * Props:
 *   label        {string}  — localised label (already translated by caller)
 *   value        {number}  — current metric value
 *   goal         {number}  — 100% target value
 *   unit         {string}  — unit string (already translated)
 *   fillColor    {string}  — bar fill colour (overridden by warn state)
 *   warn         {boolean} — red fill + bold value when true
 *   themeAccent  {string}  — optional accent from dynamic theme (goal text)
 *
 * RTL constraints preserved:
 *   marginStart/End, textAlign: right via RTL.text / RTL.row
 */

import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  Easing,
} from 'react-native-reanimated';

import { COLORS, FONT, SPACING, RADIUS, RTL } from './tokens';
import { t } from '../utils/i18n';

export default function MetricBar({
  label,
  value,
  goal,
  unit,
  fillColor,
  warn        = false,
  themeAccent = null,
}) {
  const clampedRatio = Math.min(1, Math.max(0, goal > 0 ? value / goal : 0));

  // Shared value lives on the UI thread — animation never touches JS thread
  const progress = useSharedValue(0);

  useEffect(() => {
    // Animate from current value to target on mount or value change
    progress.value = withTiming(clampedRatio, {
      duration: 700,
      easing:   Easing.out(Easing.cubic),
    });
  }, [clampedRatio]);

  // Animated style — runs on UI thread (worklet)
  const animatedFillStyle = useAnimatedStyle(() => ({
    width: `${progress.value * 100}%`,
  }));

  const pct          = Math.round(clampedRatio * 100);
  const effectiveFill = warn ? COLORS.danger : fillColor;
  const goalTextColor = themeAccent ?? COLORS.textDisabled;

  return (
    <View style={styles.wrapper}>
      {/* Label row — RTL: label right, value left */}
      <View style={[styles.labelRow, RTL.row]}>
        <Text style={[styles.label, RTL.text]}>{label}</Text>
        <Text style={[styles.value, warn && styles.valueWarn]}>
          {typeof value === 'number'
            ? value.toLocaleString('he-IL')
            : value}{' '}{unit}
        </Text>
      </View>

      {/* Track + animated fill */}
      <View style={styles.track}>
        <Animated.View
          style={[
            styles.fill,
            { backgroundColor: effectiveFill },
            animatedFillStyle,
          ]}
        />
      </View>

      {/* Goal / percentage row */}
      <View style={[styles.goalRow, RTL.row]}>
        <Text style={[styles.goalText, { color: goalTextColor }, RTL.text]}>
          {pct}% {t('PROGRESS_COMPLETE')}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: SPACING.md,
  },
  labelRow: {
    justifyContent: 'space-between',
    marginBottom:   SPACING.xxs,
  },
  label: {
    fontSize:   FONT.sm,
    fontWeight: '600',
    color:      COLORS.textPrimary,
    flex:       1,
  },
  value: {
    fontSize:    FONT.sm,
    color:       COLORS.textSecondary,
    marginStart: SPACING.sm,
  },
  valueWarn: {
    color:      COLORS.danger,
    fontWeight: '700',
  },
  track: {
    height:          10,
    backgroundColor: COLORS.trackBg,
    borderRadius:    RADIUS.pill,
    overflow:        'hidden',
  },
  fill: {
    height:       '100%',
    borderRadius: RADIUS.pill,
  },
  goalRow: {
    marginTop: SPACING.xxs,
  },
  goalText: {
    fontSize: FONT.xs,
  },
});
