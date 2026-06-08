// @flow
/**
 * StrengthWorkoutButton.js — Phase 2 Strength Training Logger
 *
 * ADDITIONS in this version:
 *   - Haptic feedback: Haptics.notificationAsync(Success) fires on successful log
 *   - Reanimated scale pulse on the log button (UI-thread, 60fps)
 *   - expo-haptics gracefully no-ops on web (no crash)
 *
 * ARCHITECTURE RULES (per ROADMAP.md):
 *   ✓ Zero clinical logic — GLUT4 text comes from Orchestrator response
 *   ✓ All Hebrew strings via t() from locales/he.json
 *   ✓ RTL: borderStartWidth, marginEnd, paddingEnd, textAlign: right
 *   ✓ _apiOverride injection point for tests
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  UIManager,
} from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSequence,
  withSpring,
} from 'react-native-reanimated';

import { t } from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';
import ExternalResourceButton from './ExternalResourceButton';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// Haptics: safe import — expo-haptics no-ops on web automatically
let Haptics = null;
try {
  Haptics = require('expo-haptics');
} catch (_) { /* web or simulator — silently skip */ }

async function triggerSuccessHaptic() {
  try {
    if (Haptics) {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    }
  } catch (_) { /* haptics not available on this device */ }
}

// ── Duration options ──────────────────────────────────────────────────────
const DURATION_OPTIONS = [
  { key: 'STRENGTH_BTN_DURATION_30', minutes: 30 },
  { key: 'STRENGTH_BTN_DURATION_45', minutes: 45 },
  { key: 'STRENGTH_BTN_DURATION_60', minutes: 60 },
  { key: 'STRENGTH_BTN_DURATION_90', minutes: 90 },
];

async function _defaultLogExercise(payload) {
  const { logExerciseSession } = require('../api/endpoints');
  return logExerciseSession(payload);
}

