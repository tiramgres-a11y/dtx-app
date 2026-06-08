// @flow
/**
 * HistoryScreen — Weekly summary fetched from Orchestrator.
 * Calls POST /api/v1/engine/weekly-summary with MOCK_WEEKLY_DAYS.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
} from 'react-native';

import { t }               from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from '../components/tokens';
import { useUser }         from '../context/UserContext';
import { fetchWeeklySummary } from '../api/endpoints';

// Demo days payload (same as DashboardScreen mock — no real sensor yet)
const DEMO_DAYS = [
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

function MetricRow({ label, value, unit, accentColor }) {
  return (
    <View style={[styles.metricRow, RTL.row]}>
      <View style={[styles.metricDot, { backgroundColor: accentColor || COLORS.primary }]} />
      <Text style={[styles.metricLabel, RTL.text]}>{label}</Text>
      <Text style={[styles.metricValue, { color: accentColor || COLORS.text }]}>
        {value} <Text style={styles.metricUnit}>{unit}</Text>
      </Text>
    </View>
  );
}

export default function HistoryScreen() {
  const { userId, currentWeek } = useUser();

  const [loading,  setLoading]  = useState(false);
  const [summary,  setSummary]  = useState(null);
  const [error,    setError]    = useState(false);

  const handleLoad = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await fetchWeeklySummary({
        user_id:      userId,
        current_week: currentWeek,
        days:         DEMO_DAYS,
      });
      setSummary(res);
    } catch (_err) {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [userId, currentWeek]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={[styles.headerTitle, RTL.text]}>{t('HISTORY_TITLE')}</Text>
        <Text style={[styles.headerSub, RTL.text]}>
          {t('HISTORY_WEEK_SELECTOR')} {currentWeek}
        </Text>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Load button */}
        {!summary && !loading && (
          <TouchableOpacity style={styles.loadBtn} onPress={handleLoad} accessibilityRole="button">
            <Text style={styles.loadBtnText}>{t('HISTORY_LOAD_BTN')}</Text>
          </TouchableOpacity>
        )}

        {/* Loading */}
        {loading && (
          <View style={styles.centerMsg}>
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text style={[styles.loadingText, RTL.text]}>{t('HISTORY_LOADING')}</Text>
          </View>
        )}

        {/* Error */}
        {error && !loading && (
          <View style={styles.centerMsg}>
            <Text style={[styles.errorText, RTL.text]}>{t('HISTORY_ERROR')}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={handleLoad}>
              <Text style={styles.retryBtnText}>{t('WEEKLY_CARD_RETRY')}</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Summary */}
        {summary && !loading && (
          <>
            {/* Metrics */}
            <View style={styles.card}>
              <Text style={[styles.cardTitle, RTL.text]}>{t('WEEKLY_CARD_METRICS_TITLE')}</Text>
              {summary.avg_sleep_hours != null && (
                <MetricRow
                  label={t('HISTORY_AVG_SLEEP')}
                  value={summary.avg_sleep_hours.toFixed(1)}
                  unit={t('HISTORY_HOURS')}
                  accentColor={COLORS.sleepFill}
                />
              )}
              {summary.avg_steps != null && (
                <MetricRow
                  label={t('HISTORY_AVG_STEPS')}
                  value={Math.round(summary.avg_steps).toLocaleString()}
                  unit={t('HISTORY_STEPS')}
                  accentColor={COLORS.stepsFill}
                />
              )}
              {summary.total_strength_sessions != null && (
                <MetricRow
                  label={t('HISTORY_STRENGTH')}
                  value={summary.total_strength_sessions}
                  unit={t('HISTORY_SESSIONS')}
                  accentColor={COLORS.primary}
                />
              )}
              {summary.total_cardio_sessions != null && (
                <MetricRow
                  label={t('HISTORY_CARDIO')}
                  value={summary.total_cardio_sessions}
                  unit={t('HISTORY_SESSIONS')}
                  accentColor='#8B5CF6'
                />
              )}
              {summary.avg_resting_hr != null && (
                <MetricRow
                  label={t('HISTORY_AVG_RHR')}
                  value={Math.round(summary.avg_resting_hr)}
                  unit={t('HISTORY_BPM')}
                  accentColor={COLORS.danger}
                />
              )}
            </View>

            {/* Insights */}
            {summary.insights && summary.insights.length > 0 && (
              <View style={styles.card}>
                <Text style={[styles.cardTitle, RTL.text]}>{t('WEEKLY_CARD_INSIGHTS_TITLE')}</Text>
                {summary.insights.map((insight, i) => (
                  <View key={i} style={styles.insightRow}>
                    <Text style={styles.insightBullet}>•</Text>
                    <Text style={[styles.insightText, RTL.text]}>{insight}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* OARS reflection */}
            {summary.oars_reflection_he && (
              <View style={styles.oarsCard}>
                <Text style={[styles.oarsLabel, RTL.text]}>{t('HISTORY_OARS_LABEL')}</Text>
                <Text style={[styles.oarsText, RTL.text]}>{summary.oars_reflection_he}</Text>
              </View>
            )}

            {/* Reload */}
            <TouchableOpacity style={styles.retryBtn} onPress={handleLoad}>
              <Text style={styles.retryBtnText}>{t('WEEKLY_CARD_RETRY')}</Text>
            </TouchableOpacity>
          </>
        )}

        <View style={{ height: SPACING.xl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F9FAFB' },
  header: {
    backgroundColor:   '#fff',
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.md,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: FONT.xl, fontWeight: '700', color: COLORS.text },
  headerSub:   { fontSize: FONT.sm, color: COLORS.textSecondary, marginTop: 2 },

  scroll:        { flex: 1 },
  scrollContent: { padding: SPACING.md },

  loadBtn: {
    backgroundColor: COLORS.primary,
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.md,
    alignItems:      'center',
    marginBottom:    SPACING.md,
  },
  loadBtnText: { color: '#fff', fontSize: FONT.md, fontWeight: '700' },

  centerMsg:   { alignItems: 'center', paddingVertical: SPACING.xl },
  loadingText: { marginTop: SPACING.sm, fontSize: FONT.md, color: COLORS.textSecondary },
  errorText:   { fontSize: FONT.md, color: COLORS.danger, marginBottom: SPACING.md, textAlign: 'center' },

  retryBtn: {
    borderWidth:     1,
    borderColor:     COLORS.border,
    borderRadius:    RADIUS.md,
    paddingVertical: SPACING.sm,
    alignItems:      'center',
    backgroundColor: '#fff',
    marginTop:       SPACING.sm,
  },
  retryBtnText: { fontSize: FONT.md, color: COLORS.text, fontWeight: '600' },

  card: {
    backgroundColor: '#fff',
    borderRadius:    RADIUS.lg,
    padding:         SPACING.md,
    marginBottom:    SPACING.sm,
    elevation:       2,
    shadowOffset:    { width: 0, height: 1 },
    shadowOpacity:   0.06,
    shadowRadius:    4,
  },
  cardTitle: { fontSize: FONT.lg, fontWeight: '700', color: COLORS.text, marginBottom: SPACING.sm },

  metricRow:   { alignItems: 'center', paddingVertical: SPACING.xs },
  metricDot:   { width: 10, height: 10, borderRadius: 5, marginEnd: SPACING.sm },
  metricLabel: { flex: 1, fontSize: FONT.md, color: COLORS.textSecondary },
  metricValue: { fontSize: FONT.md, fontWeight: '700' },
  metricUnit:  { fontSize: FONT.sm, fontWeight: '400', color: COLORS.textSecondary },

  insightRow:    { flexDirection: 'row', marginBottom: SPACING.xs },
  insightBullet: { color: COLORS.primary, fontWeight: '700', marginEnd: SPACING.xs, fontSize: FONT.md },
  insightText:   { flex: 1, fontSize: FONT.sm, color: COLORS.text, lineHeight: 22 },

  oarsCard: {
    backgroundColor:  '#EFF6FF',
    borderRadius:     RADIUS.md,
    padding:          SPACING.md,
    borderStartWidth: 4,
    borderStartColor: COLORS.primary,
    marginBottom:     SPACING.sm,
  },
  oarsLabel: { fontSize: FONT.sm, fontWeight: '700', color: COLORS.primary, marginBottom: SPACING.xs },
  oarsText:  { fontSize: FONT.md, color: '#1E40AF', lineHeight: 24 },
});
