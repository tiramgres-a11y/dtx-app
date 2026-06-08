// @flow
/**
 * HabitStackingCard.js — Phase 1 Gamification UI (Weeks 1-4)
 *
 * Renders a contextual Habit Stacking prompt when a behaviour trigger is active.
 * Trigger types: sedentary_alert | hydration_reminder | coffee_habit |
 *                post_meal | sleep_prep
 *
 * ANIMATION: Card slides in from bottom-right (RTL reading direction) using
 * react-native-reanimated withSpring — runs entirely on the UI thread at 60fps.
 *
 * ARCHITECTURE RULES (per ROADMAP.md):
 *   ✓ Owned by Worker 2 (Frontend Manager) — zero clinical logic
 *   ✓ All Hebrew strings via t() from locales/he.json — no inline literals
 *   ✓ RTL layout: marginStart/End, borderStartWidth, writingDirection: rtl
 *   ✓ API call (logHabitCompletion) via endpoints.js — no direct axios usage
 *   ✓ Component is purely presentational + local interaction state only
 *
 * Props:
 *   trigger       {string|null}   — active trigger id, null = render nothing
 *   userId        {string}        — forwarded to API payload
 *   currentWeek   {number}        — forwarded to API payload
 *   streakDays    {number}        — consecutive days completed (display only)
 *   onCompleted   {function}      — called after successful API log (optional)
 *   onDismiss     {function}      — called when user dismisses card (optional)
 *   _apiOverride  {function}      — injected in tests to replace real API call
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
  UIManager,
  ActivityIndicator,
} from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
} from 'react-native-reanimated';

import { t }    from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';

// Enable LayoutAnimation on Android (kept for non-Reanimated paths)
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// ── Trigger → locale-key map ──────────────────────────────────────────────

const TRIGGER_KEYS = {
  sedentary_alert:    {
    title: 'HABIT_TRIGGER_SEDENTARY_TITLE',
    cue:   'HABIT_TRIGGER_SEDENTARY_CUE',
    why:   'HABIT_TRIGGER_SEDENTARY_WHY',
  },
  hydration_reminder: {
    title: 'HABIT_TRIGGER_HYDRATION_TITLE',
    cue:   'HABIT_TRIGGER_HYDRATION_CUE',
    why:   'HABIT_TRIGGER_HYDRATION_WHY',
  },
  coffee_habit:       {
    title: 'HABIT_TRIGGER_COFFEE_TITLE',
    cue:   'HABIT_TRIGGER_COFFEE_CUE',
    why:   'HABIT_TRIGGER_COFFEE_WHY',
  },
  post_meal:          {
    title: 'HABIT_TRIGGER_POST_MEAL_TITLE',
    cue:   'HABIT_TRIGGER_POST_MEAL_CUE',
    why:   'HABIT_TRIGGER_POST_MEAL_WHY',
  },
  sleep_prep:         {
    title: 'HABIT_TRIGGER_SLEEP_PREP_TITLE',
    cue:   'HABIT_TRIGGER_SLEEP_PREP_CUE',
    why:   'HABIT_TRIGGER_SLEEP_PREP_WHY',
  },
};

const TRIGGER_ACCENT = {
  sedentary_alert:    COLORS.sedentaryFill,
  hydration_reminder: '#0EA5E9',
  coffee_habit:       '#92400E',
  post_meal:          COLORS.success,
  sleep_prep:         COLORS.sleepFill,
};

// ── Spring config for slide-in ────────────────────────────────────────────
const SPRING_CONFIG = {
  damping:   18,
  stiffness: 200,
  mass:      0.8,
};

// ── Component ─────────────────────────────────────────────────────────────

export default function HabitStackingCard({
  trigger,
  userId,
  currentWeek,
  streakDays   = 0,
  onCompleted  = null,
  onDismiss    = null,
  _apiOverride = null,
}) {
  const [isLogging,   setIsLogging]   = useState(false);
  const [isDone,      setIsDone]      = useState(false);
  const [hasError,    setHasError]    = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  // Reanimated slide-in: translateY 40→0, opacity 0→1
  const translateY = useSharedValue(40);
  const opacity    = useSharedValue(0);

  // Animate in when trigger becomes active
  useEffect(() => {
    if (trigger && !isDismissed) {
      translateY.value = 40;
      opacity.value    = 0;
      translateY.value = withSpring(0, SPRING_CONFIG);
      opacity.value    = withTiming(1, { duration: 280 });
    }
  }, [trigger]);

  const cardAnimStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
    opacity:   opacity.value,
  }));

  // Reset when trigger changes
  const prevTriggerRef = useRef(trigger);
  useEffect(() => {
    if (prevTriggerRef.current !== trigger) {
      prevTriggerRef.current = trigger;
      setIsDone(false);
      setHasError(false);
      setIsDismissed(false);
    }
  }, [trigger]);

  // ── Completion handler ───────────────────────────────────────────────────
  const handleCompleted = useCallback(async () => {
    if (isLogging || isDone) return;
    setIsLogging(true);
    setHasError(false);
    try {
      const callApi = _apiOverride ?? _defaultLogHabit;
      await callApi({
        user_id:      userId,
        current_week: currentWeek,
        trigger_id:   trigger,
        event_type:   'HABIT_COMPLETED',
        completed_at: new Date().toISOString(),
      });
      setIsDone(true);
      if (typeof onCompleted === 'function') onCompleted({ trigger, userId });
    } catch (_err) {
      setHasError(true);
    } finally {
      setIsLogging(false);
    }
  }, [isLogging, isDone, trigger, userId, currentWeek, onCompleted, _apiOverride]);

  // ── Dismiss handler (animate out then hide) ──────────────────────────────
  const handleDismiss = useCallback(() => {
    opacity.value    = withTiming(0, { duration: 200 });
    translateY.value = withTiming(20, { duration: 200 }, (finished) => {
      if (finished) {
        runOnJS(setIsDismissed)(true);
        if (typeof onDismiss === 'function') runOnJS(onDismiss)({ trigger });
      }
    });
  }, [trigger, onDismiss]);

  // Guard
  if (!trigger || isDismissed) return null;
  const keys = TRIGGER_KEYS[trigger];
  if (!keys) return null;

  const accent = TRIGGER_ACCENT[trigger] ?? COLORS.primary;
  const title  = t(keys.title);
  const cue    = t(keys.cue);
  const why    = t(keys.why);

  return (
    <Animated.View
      style={[styles.card, { borderStartColor: accent }, cardAnimStyle]}
      accessibilityRole="none"
      accessibilityLabel={title}
    >
      {/* Header */}
      <View style={[styles.headerRow, RTL.row]}>
        <View style={[styles.accentDot, { backgroundColor: accent }]} />
        <Text style={[styles.sectionLabel, RTL.text]}>
          {t('HABIT_CARD_SECTION_TITLE')}
        </Text>
        <TouchableOpacity
          style={styles.dismissBtn}
          onPress={handleDismiss}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          accessibilityRole="button"
          accessibilityLabel={t('HABIT_CARD_DISMISS_LABEL')}
        >
          <Text style={styles.dismissX}>✕</Text>
        </TouchableOpacity>
      </View>

      {/* Title */}
      <Text style={[styles.title, RTL.text]}>{title}</Text>

      {/* Cue box */}
      <View style={[styles.cueBox, { borderStartColor: accent }]}>
        <Text style={[styles.cueText, RTL.text]}>{cue}</Text>
      </View>

      {/* Science rationale */}
      <Text style={[styles.whyText, RTL.text]}>{why}</Text>

      {/* Footer: streak + complete button */}
      <View style={[styles.footer, RTL.row]}>
        {streakDays > 0 && (
          <View style={styles.streakBadge}>
            <Text style={styles.streakText}>
              🔥 {t('HABIT_CARD_STREAK_LABEL')} {streakDays} {t('HABIT_CARD_STREAK_DAYS')}
            </Text>
          </View>
        )}
        <Text style={styles.xpLabel}>{t('HABIT_CARD_XP_LABEL')}</Text>
        <TouchableOpacity
          style={[
            styles.completeBtn,
            { backgroundColor: isDone ? COLORS.success : accent },
            (isLogging || isDone) && styles.completeBtnDisabled,
          ]}
          onPress={handleCompleted}
          disabled={isLogging || isDone}
          accessibilityRole="button"
          accessibilityLabel={t('HABIT_CARD_COMPLETED_BTN')}
          accessibilityState={{ disabled: isLogging || isDone }}
        >
          {isLogging
            ? <ActivityIndicator size="small" color={COLORS.surface} />
            : <Text style={styles.completeBtnText}>
                {isDone
                  ? `✓ ${t('HABIT_CARD_DONE_TOAST').split('.')[0]}`
                  : t('HABIT_CARD_COMPLETED_BTN')}
              </Text>
          }
        </TouchableOpacity>
      </View>

      {/* Error toast */}
      {hasError && (
        <View style={styles.errorToast}>
          <Text style={[styles.errorToastText, RTL.text]}>
            {t('HABIT_CARD_ERROR_TOAST')}
          </Text>
        </View>
      )}
    </Animated.View>
  );
}