// ── Component ─────────────────────────────────────────────────────────────
export default function StrengthWorkoutButton({
  userId,
  currentWeek,
  onLogged     = null,
  _apiOverride = null,
}) {
  const [selectedMinutes, setSelectedMinutes] = useState(45);
  const [status,     setStatus]     = useState('idle');   // idle|logging|done|error
  const [glut4,      setGlut4]      = useState(null);
  const [showPanel,  setShowPanel]  = useState(false);
  const [actionUrl,  setActionUrl]  = useState(null);
  const [actionLabel,setActionLabel]= useState(null);

  // Scale pulse for the log button — UI thread only
  const btnScale = useSharedValue(1);
  const btnAnimStyle = useAnimatedStyle(() => ({
    transform: [{ scale: btnScale.value }],
  }));

  const handleDurationSelect = useCallback((mins) => {
    if (status === 'done') return;
    setSelectedMinutes(mins);
  }, [status]);

  const handleLog = useCallback(async () => {
    if (status === 'logging' || status === 'done') return;

    // Scale pulse feedback on button tap
    btnScale.value = withSequence(
      withSpring(0.94, { damping: 10, stiffness: 400 }),
      withSpring(1,    { damping: 12, stiffness: 300 }),
    );

    setStatus('logging');
    setGlut4(null);
    setShowPanel(false);

    try {
      const callApi = _apiOverride ?? _defaultLogExercise;
      const result  = await callApi({
        user_id:      userId,
        current_week: currentWeek,
        exercise: {
          type:             'STRENGTH',
          duration_minutes: selectedMinutes,
          completed:        true,
        },
      });

      // Haptic success notification (native only, no-op on web)
      await triggerSuccessHaptic();

      setStatus('done');
      const affirmation = result?.oars_affirmation_he ?? null;
      if (affirmation) {
        setGlut4(affirmation);
        setShowPanel(true);
      }
      // Content Curation: surface deep-link if Orchestrator attached one
      setActionUrl(result?.action_url   ?? null);
      setActionLabel(result?.action_label ?? null);
      if (typeof onLogged === 'function') onLogged(result);

    } catch (_err) {
      setStatus('error');
    }
  }, [status, userId, currentWeek, selectedMinutes, onLogged, _apiOverride]);

  const handleDismissPanel = useCallback(() => {
    setShowPanel(false);
  }, []);

  const btnLabel = {
    idle:    t('STRENGTH_BTN_IDLE'),
    logging: t('STRENGTH_BTN_LOGGING'),
    done:    t('STRENGTH_BTN_DONE'),
    error:   t('STRENGTH_BTN_ERROR'),
  }[status];

  const btnColorStyle = [
    styles.logBtn,
    status === 'done'  && styles.logBtnDone,
    status === 'error' && styles.logBtnError,
    (status === 'logging' || status === 'done') && styles.logBtnDisabled,
  ];

  return (
    <View style={styles.wrapper}>
      {/* Section label */}
      <View style={[styles.labelRow, RTL.row]}>
        <View style={[styles.iconDot, { backgroundColor: COLORS.strengthFill }]} />
        <Text style={[styles.sectionLabel, RTL.text]}>
          {t('STRENGTH_BTN_SECTION_LABEL')}
        </Text>
      </View>

      {/* Duration picker */}
      <Text style={[styles.durationLabel, RTL.text]}>
        {t('STRENGTH_BTN_DURATION_LABEL')}
      </Text>
      <View style={[styles.durationRow, RTL.row]}>
        {DURATION_OPTIONS.map(({ key, minutes }) => {
          const selected = selectedMinutes === minutes;
          return (
            <TouchableOpacity
              key={key}
              style={[styles.durationChip, selected && styles.durationChipSelected]}
              onPress={() => handleDurationSelect(minutes)}
              disabled={status === 'done' || status === 'logging'}
              accessibilityRole="radio"
              accessibilityState={{ checked: selected }}
              accessibilityLabel={t(key)}
            >
              <Text style={[
                styles.durationChipText,
                selected && styles.durationChipTextSelected,
              ]}>
                {t(key)}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Log button — wrapped in Animated.View for scale pulse */}
      <Animated.View style={btnAnimStyle}>
        <TouchableOpacity
          style={btnColorStyle}
          onPress={handleLog}
          disabled={status === 'logging' || status === 'done'}
          accessibilityRole="button"
          accessibilityLabel={btnLabel}
          accessibilityState={{ disabled: status === 'logging' || status === 'done' }}
        >
          {status === 'logging'
            ? <ActivityIndicator color={COLORS.surface} size="small" />
            : <Text style={styles.logBtnText}>{btnLabel}</Text>
          }
        </TouchableOpacity>
      </Animated.View>

      {/* GLUT4 feedback panel */}
      {showPanel && glut4 && (
        <View style={styles.glut4Panel}>
          <View style={[styles.glut4Header, RTL.row]}>
            <Text style={[styles.glut4Title, RTL.text]}>
              {t('STRENGTH_GLUT4_PANEL_TITLE')}
            </Text>
            <TouchableOpacity
              onPress={handleDismissPanel}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              accessibilityLabel={t('STRENGTH_GLUT4_DISMISS')}
              accessibilityRole="button"
            >
              <Text style={styles.dismissX}>✕</Text>
            </TouchableOpacity>
          </View>
          <Text style={[styles.glut4Body, RTL.text]}>{glut4}</Text>
          <View style={styles.glut4Tip}>
            <Text style={[styles.glut4TipText, RTL.text]}>
              ⏱ {t('STRENGTH_GLUT4_TIP')}
            </Text>
          </View>
          {/* Content Curation: deep-link button (null-safe — renders nothing when missing) */}
          <ExternalResourceButton
            url={actionUrl}
            label={actionLabel}
            accentColor={STRENGTH_FILL}
          />

          <TouchableOpacity
            style={styles.dismissBtn}
            onPress={handleDismissPanel}
            accessibilityRole="button"
            accessibilityLabel={t('STRENGTH_GLUT4_DISMISS')}
          >
            <Text style={styles.dismissBtnText}>{t('STRENGTH_GLUT4_DISMISS')}</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

StrengthWorkoutButton.DURATION_OPTIONS = DURATION_OPTIONS;

// ── Styles ────────────────────────────────────────────────────────────────
const STRENGTH_FILL = '#7C3AED';

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor:  COLORS.surface,
    borderRadius:     RADIUS.lg,
    padding:          SPACING.md,
    marginTop:        SPACING.md,
    borderStartWidth: 4,
    borderStartColor: STRENGTH_FILL,
    shadowColor:      '#000',
    shadowOffset:     { width: 0, height: 2 },
    shadowOpacity:    0.07,
    shadowRadius:     5,
    elevation:        3,
  },
  labelRow: {
    alignItems:   'center',
    marginBottom: SPACING.xs,
  },
  iconDot: {
    width: 10, height: 10, borderRadius: 5,
    marginEnd:  SPACING.xs,
    flexShrink: 0,
  },
  sectionLabel: {
    flex:          1,
    fontSize:      FONT.xs,
    fontWeight:    '700',
    color:         COLORS.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  durationLabel: {
    fontSize:     FONT.sm,
    color:        COLORS.textSecondary,
    marginBottom: SPACING.xs,
  },
  durationRow: {
    gap:          SPACING.xs,
    marginBottom: SPACING.sm,
    flexWrap:     'wrap',
  },
  durationChip: {
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xxs,
    borderRadius:      RADIUS.pill,
    borderWidth:       1.5,
    borderColor:       COLORS.border,
    backgroundColor:   COLORS.surface,
  },
  durationChipSelected: {
    backgroundColor: STRENGTH_FILL,
    borderColor:     STRENGTH_FILL,
  },
  durationChipText: {
    fontSize: FONT.sm,
    color:    COLORS.textSecondary,
  },
  durationChipTextSelected: {
    color:      COLORS.surface,
    fontWeight: '700',
  },
  logBtn: {
    backgroundColor: STRENGTH_FILL,
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.sm,
    alignItems:      'center',
    justifyContent:  'center',
    minHeight:       48,
  },
  logBtnDone:     { backgroundColor: COLORS.success },
  logBtnError:    { backgroundColor: COLORS.danger },
  logBtnDisabled: { opacity: 0.75 },
  logBtnText: {
    color:      COLORS.surface,
    fontSize:   FONT.md,
    fontWeight: '700',
  },
  glut4Panel: {
    marginTop:        SPACING.md,
    backgroundColor:  '#F5F3FF',
    borderRadius:     RADIUS.md,
    padding:          SPACING.md,
    borderStartWidth: 4,
    borderStartColor: STRENGTH_FILL,
  },
  glut4Header: {
    alignItems:   'center',
    marginBottom: SPACING.xs,
  },
  glut4Title: {
    flex:       1,
    fontSize:   FONT.md,
    fontWeight: '700',
    color:      STRENGTH_FILL,
  },
  dismissX: {
    fontSize:     FONT.sm,
    color:        COLORS.textDisabled,
    fontWeight:   '700',
    paddingStart: SPACING.sm,
  },
  glut4Body: {
    fontSize:     FONT.sm,
    color:        COLORS.textPrimary,
    lineHeight:   FONT.sm * 1.6,
    marginBottom: SPACING.sm,
  },
  glut4Tip: {
    backgroundColor: '#EDE9FE',
    borderRadius:    RADIUS.sm,
    padding:         SPACING.xs,
    marginBottom:    SPACING.sm,
  },
  glut4TipText: {
    fontSize:   FONT.sm,
    fontWeight: '600',
    color:      STRENGTH_FILL,
  },
  dismissBtn: {
    alignSelf:         'flex-end',
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.xs,
    borderRadius:      RADIUS.pill,
    borderWidth:       1,
    borderColor:       STRENGTH_FILL,
  },
  dismissBtnText: {
    color:      STRENGTH_FILL,
    fontSize:   FONT.sm,
    fontWeight: '600',
  },
});
