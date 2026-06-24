// @flow
/**
 * SOSScreen — Crisis / Craving response screen.
 * Calls /api/v1/sos/trigger → shows 3-step protocol.
 * Then /api/v1/sos/resolve with SUCCESS or LAPSE.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Platform,
  UIManager,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

import { t }            from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from '../components/tokens';
import { useUser }      from '../context/UserContext';
import { triggerSOS, resolveSOS } from '../api/endpoints';

// ── States ────────────────────────────────────────────────────────────────
const STATE = { IDLE: 'idle', LOADING: 'loading', ACTIVE: 'active', RESOLVING: 'resolving', DONE: 'done', ERROR: 'error' };

// ── Step card ─────────────────────────────────────────────────────────────
function StepCard({ number, title, instruction, accentColor }) {
  return (
    <View style={[styles.stepCard, { borderStartColor: accentColor }]}>
      <View style={[styles.stepHeader, RTL.row]}>
        <View style={[styles.stepBadge, { backgroundColor: accentColor }]}>
          <Text style={styles.stepBadgeText}>{number}</Text>
        </View>
        <Text style={[styles.stepTitle, RTL.text]}>{title}</Text>
      </View>
      <Text style={[styles.stepBody, RTL.text]}>{instruction}</Text>
    </View>
  );
}

export default function SOSScreen() {
  const { userId, currentWeek } = useUser();

  const [phase,       setPhase]       = useState(STATE.IDLE);
  const [sosData,     setSosData]     = useState(null);   // trigger response
  const [resolveData, setResolveData] = useState(null);  // resolve response
  const [timestamp,   setTimestamp]   = useState(null);

  const handleTrigger = useCallback(async () => {
    setPhase(STATE.LOADING);
    try {
      const res = await triggerSOS({ user_id: userId, week_context: currentWeek });
      setSosData(res);
      setTimestamp(res.event_timestamp_utc || new Date().toISOString());
      setPhase(STATE.ACTIVE);
    } catch (_err) {
      setPhase(STATE.ERROR);
    }
  }, [userId, currentWeek]);

  const handleResolve = useCallback(async (status) => {
    setPhase(STATE.RESOLVING);
    try {
      const res = await resolveSOS({
        user_id:             userId,
        event_timestamp_utc: timestamp,
        status,
        week_context:        currentWeek,
      });
      setResolveData(res);
      setPhase(STATE.DONE);
    } catch (_err) {
      setPhase(STATE.ERROR);
    }
  }, [userId, currentWeek, timestamp]);

  const handleReset = useCallback(() => {
    setPhase(STATE.IDLE);
    setSosData(null);
    setResolveData(null);
    setTimestamp(null);
  }, []);

  // ── IDLE ──────────────────────────────────────────────────────────────
  if (phase === STATE.IDLE) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <Text style={[styles.headerTitle, RTL.text]}>{t('SOS_SCREEN_TITLE')}</Text>
        </View>
        <View style={styles.centerContainer}>
          <Text style={[styles.empathyText, RTL.text]}>{t('SOS_RELAPSE_EMPATHY')}</Text>
          <TouchableOpacity
            style={styles.sosBtn}
            onPress={handleTrigger}
            accessibilityRole="button"
            accessibilityLabel={t('SOS_TRIGGER_BTN')}
          >
            <Text style={styles.sosBtnEmoji}>🆘</Text>
            <Text style={styles.sosBtnText}>{t('SOS_TRIGGER_BTN')}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ── LOADING ───────────────────────────────────────────────────────────
  if (phase === STATE.LOADING) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={COLORS.danger} />
          <Text style={[styles.loadingText, RTL.text]}>{t('SOS_TRIGGERING')}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // ── ERROR ─────────────────────────────────────────────────────────────
  if (phase === STATE.ERROR) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.centerContainer}>
          <Text style={[styles.errorText, RTL.text]}>{t('SOS_ERROR')}</Text>
          <TouchableOpacity style={styles.secondaryBtn} onPress={handleReset}>
            <Text style={styles.secondaryBtnText}>{t('SOS_BACK_BTN')}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ── ACTIVE — show protocol ────────────────────────────────────────────
  if (phase === STATE.ACTIVE || phase === STATE.RESOLVING) {
    const STEP_COLORS = ['#EF4444', '#F59E0B', '#10B981'];
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <Text style={[styles.headerTitle, RTL.text]}>{t('SOS_PROTOCOL_HEADER')}</Text>
        </View>
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          <StepCard number={1} title={t('SOS_STEP1_TITLE')} instruction={t('SOS_STEP1_INSTRUCTION')} accentColor={STEP_COLORS[0]} />
          <StepCard number={2} title={t('SOS_STEP2_TITLE')} instruction={t('SOS_STEP2_INSTRUCTION')} accentColor={STEP_COLORS[1]} />
          <StepCard number={3} title={t('SOS_STEP3_TITLE')} instruction={t('SOS_STEP3_INSTRUCTION')} accentColor={STEP_COLORS[2]} />

          <Text style={[styles.closingText, RTL.text]}>{t('SOS_CLOSING_HE')}</Text>

          <View style={styles.resolveSection}>
            <Text style={[styles.resolveTitle, RTL.text]}>{t('SOS_RESOLVE_TITLE')}</Text>
            <TouchableOpacity
              style={[styles.resolveBtn, { backgroundColor: '#10B981' }]}
              onPress={() => handleResolve('SUCCESS')}
              disabled={phase === STATE.RESOLVING}
              accessibilityRole="button"
            >
              {phase === STATE.RESOLVING
                ? <ActivityIndicator color="#fff" />
                : <Text style={styles.resolveBtnText}>{t('SOS_RESOLVE_SUCCESS_BTN')}</Text>
              }
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.resolveBtn, { backgroundColor: '#F59E0B', marginTop: SPACING.sm }]}
              onPress={() => handleResolve('LAPSE')}
              disabled={phase === STATE.RESOLVING}
              accessibilityRole="button"
            >
              <Text style={styles.resolveBtnText}>{t('SOS_RESOLVE_LAPSE_BTN')}</Text>
            </TouchableOpacity>
          </View>
          <View style={{ height: SPACING.xl }} />
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ── DONE ──────────────────────────────────────────────────────────────
  if (phase === STATE.DONE) {
    const isSuccess = resolveData?.resolution === 'SUCCESS';
    const msg = isSuccess
      ? (resolveData?.resolve_message_he || t('RESOLVE_SUCCESS_HE'))
      : (resolveData?.resolve_message_he || t('RESOLVE_LAPSE_ACK_HE'));

    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.header}>
          <Text style={[styles.headerTitle, RTL.text]}>{t('SOS_DONE_TITLE')}</Text>
        </View>
        <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
          <View style={[styles.doneCard, { borderColor: isSuccess ? '#10B981' : '#F59E0B' }]}>
            <Text style={styles.doneEmoji}>{isSuccess ? '✅' : '💛'}</Text>
            <Text style={[styles.doneMsg, RTL.text]}>{msg}</Text>
          </View>
          {resolveData?.morning_queue && (
            <View style={styles.morningCard}>
              <Text style={[styles.morningTitle, RTL.text]}>{t('MORNING_QUEUE_HEADER_HE')}</Text>
              <Text style={[styles.morningBody, RTL.text]}>{resolveData.morning_queue.lapse_habit_reset}</Text>
            </View>
          )}
          <TouchableOpacity style={[styles.secondaryBtn, { marginTop: SPACING.lg }]} onPress={handleReset}>
            <Text style={styles.secondaryBtnText}>{t('SOS_BACK_BTN')}</Text>
          </TouchableOpacity>
          <View style={{ height: SPACING.xl }} />
        </ScrollView>
      </SafeAreaView>
    );
  }

  return null;
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F9FAFB' },
  header: {
    backgroundColor:   '#fff',
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.md,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: {
    fontSize:   FONT.xl,
    fontWeight: '700',
    color:      COLORS.text,
  },
  centerContainer: {
    flex:           1,
    justifyContent: 'center',
    alignItems:     'center',
    padding:        SPACING.lg,
  },
  empathyText: {
    fontSize:     FONT.md,
    color:        COLORS.textSecondary,
    textAlign:    'center',
    marginBottom: SPACING.xl,
    lineHeight:   24,
  },
  sosBtn: {
    backgroundColor: COLORS.danger,
    borderRadius:    RADIUS.lg,
    paddingVertical: SPACING.lg,
    paddingHorizontal: SPACING.xl,
    alignItems:      'center',
    elevation:       4,
    shadowColor:     COLORS.danger,
    shadowOffset:    { width: 0, height: 4 },
    shadowOpacity:   0.3,
    shadowRadius:    8,
  },
  sosBtnEmoji: { fontSize: 48, marginBottom: SPACING.sm },
  sosBtnText:  { fontSize: FONT.lg, fontWeight: '700', color: '#fff' },

  loadingText: { marginTop: SPACING.md, fontSize: FONT.md, color: COLORS.textSecondary },
  errorText:   { fontSize: FONT.md, color: COLORS.danger, marginBottom: SPACING.md, textAlign: 'center' },

  scroll:        { flex: 1 },
  scrollContent: { padding: SPACING.md },

  stepCard: {
    backgroundColor:  '#fff',
    borderRadius:     RADIUS.md,
    padding:          SPACING.md,
    marginBottom:     SPACING.sm,
    borderStartWidth: 4,
    elevation:        2,
    shadowOffset:     { width: 0, height: 1 },
    shadowOpacity:    0.06,
    shadowRadius:     4,
  },
  stepHeader: { alignItems: 'center', marginBottom: SPACING.sm },
  stepBadge: {
    width: 28, height: 28, borderRadius: 14,
    justifyContent: 'center', alignItems: 'center',
    marginEnd: SPACING.sm,
  },
  stepBadgeText: { color: '#fff', fontWeight: '700', fontSize: FONT.sm },
  stepTitle:     { fontSize: FONT.md, fontWeight: '700', color: COLORS.text, flex: 1 },
  stepBody:      { fontSize: FONT.sm, color: COLORS.textSecondary, lineHeight: 22 },

  closingText: {
    fontSize:   FONT.md,
    color:      COLORS.primary,
    fontWeight: '600',
    textAlign:  'center',
    marginVertical: SPACING.md,
  },
  resolveSection: { marginTop: SPACING.sm },
  resolveTitle: {
    fontSize:     FONT.lg,
    fontWeight:   '700',
    color:        COLORS.text,
    marginBottom: SPACING.sm,
    textAlign:    'center',
  },
  resolveBtn: {
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.md,
    alignItems:      'center',
  },
  resolveBtnText: { color: '#fff', fontSize: FONT.md, fontWeight: '700' },

  doneCard: {
    backgroundColor: '#fff',
    borderRadius:    RADIUS.lg,
    padding:         SPACING.lg,
    borderWidth:     2,
    alignItems:      'center',
    marginBottom:    SPACING.md,
  },
  doneEmoji: { fontSize: 56, marginBottom: SPACING.md },
  doneMsg:   { fontSize: FONT.md, color: COLORS.text, lineHeight: 24, textAlign: 'center' },

  morningCard: {
    backgroundColor:  '#EFF6FF',
    borderRadius:     RADIUS.md,
    padding:          SPACING.md,
    borderStartWidth: 4,
    borderStartColor: COLORS.primary,
  },
  morningTitle: { fontSize: FONT.md, fontWeight: '700', color: COLORS.primary, marginBottom: SPACING.xs },
  morningBody:  { fontSize: FONT.sm, color: '#1E40AF', lineHeight: 22 },

  secondaryBtn: {
    borderWidth:     1,
    borderColor:     COLORS.border,
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.sm,
    alignItems:      'center',
    backgroundColor: '#fff',
  },
  secondaryBtnText: { fontSize: FONT.md, color: COLORS.text, fontWeight: '600' },
});
