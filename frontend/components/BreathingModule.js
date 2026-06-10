// @flow
/**
 * BreathingModule.js — Evening "Engine Shutdown" breathing exercise
 *
 * Shown on the Dashboard during evening/night themes (theme.isDark).
 * Guides a 4-4-6 breathing cycle (inhale 4s / hold 4s / exhale 6s) with an
 * animated circle — promotes parasympathetic activation and melatonin-friendly
 * wind-down per the sleep-engineering spec.
 *
 * Animation runs on the UI thread via react-native-reanimated (60fps, no JS block).
 *
 * ARCHITECTURE (per ROADMAP.md):
 *   Owned by Worker 2. Zero clinical logic — fixed breathing pattern, ambient UX.
 *   All strings from locales/he.json via t().
 */

import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSequence,
  withRepeat,
  Easing,
} from 'react-native-reanimated';

import { FONT, SPACING, RADIUS, RTL } from './tokens';
import { t } from '../utils/i18n';

// Breathing cycle timing (ms) — inhale 4s, hold 4s, exhale 6s
const INHALE_MS = 4000;
const HOLD_MS   = 4000;
const EXHALE_MS = 6000;
const CYCLE_MS  = INHALE_MS + HOLD_MS + EXHALE_MS;

export default function BreathingModule({ theme }) {
  const [isActive, setIsActive]   = useState(false);
  const [phaseKey, setPhaseKey]   = useState('BREATHING_START_HINT');

  const scale = useSharedValue(0.55);

  const circleStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  // Phase label cycler — JS-side timer mirrors the UI-thread animation
  useEffect(() => {
    if (!isActive) return undefined;

    let cancelled = false;
    const phases = [
      { key: 'BREATHING_INHALE', ms: INHALE_MS },
      { key: 'BREATHING_HOLD',   ms: HOLD_MS   },
      { key: 'BREATHING_EXHALE', ms: EXHALE_MS },
    ];
    let idx = 0;
    let timer = null;

    const tick = () => {
      if (cancelled) return;
      setPhaseKey(phases[idx].key);
      timer = setTimeout(() => {
        idx = (idx + 1) % phases.length;
        tick();
      }, phases[idx].ms);
    };
    tick();

    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [isActive]);

  const handleToggle = useCallback(() => {
    if (isActive) {
      setIsActive(false);
      setPhaseKey('BREATHING_START_HINT');
      scale.value = withTiming(0.55, { duration: 600 });
    } else {
      setIsActive(true);
      scale.value = withRepeat(
        withSequence(
          withTiming(1.0,  { duration: INHALE_MS, easing: Easing.inOut(Easing.quad) }),
          withTiming(1.0,  { duration: HOLD_MS }),
          withTiming(0.55, { duration: EXHALE_MS, easing: Easing.inOut(Easing.quad) }),
        ),
        -1, // repeat forever until stopped
      );
    }
  }, [isActive, scale]);

  const accent = theme?.accent || '#818CF8';

  return (
    <View style={[styles.card, { backgroundColor: theme?.cardBg || '#2E2A5E' }]}>
      <Text style={[styles.title, { color: theme?.greeting || '#E0E7FF' }, RTL.text]}>
        {t('BREATHING_TITLE')}
      </Text>
      <Text style={[styles.subtitle, { color: theme?.weekLabel || '#A5B4FC' }, RTL.text]}>
        {t('BREATHING_SUBTITLE')}
      </Text>

      <View style={styles.circleArea}>
        <Animated.View
          style={[styles.circle, { backgroundColor: accent + '33', borderColor: accent }, circleStyle]}
        />
        <Text style={[styles.phaseLabel, { color: theme?.greeting || '#E0E7FF' }]}>
          {t(phaseKey)}
        </Text>
      </View>

      <TouchableOpacity
        style={[styles.btn, { backgroundColor: isActive ? 'transparent' : accent, borderColor: accent }]}
        onPress={handleToggle}
        accessibilityRole="button"
        accessibilityLabel={isActive ? t('BREATHING_STOP_BTN') : t('BREATHING_START_BTN')}
      >
        <Text style={[styles.btnText, { color: isActive ? accent : '#FFFFFF' }]}>
          {isActive ? t('BREATHING_STOP_BTN') : t('BREATHING_START_BTN')}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  card: {
    borderRadius:      RADIUS.lg,
    padding:           SPACING.md,
    marginTop:         SPACING.sm,
    alignItems:        'stretch',
  },
  title: {
    fontSize:   FONT.lg,
    fontWeight: '700',
  },
  subtitle: {
    fontSize:  FONT.sm,
    marginTop: SPACING.xxs,
  },
  circleArea: {
    height:         180,
    alignItems:     'center',
    justifyContent: 'center',
    marginVertical: SPACING.sm,
  },
  circle: {
    position:     'absolute',
    width:        160,
    height:       160,
    borderRadius: 80,
    borderWidth:  2,
  },
  phaseLabel: {
    fontSize:   FONT.lg,
    fontWeight: '600',
  },
  btn: {
    borderRadius:    RADIUS.pill,
    borderWidth:     1.5,
    height:          44,
    alignItems:      'center',
    justifyContent:  'center',
  },
  btnText: {
    fontSize:   FONT.sm,
    fontWeight: '700',
  },
});
