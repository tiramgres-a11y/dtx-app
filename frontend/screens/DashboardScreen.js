// @flow
/**
 * DashboardScreen — Phase 1 & 2 Dashboard (Lumen Health)
 *
 * ADDITIONS in this version (UI/UX Gamification Polish):
 *   - Dynamic Time-of-Day Theming: background, header, card colours shift by hour
 *     (dawn / day / dusk / "Engine Shutdown" evening / night)
 *   - MetricBar uses react-native-reanimated (UI-thread, 60fps, no JS block)
 *   - HabitStackingCard slides in with Reanimated withSpring
 *   - StrengthWorkoutButton fires haptic success notification (native only)
 *   - StatusBar style adapts to dark/light theme
 *
 * Architecture (per ROADMAP.md):
 *   This screen is owned by Worker 2 (Frontend Manager).
 *   Zero clinical logic — all rules live in the Orchestrator.
 *
 * i18n constraint:  NO Hebrew string literals in JSX — all via t().
 * RTL constraint:   marginStart/End, borderStartWidth, writingDirection: rtl.
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  StatusBar,
  Platform,
  UIManager,
} from 'react-native';

// Enable LayoutAnimation on Android (used by child components)
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

import { t }                   from '../utils/i18n';
import { useUser }             from '../context/UserContext';
import { evaluateMetrics }     from '../api/endpoints';
import { getTheme }            from '../utils/theme';
import { RTL, COLORS, FONT, SPACING, RADIUS } from '../components/tokens';
import SensorStatusBadge       from '../components/SensorStatusBadge';
import MetricBar               from '../components/MetricBar';
import SleepQuickTap           from '../components/SleepQuickTap';
import MilestoneChecklist      from '../components/MilestoneChecklist';
import HabitStackingCard       from '../components/HabitStackingCard';
import StrengthWorkoutButton   from '../components/StrengthWorkoutButton';
import RHRStatusBadge          from '../components/RHRStatusBadge';
import WeeklySummaryCard       from '../components/WeeklySummaryCard';

// ── Mock data (replaced by Worker 1 payload in Sprint 2) ─────────────────
const MOCK_SENSOR_DATA = {
  sleepHours:     5.2,
  sleepGoal:      7.0,
  steps:          4820,
  stepsGoal:      8000,
  sedentaryMins:  75,
  sedentaryLimit: 60,
};

const CURRENT_WEEK   = 6;
const MOCK_USER_ID   = 'user-demo-001';
const MOCK_RESTING_HR = 68;

const MOCK_WEEKLY_DAYS = [
  { date: '2026-06-01', sleep: { duration_hours: 6.5 }, steps: { steps: 7200, idle_minutes: 30 },
    exercise: { type: 'STRENGTH', duration_minutes: 45, completed: true }, heart_rate: { resting_hr: 65 } },
  { date: '2026-06-02', sleep: { duration_hours: 7.0 }, steps: { steps: 8100, idle_minutes: 25 } },
  { date: '2026-06-03', sleep: { duration_hours: 5.5 }, steps: { steps: 6000, idle_minutes: 50 },
    heart_rate: { resting_hr: 68 } },
  { date: '2026-06-04' },
  { date: '2026-06-05', sleep: { duration_hours: 7.5 }, steps: { steps: 9000, idle_minutes: 20 },
    exercise: { type: 'STRENGTH', duration_minutes: 50, completed: true }, heart_rate: { resting_hr: 63 } },
  { date: '2026-06-06', sleep: { duration_hours: 6.0 }, steps: { steps: 5500, idle_minutes: 40 },
    heart_rate: { resting_hr: 64 } },
  { date: '2026-06-07', sleep: { duration_hours: 6.5 }, steps: { steps: 7800, idle_minutes: 35 } },
];

// ── Greeting helper ───────────────────────────────────────────────────────
function getGreetingKey() {
  const hour = new Date().getHours();
  if (hour < 12) return 'DASHBOARD_GREETING_MORNING';
  if (hour < 17) return 'DASHBOARD_GREETING_AFTERNOON';
  return 'DASHBOARD_GREETING_EVENING';
}

// ── Screen ────────────────────────────────────────────────────────────────
export default function DashboardScreen() {
  // ── Dynamic theme (computed once per render cycle) ────────────────────
  const theme = useMemo(() => getTheme(), []);

  // ── User context (shared across tabs) ────────────────────────────────
  const { userId, currentWeek } = useUser();

  // ── Core graceful-degradation toggle ─────────────────────────────────
  const [isSensorActive, setIsSensorActive] = useState(true);

  // ── Phase 2 state ─────────────────────────────────────────────────────
  const [restingHr,         setRestingHr]         = useState(MOCK_RESTING_HR);
  const [rhrTrend,          setRhrTrend]           = useState('stable');
  const [weeklySummaryDays, setWeeklySummaryDays]  = useState(MOCK_WEEKLY_DAYS);

  // ── Coaching response from Orchestrator ──────────────────────────────
  const [coachingMsg,   setCoachingMsg]   = useState(null);
  const [evalLoading,   setEvalLoading]   = useState(false);
  const [evalError,     setEvalError]     = useState(false);

  // ── Habit trigger ─────────────────────────────────────────────────────
  const [activeTrigger, setActiveTrigger] = useState(
    MOCK_SENSOR_DATA.sedentaryMins >= MOCK_SENSOR_DATA.sedentaryLimit
      ? 'sedentary_alert'
      : null,
  );
  const [habitStreakDays, setHabitStreakDays] = useState(3);

  // ── Manual-mode state ─────────────────────────────────────────────────
  const [selectedSleepHours, setSelectedSleepHours] = useState(null);
  const [checkedMilestones,  setCheckedMilestones]  = useState([]);
  const [savedToast,         setSavedToast]          = useState(false);

  // ── Call Orchestrator when manual data is saved ───────────────────────
  const _callOrchestrator = useCallback(async (sleepH) => {
    setEvalLoading(true);
    setEvalError(false);
    try {
      const sleepHours = sleepH ?? selectedSleepHours ?? 6;
      const res = await evaluateMetrics({
        user_id:      userId,
        current_week: currentWeek,
        sleep:        { duration_hours: sleepHours },
        steps:        { steps: MOCK_SENSOR_DATA.steps, idle_minutes: MOCK_SENSOR_DATA.sedentaryMins },
      });
      // Show first coaching message from the engine
      const msg = res.oars_reflection_he || res.coaching_message_he || null;
      setCoachingMsg(msg);
      // If engine flagged a rule, surface it as a habit trigger
      if (res.triggered_rules && res.triggered_rules.length > 0) {
        const rule = res.triggered_rules[0];
        if (rule.includes('SEDENTARY') || rule.includes('SLEEP')) {
          setActiveTrigger('sedentary_alert');
        }
      }
    } catch (_err) {
      setEvalError(true);
    } finally {
      setEvalLoading(false);
    }
  }, [userId, currentWeek, selectedSleepHours]);

  const handleMilestoneToggle = useCallback((id) => {
    setCheckedMilestones((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const handleManualSave = useCallback(() => {
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 2500);
    _callOrchestrator(selectedSleepHours);
  }, [selectedSleepHours, _callOrchestrator]);

  const handleConnectPress = useCallback(() => {
    setIsSensorActive(true);
  }, []);

  const handleStrengthLogged = useCallback((res) => {
    if (!res) return;
    const msg = res.oars_reflection_he || res.coaching_message_he || null;
    if (msg) setCoachingMsg(msg);
  }, []);

  const handleHabitCompleted = useCallback(() => {
    setHabitStreakDays((d) => d + 1);
    setTimeout(() => setActiveTrigger(null), 1800);
  }, []);

  const handleHabitDismiss = useCallback(() => {
    setActiveTrigger(null);
  }, []);

  const handleDevToggle = useCallback(() => {
    setIsSensorActive((v) => !v);
  }, []);

  const { sleepHours, sleepGoal, steps, stepsGoal, sedentaryMins, sedentaryLimit } =
    MOCK_SENSOR_DATA;

  // ── Dynamic theme-aware styles (inline — change with theme) ──────────
  const themedSafe    = [styles.safe,    { backgroundColor: theme.background }];
  const themedHeader  = [styles.header,  { backgroundColor: theme.headerBg }, RTL.row];
  const themedBadge   = [styles.badgeRow,{ backgroundColor: theme.headerBg }];
  const themedCard    = [styles.card,    { backgroundColor: theme.cardBg,
                                           shadowColor: theme.cardShadow }];
  const themedGreeting = [styles.greeting, { color: theme.greeting }];
  const themedWeekLabel = [styles.weekLabel, { color: theme.weekLabel }, RTL.text];

  return (
    <SafeAreaView style={themedSafe}>
      <StatusBar
        barStyle={theme.statusBarStyle === 'light' ? 'light-content' : 'dark-content'}
        backgroundColor={theme.headerBg}
      />

      {/* ── Header ──────────────────────────────────────────────────── */}
      <View style={themedHeader}>
        <View style={RTL.container}>
          <Text style={[themedGreeting, RTL.text]}>{t(getGreetingKey())}</Text>
          <Text style={themedWeekLabel}>
            {t('DASHBOARD_WEEK_LABEL')} {currentWeek} — {t('DASHBOARD_PHASE_LABEL')}
          </Text>
        </View>

        {/* Dev-only sensor toggle pill */}
        {__DEV__ && (
          <TouchableOpacity
            style={[styles.devToggle, isSensorActive ? styles.devToggleOn : styles.devToggleOff]}
            onPress={handleDevToggle}
            accessibilityLabel="Dev: toggle sensor"
          >
            <Text style={styles.devToggleText}>
              {isSensorActive ? 'sensor ON' : 'sensor OFF'}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      {/* ── Sensor status badge ─────────────────────────────────────── */}
      <View style={themedBadge}>
        <SensorStatusBadge
          isActive={isSensorActive}
          onConnectPress={handleConnectPress}
        />
      </View>

      {/* ── Scrollable body ─────────────────────────────────────────── */}
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {/* ════ ACTIVE STATE — Automated sensor metrics ════ */}
        {isSensorActive && (
          <View style={themedCard}>
            <Text style={[styles.cardTitle, { color: theme.greeting }, RTL.text]}>
              {t('METRICS_SECTION_TITLE')}
            </Text>

            <MetricBar
              label={t('METRICS_SLEEP_LABEL')}
              value={sleepHours}
              goal={sleepGoal}
              unit={t('METRICS_SLEEP_UNIT')}
              fillColor={COLORS.sleepFill}
              warn={sleepHours < 6}
              themeAccent={theme.progressAccent}
            />
            <MetricBar
              label={t('METRICS_STEPS_LABEL')}
              value={steps}
              goal={stepsGoal}
              unit={t('METRICS_STEPS_UNIT')}
              fillColor={COLORS.stepsFill}
              warn={false}
              themeAccent={theme.progressAccent}
            />
            <MetricBar
              label={t('METRICS_SEDENTARY_LABEL')}
              value={sedentaryMins}
              goal={sedentaryLimit}
              unit={t('METRICS_SEDENTARY_UNIT')}
              fillColor={COLORS.sedentaryFill}
              warn={sedentaryMins >= sedentaryLimit}
              themeAccent={theme.progressAccent}
            />

            {sedentaryMins >= sedentaryLimit && (
              <View style={styles.warningBanner}>
                <Text style={[styles.warningText, RTL.text]}>
                  {t('METRICS_SEDENTARY_WARNING')}
                </Text>
              </View>
            )}

            <RHRStatusBadge restingHr={restingHr} trend={rhrTrend} />
          </View>
        )}

        {/* ════ PHASE 2 — Strength Workout Logger (Weeks 5-9) ════ */}
        {isSensorActive && currentWeek >= 5 && currentWeek <= 9 && (
          <StrengthWorkoutButton
            userId={userId}
            currentWeek={currentWeek}
            onLogged={handleStrengthLogged}
          />
        )}

        {/* ════ INACTIVE STATE — Manual logging panel ════ */}
        {!isSensorActive && (
          <View style={themedCard}>
            <Text style={[styles.cardTitle, { color: theme.greeting }, RTL.text]}>
              {t('MANUAL_SECTION_TITLE')}
            </Text>
            <Text style={[styles.cardSubtitle, RTL.text]}>
              {t('MANUAL_SECTION_SUBTITLE')}
            </Text>
            <View style={styles.divider} />
            <SleepQuickTap
              selectedValue={selectedSleepHours}
              onSelect={setSelectedSleepHours}
            />
            <View style={styles.divider} />
            <MilestoneChecklist
              checked={checkedMilestones}
              onToggle={handleMilestoneToggle}
            />
            <TouchableOpacity
              style={[styles.saveBtn, (!selectedSleepHours || evalLoading) && styles.saveBtnDisabled]}
              onPress={handleManualSave}
              disabled={!selectedSleepHours || evalLoading}
              accessibilityRole="button"
              accessibilityLabel={t('DASHBOARD_SAVE_AND_EVAL')}
            >
              <Text style={styles.saveBtnText}>
                {evalLoading ? t('DASHBOARD_EVAL_LOADING') : t('DASHBOARD_SAVE_AND_EVAL')}
              </Text>
            </TouchableOpacity>
            {savedToast && (
              <View style={styles.toast}>
                <Text style={[styles.toastText, RTL.text]}>{t('MANUAL_SAVED_TOAST')}</Text>
              </View>
            )}
            {evalError && (
              <View style={[styles.toast, { borderStartColor: '#F59E0B', backgroundColor: '#FFFBEB' }]}>
                <Text style={[styles.toastText, { color: '#92400E' }, RTL.text]}>
                  {t('DASHBOARD_EVAL_ERROR')}
                </Text>
              </View>
            )}
            {coachingMsg && !evalLoading && (
              <View style={[styles.toast, { borderStartColor: COLORS.primary, backgroundColor: '#EFF6FF' }]}>
                <Text style={[styles.toastText, { color: COLORS.primary }, RTL.text]}>
                  {t('DASHBOARD_COACHING_TITLE')}
                </Text>
                <Text style={[{ fontSize: FONT.sm, color: '#1E40AF', marginTop: 4 }, RTL.text]}>
                  {coachingMsg}
                </Text>
              </View>
            )}
          </View>
        )}

        {/* ════ HABIT STACKING CARD — Reanimated slide-in ════ */}
        <HabitStackingCard
          trigger={activeTrigger}
          userId={MOCK_USER_ID}
          currentWeek={CURRENT_WEEK}
          streakDays={habitStreakDays}
          onCompleted={handleHabitCompleted}
          onDismiss={handleHabitDismiss}
        />

        {/* ════ PHASE 2 — Weekly Summary Card (Weeks 5-9) ════ */}
        {currentWeek >= 5 && currentWeek <= 9 && (
          <WeeklySummaryCard
            userId={userId}
            currentWeek={currentWeek}
            days={weeklySummaryDays}
          />
        )}

        <View style={styles.bottomPad} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: {
    flex: 1,
    // backgroundColor set inline from theme
  },
  header: {
    justifyContent:  'space-between',
    alignItems:      'center',
    paddingHorizontal: SPACING.md,
    paddingTop:      Platform.OS === 'android' ? SPACING.md : SPACING.xs,
    paddingBottom:   SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  greeting: {
    fontSize:   FONT.xl,
    fontWeight: '700',
    // color set inline from theme
  },
  weekLabel: {
    fontSize:  FONT.sm,
    marginTop: SPACING.xxs,
    // color set inline from theme
  },
  devToggle: {
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xxs,
    borderRadius:      RADIUS.pill,
  },
  devToggleOn:   { backgroundColor: '#D1FAE5' },
  devToggleOff:  { backgroundColor: '#FEE2E2' },
  devToggleText: { fontSize: FONT.xs, fontWeight: '700' },

  badgeRow: {
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.xs,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },

  scroll:        { flex: 1 },
  scrollContent: {
    paddingHorizontal: SPACING.md,
    paddingTop:        SPACING.md,
  },

  card: {
    borderRadius:  RADIUS.lg,
    padding:       SPACING.md,
    shadowOffset:  { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius:  4,
    elevation:     2,
  },
  cardTitle: {
    fontSize:     FONT.lg,
    fontWeight:   '700',
    marginBottom: SPACING.sm,
  },
  cardSubtitle: {
    fontSize:     FONT.sm,
    color:        COLORS.textSecondary,
    marginBottom: SPACING.sm,
  },

  divider: {
    height:          1,
    backgroundColor: COLORS.border,
    marginVertical:  SPACING.sm,
  },

  warningBanner: {
    backgroundColor: '#FEF2F2',
    borderRadius:    RADIUS.sm,
    padding:         SPACING.sm,
    marginTop:       SPACING.xs,
    borderStartWidth: 4,
    borderStartColor: COLORS.danger,
  },
  warningText: {
    color:      COLORS.danger,
    fontSize:   FONT.sm,
    fontWeight: '600',
  },

  saveBtn: {
    backgroundColor: COLORS.primary,
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.sm,
    alignItems:      'center',
    marginTop:       SPACING.xs,
  },
  saveBtnDisabled: { backgroundColor: COLORS.textDisabled },
  saveBtnText: {
    color:      COLORS.surface,
    fontSize:   FONT.md,
    fontWeight: '700',
  },

  toast: {
    marginTop:        SPACING.sm,
    backgroundColor:  '#F0FDF4',
    borderRadius:     RADIUS.sm,
    padding:          SPACING.sm,
    borderStartWidth: 4,
    borderStartColor: COLORS.success,
    alignItems:       'flex-start',
  },
  toastText: {
    color:      COLORS.success,
    fontSize:   FONT.sm,
    fontWeight: '600',
  },

  bottomPad: { height: SPACING.xl },
});
