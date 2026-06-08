// @flow
/**
 * WeeklySummaryCard.js — Phase 2 Weekly Aggregated Summary
 *
 * Fetches POST /api/v1/engine/weekly-summary in a background effect
 * (does NOT block the main UI render). Shows a skeleton while loading.
 *
 * States:
 *   idle     → nothing rendered (no days supplied yet)
 *   loading  → skeleton shimmer
 *   success  → metrics grid + OARS reflective question + insights
 *   error    → friendly Hebrew error + retry button
 *
 * ARCHITECTURE RULES (per ROADMAP.md):
 *   ✓ Zero clinical logic — all interpretation lives in the Orchestrator
 *   ✓ All Hebrew strings via t() from locales/he.json
 *   ✓ RTL: borderStartWidth, marginEnd, textAlign: right
 *   ✓ _apiOverride injection for tests
 *   ✓ Collapses/expands via LayoutAnimation to keep scroll layout stable
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  LayoutAnimation,
  Platform,
  UIManager,
} from 'react-native';

import { t }    from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

async function _defaultFetchSummary(payload) {
  const { fetchWeeklySummary } = require('../api/endpoints');
  return fetchWeeklySummary(payload);
}

// ─── Metric row sub-component ─────────────────────────────────────────────
function MetricRow({ label, value, unit, accent }) {
  if (value == null) return null;
  return (
    <View style={[styles.metricRow, RTL.row]}>
      <Text style={[styles.metricLabel, RTL.text]}>{label}</Text>
      <View style={[styles.metricValueRow, RTL.row]}>
        <Text style={[styles.metricValue, { color: accent ?? COLORS.primary }]}>
          {typeof value === 'number' ? value.toLocaleString('he-IL') : value}
        </Text>
        {unit ? (
          <Text style={styles.metricUnit}> {unit}</Text>
        ) : null}
      </View>
    </View>
  );
}

// ─── Skeleton row ─────────────────────────────────────────────────────────
function SkeletonRow() {
  return <View style={styles.skeletonRow} />;
}

// ─── Main component ───────────────────────────────────────────────────────
export default function WeeklySummaryCard({
  userId,
  currentWeek,
  days,            // Array<DailyRecord> — if null/empty, card renders nothing
  _apiOverride = null,
}) {
  const [fetchState, setFetchState] = useState('idle');   // idle|loading|success|error
  const [summary,    setSummary]    = useState(null);
  const [expanded,   setExpanded]   = useState(true);

  // ── Trigger fetch whenever days change and are non-empty ──────────────
  useEffect(() => {
    if (!days || days.length === 0) {
      setFetchState('idle');
      setSummary(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setFetchState('loading');
      try {
        const callApi = _apiOverride ?? _defaultFetchSummary;
        const result  = await callApi({ user_id: userId, current_week: currentWeek, days });
        if (!cancelled) {
          LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
          setSummary(result);
          setFetchState('success');
        }
      } catch (_err) {
        if (!cancelled) {
          LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
          setFetchState('error');
        }
      }
    };

    load();
    return () => { cancelled = true; };
  // Re-fetch only when the days array reference changes or week changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, currentWeek, userId]);

  // ── Retry ─────────────────────────────────────────────────────────────
  const handleRetry = useCallback(() => {
    setSummary(null);
    setFetchState('idle');
    // Trigger re-fetch by briefly marking idle; useEffect will re-run on next render
    // because we toggle fetchState which causes re-render → effect sees same `days`
    // but we force a new fetch by resetting and letting the effect re-trigger via key
    setFetchState('loading');

    const load = async () => {
      try {
        const callApi = _apiOverride ?? _defaultFetchSummary;
        const result  = await callApi({ user_id: userId, current_week: currentWeek, days });
        LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
        setSummary(result);
        setFetchState('success');
      } catch {
        setFetchState('error');
      }
    };
    load();
  }, [userId, currentWeek, days, _apiOverride]);

  // ── Collapse / expand ─────────────────────────────────────────────────
  const toggleExpand = useCallback(() => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((v) => !v);
  }, []);

  // ── Guard: no data yet ────────────────────────────────────────────────
  if (fetchState === 'idle') return null;

  const m = summary?.metrics ?? {};

  return (
    <View style={styles.card}>
      {/* ── Card header ───────────────────────────────────────────────── */}
      <TouchableOpacity
        style={[styles.headerRow, RTL.row]}
        onPress={toggleExpand}
        accessibilityRole="button"
        accessibilityLabel={expanded ? t('WEEKLY_CARD_COLLAPSE') : t('WEEKLY_CARD_EXPAND')}
      >
        <Text style={[styles.cardTitle, RTL.text]}>
          {t('WEEKLY_SUMMARY_HEADER')}
        </Text>
        <Text style={styles.chevron}>{expanded ? '▲' : '▼'}</Text>
      </TouchableOpacity>

      {expanded && (
        <>
          {/* ── Loading skeleton ───────────────────────────────────────── */}
          {fetchState === 'loading' && (
            <View style={styles.loadingBlock}>
              <ActivityIndicator color={COLORS.primary} />
              <Text style={[styles.loadingText, RTL.text]}>{t('WEEKLY_CARD_LOADING')}</Text>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </View>
          )}

          {/* ── Error state ────────────────────────────────────────────── */}
          {fetchState === 'error' && (
            <View style={styles.errorBlock}>
              <Text style={[styles.errorText, RTL.text]}>{t('WEEKLY_CARD_ERROR')}</Text>
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={handleRetry}
                accessibilityRole="button"
                accessibilityLabel={t('WEEKLY_CARD_RETRY')}
              >
                <Text style={styles.retryBtnText}>{t('WEEKLY_CARD_RETRY')}</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* ── Success: metrics + OARS ────────────────────────────────── */}
          {fetchState === 'success' && summary && (
            <>
              {/* Metrics grid */}
              <Text style={[styles.sectionTitle, RTL.text]}>
                {t('WEEKLY_CARD_METRICS_TITLE')}
              </Text>

              <MetricRow
                label={t('WEEKLY_AVG_SLEEP_LABEL')}
                value={m.avg_sleep_hours}
                unit={t('WEEKLY_AVG_SLEEP_UNIT')}
                accent={COLORS.sleepFill}
              />
              <MetricRow
                label={t('WEEKLY_AVG_STEPS_LABEL')}
                value={m.avg_steps != null ? Math.round(m.avg_steps) : null}
                unit={t('WEEKLY_AVG_STEPS_UNIT')}
                accent={COLORS.stepsFill}
              />
              <MetricRow
                label={t('WEEKLY_TOTAL_STRENGTH_LABEL')}
                value={m.total_strength_sessions > 0 ? m.total_strength_sessions : null}
                unit={t('WEEKLY_TOTAL_STRENGTH_UNIT')}
                accent='#7C3AED'
              />
              <MetricRow
                label={t('WEEKLY_AVG_RHR_LABEL')}
                value={m.avg_resting_hr}
                unit={t('WEEKLY_AVG_RHR_UNIT')}
                accent={COLORS.warning}
              />

              {/* Sleep trend */}
              {m.sleep_trend ? (
                <Text style={[styles.trendLine, RTL.text]}>{m.sleep_trend}</Text>
              ) : null}

              <View style={styles.divider} />

              {/* Insights */}
              {summary.insights_he?.length > 0 && (
                <>
                  <Text style={[styles.sectionTitle, RTL.text]}>
                    {t('WEEKLY_CARD_INSIGHTS_TITLE')}
                  </Text>
                  {summary.insights_he.map((ins, i) => (
                    <View key={i} style={[styles.insightRow, RTL.row]}>
                      <Text style={styles.bullet}>•</Text>
                      <Text style={[styles.insightText, RTL.text]}>{ins}</Text>
                    </View>
                  ))}
                  <View style={styles.divider} />
                </>
              )}

              {/* OARS reflective question */}
              {summary.oars_summary_he ? (
                <View style={styles.oarsBox}>
                  <Text style={[styles.oarsLabel, RTL.text]}>
                    {t('WEEKLY_CARD_OARS_LABEL')}
                  </Text>
                  <Text style={[styles.oarsQuestion, RTL.text]}>
                    {summary.oars_summary_he}
                  </Text>
                </View>
              ) : null}
            </>
          )}
        </>
      )}
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.surface,
    borderRadius:    RADIUS.lg,
    padding:         SPACING.md,
    marginTop:       SPACING.md,
    borderStartWidth: 4,
    borderStartColor: COLORS.primary,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 5,
    elevation: 3,
  },

  headerRow: {
    alignItems:   'center',
    marginBottom: SPACING.xs,
  },
  cardTitle: {
    flex:       1,
    fontSize:   FONT.lg,
    fontWeight: '700',
    color:      COLORS.textPrimary,
  },
  chevron: {
    fontSize: FONT.xs,
    color:    COLORS.textDisabled,
    paddingStart: SPACING.sm,
  },

  // Loading
  loadingBlock: {
    alignItems: 'center',
    paddingVertical: SPACING.md,
    gap: SPACING.xs,
  },
  loadingText: {
    fontSize: FONT.sm,
    color:    COLORS.textSecondary,
    marginTop: SPACING.xs,
  },
  skeletonRow: {
    height:       12,
    width:        '80%',
    borderRadius: RADIUS.pill,
    backgroundColor: COLORS.border,
    marginVertical: SPACING.xxs,
  },

  // Error
  errorBlock: {
    alignItems: 'center',
    paddingVertical: SPACING.md,
    gap: SPACING.sm,
  },
  errorText: {
    fontSize: FONT.sm,
    color:    COLORS.danger,
  },
  retryBtn: {
    paddingHorizontal: SPACING.md,
    paddingVertical:   SPACING.xs,
    borderRadius:      RADIUS.pill,
    borderWidth:       1,
    borderColor:       COLORS.primary,
  },
  retryBtnText: {
    color:    COLORS.primary,
    fontSize: FONT.sm,
    fontWeight: '600',
  },

  // Metrics
  sectionTitle: {
    fontSize:     FONT.sm,
    fontWeight:   '700',
    color:        COLORS.textSecondary,
    marginBottom: SPACING.xs,
    marginTop:    SPACING.xs,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metricRow: {
    justifyContent: 'space-between',
    alignItems:     'center',
    paddingVertical: SPACING.xxs,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  metricLabel: {
    flex:     1,
    fontSize: FONT.sm,
    color:    COLORS.textSecondary,
  },
  metricValueRow: {
    alignItems: 'baseline',
  },
  metricValue: {
    fontSize:   FONT.md,
    fontWeight: '700',
  },
  metricUnit: {
    fontSize: FONT.xs,
    color:    COLORS.textDisabled,
  },
  trendLine: {
    fontSize:  FONT.xs,
    color:     COLORS.textSecondary,
    marginTop: SPACING.xxs,
  },

  divider: {
    height: 1,
    backgroundColor: COLORS.border,
    marginVertical: SPACING.sm,
  },

  // Insights
  insightRow: {
    alignItems:   'flex-start',
    marginBottom: SPACING.xxs,
    gap:          SPACING.xs,
  },
  bullet: {
    fontSize:  FONT.sm,
    color:     COLORS.primary,
    lineHeight: FONT.sm * 1.6,
  },
  insightText: {
    flex:       1,
    fontSize:   FONT.sm,
    color:      COLORS.textPrimary,
    lineHeight: FONT.sm * 1.6,
  },

  // OARS
  oarsBox: {
    backgroundColor: '#EFF6FF',
    borderRadius:    RADIUS.md,
    padding:         SPACING.sm,
    borderStartWidth: 3,
    borderStartColor: COLORS.primary,
  },
  oarsLabel: {
    fontSize:     FONT.xs,
    fontWeight:   '700',
    color:        COLORS.primary,
    marginBottom: SPACING.xxs,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  oarsQuestion: {
    fontSize:   FONT.md,
    fontWeight: '600',
    color:      COLORS.textPrimary,
    lineHeight: FONT.md * 1.6,
  },
});