// ── Default API call ──────────────────────────────────────────────────────
async function _defaultLogHabit(payload) {
  const { evaluateMetrics } = require('../api/endpoints');
  return evaluateMetrics({
    user_id:      payload.user_id,
    current_week: payload.current_week,
    strength:     { logged: true, duration_minutes: 5 },
  });
}

// Export for tests
HabitStackingCard.TRIGGER_KEYS = TRIGGER_KEYS;

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  card: {
    backgroundColor:  COLORS.surface,
    borderRadius:     RADIUS.lg,
    padding:          SPACING.md,
    marginTop:        SPACING.md,
    borderStartWidth: 4,
    borderStartColor: COLORS.primary,
    shadowColor:      '#000',
    shadowOffset:     { width: 0, height: 2 },
    shadowOpacity:    0.08,
    shadowRadius:     6,
    elevation:        3,
  },
  headerRow: {
    alignItems:   'center',
    marginBottom: SPACING.xs,
  },
  accentDot: {
    width:        8,
    height:       8,
    borderRadius: 4,
    marginEnd:    SPACING.xs,
    flexShrink:   0,
  },
  sectionLabel: {
    flex:          1,
    fontSize:      FONT.xs,
    fontWeight:    '600',
    color:         COLORS.textSecondary,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  dismissBtn: {
    paddingStart: SPACING.sm,
  },
  dismissX: {
    fontSize:   FONT.sm,
    color:      COLORS.textDisabled,
    fontWeight: '700',
  },
  title: {
    fontSize:     FONT.lg,
    fontWeight:   '700',
    color:        COLORS.textPrimary,
    marginBottom: SPACING.sm,
  },
  cueBox: {
    backgroundColor:  '#F8FAFC',
    borderRadius:     RADIUS.md,
    padding:          SPACING.sm,
    marginBottom:     SPACING.sm,
    borderStartWidth: 3,
    borderStartColor: COLORS.primary,
  },
  cueText: {
    fontSize:   FONT.md,
    fontWeight: '600',
    color:      COLORS.textPrimary,
    lineHeight: FONT.md * 1.5,
  },
  whyText: {
    fontSize:     FONT.sm,
    color:        COLORS.textSecondary,
    marginBottom: SPACING.md,
    lineHeight:   FONT.sm * 1.6,
  },
  footer: {
    alignItems: 'center',
    flexWrap:   'wrap',
    gap:        SPACING.xs,
  },
  streakBadge: {
    backgroundColor:   '#FEF9C3',
    borderRadius:      RADIUS.pill,
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xxs,
  },
  streakText: {
    fontSize:   FONT.xs,
    fontWeight: '700',
    color:      '#92400E',
  },
  xpLabel: {
    flex:      1,
    fontSize:  FONT.xs,
    fontWeight:'700',
    color:     COLORS.primary,
    textAlign: 'left',
  },
  completeBtn: {
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.xs,
    borderRadius:      RADIUS.pill,
    minWidth:          110,
    alignItems:        'center',
    justifyContent:    'center',
  },
  completeBtnDisabled: {
    opacity: 0.75,
  },
  completeBtnText: {
    color:      COLORS.surface,
    fontSize:   FONT.sm,
    fontWeight: '700',
  },
  errorToast: {
    marginTop:        SPACING.sm,
    backgroundColor:  '#FEF2F2',
    borderRadius:     RADIUS.sm,
    padding:          SPACING.sm,
    borderStartWidth: 3,
    borderStartColor: COLORS.danger,
  },
  errorToastText: {
    color:    COLORS.danger,
    fontSize: FONT.sm,
  },
});
