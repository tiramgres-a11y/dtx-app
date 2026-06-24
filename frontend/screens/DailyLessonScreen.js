// @flow
/**
 * DailyLessonScreen — the daily curriculum lesson (Worker 2 / Frontend Manager)
 *
 * Fetches GET /api/v1/content/today and renders the day's lesson:
 *   hero image (Unsplash) + photographer credit, phase/day badge, key takeaway,
 *   educational text, the daily mission, and an optional supporting-video button.
 *
 * Zero clinical logic — all content comes from the backend curriculum.
 * All static UI strings come from locales/he.json via t().
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { fetchTodayContent }                    from '../api/endpoints';
import { useUser }                              from '../context/UserContext';
import ExternalResourceButton                   from '../components/ExternalResourceButton';
import { COLORS, FONT, SPACING, RADIUS, RTL }   from '../components/tokens';
import { t }                                    from '../utils/i18n';

const PHASE_LABEL = {
  1: 'PHASE_1_LABEL',
  2: 'PHASE_2_LABEL',
  3: 'PHASE_3_LABEL',
};

export default function DailyLessonScreen() {
  const { userId } = useUser();

  const [lesson,    setLesson]    = useState(null);
  const [status,    setStatus]    = useState('loading'); // 'loading' | 'ok' | 'error'
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchTodayContent(userId);
      setLesson(data);
      setStatus('ok');
    } catch (_err) {
      setStatus('error');
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  // ── Loading ──
  if (status === 'loading') {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={[styles.loadingText, RTL.text]}>{t('LESSON_LOADING')}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // ── Error ──
  if (status === 'error' || !lesson) {
    return (
      <SafeAreaView style={styles.safe} edges={['top']}>
        <View style={styles.centered}>
          <Text style={styles.errorEmoji}>📡</Text>
          <Text style={[styles.errorText, RTL.text]}>{t('LESSON_ERROR')}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={load} accessibilityRole="button">
            <Text style={styles.retryBtnText}>{t('LESSON_RETRY_BTN')}</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const { phase, day_number, theme, keyTakeaway, educationalText,
          dailyMission, image, videoUrl, videoTitle } = lesson;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />
        }
      >
        {/* Hero image */}
        {image?.image_url && (
          <View style={styles.heroWrap}>
            <Image source={{ uri: image.image_url }} style={styles.hero} resizeMode="cover" />
            {image.photographer && (
              <Text style={styles.credit}>
                {t('LESSON_PHOTO_CREDIT')} {image.photographer} / Unsplash
              </Text>
            )}
          </View>
        )}

        {/* Phase + day badge */}
        <View style={[styles.badgeRow, RTL.row]}>
          <View style={styles.phaseBadge}>
            <Text style={styles.phaseBadgeText}>{t(PHASE_LABEL[phase] || 'PHASE_1_LABEL')}</Text>
          </View>
          <Text style={[styles.dayLabel, RTL.text]}>
            {t('LESSON_DAY_LABEL')} {day_number} / 91
          </Text>
        </View>

        {/* Theme title */}
        {theme && (
          <Text style={[styles.theme, RTL.text]}>{theme.replace(/_/g, ' ')}</Text>
        )}

        {/* Key takeaway — highlighted */}
        <View style={styles.takeawayBox}>
          <Text style={[styles.takeawayText, RTL.text]}>{keyTakeaway}</Text>
        </View>

        {/* Educational text */}
        <Text style={[styles.body, RTL.text]}>{educationalText}</Text>

        {/* Daily mission */}
        {dailyMission?.description && (
          <View style={styles.missionCard}>
            <Text style={[styles.missionTitle, RTL.text]}>{t('LESSON_MISSION_TITLE')}</Text>
            <Text style={[styles.missionText, RTL.text]}>{dailyMission.description}</Text>
          </View>
        )}

        {/* Supporting video — only when a url is present */}
        {videoUrl && (
          <ExternalResourceButton url={videoUrl} label={videoTitle || t('LESSON_WATCH_VIDEO')} />
        )}

        <View style={styles.bottomPad} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.surfaceAlt },
  scrollContent: { paddingBottom: SPACING.lg },

  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: SPACING.lg },
  loadingText: { marginTop: SPACING.sm, color: COLORS.textSecondary, fontSize: FONT.sm },
  errorEmoji: { fontSize: 44, marginBottom: SPACING.sm },
  errorText: { color: COLORS.textSecondary, fontSize: FONT.md, textAlign: 'center', lineHeight: FONT.md * 1.5 },
  retryBtn: {
    marginTop: SPACING.md, backgroundColor: COLORS.primary, borderRadius: RADIUS.pill,
    paddingHorizontal: SPACING.lg, paddingVertical: SPACING.xs,
  },
  retryBtnText: { color: '#fff', fontSize: FONT.sm, fontWeight: '700' },

  heroWrap: { width: '100%', backgroundColor: COLORS.border },
  hero: { width: '100%', height: 200 },
  credit: {
    fontSize: FONT.xxs, color: '#fff', backgroundColor: '#00000066',
    position: 'absolute', bottom: 0, start: 0, paddingHorizontal: SPACING.xs, paddingVertical: 2,
  },

  badgeRow: {
    alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: SPACING.md, paddingTop: SPACING.md,
  },
  phaseBadge: {
    backgroundColor: COLORS.primaryLight, borderRadius: RADIUS.pill,
    paddingHorizontal: SPACING.sm, paddingVertical: 2,
  },
  phaseBadgeText: { color: COLORS.primary, fontSize: FONT.xs, fontWeight: '700' },
  dayLabel: { color: COLORS.textSecondary, fontSize: FONT.sm, fontWeight: '600' },

  theme: {
    fontSize: FONT.xl, fontWeight: '800', color: COLORS.textPrimary,
    paddingHorizontal: SPACING.md, paddingTop: SPACING.xs,
  },

  takeawayBox: {
    backgroundColor: COLORS.primaryLight, borderStartWidth: 4, borderStartColor: COLORS.primary,
    borderRadius: RADIUS.md, marginHorizontal: SPACING.md, marginTop: SPACING.md,
    padding: SPACING.sm,
  },
  takeawayText: { color: COLORS.textPrimary, fontSize: FONT.md, fontWeight: '600', lineHeight: FONT.md * 1.5 },

  body: {
    color: COLORS.textPrimary, fontSize: FONT.md, lineHeight: FONT.md * 1.7,
    paddingHorizontal: SPACING.md, paddingTop: SPACING.md,
  },

  missionCard: {
    backgroundColor: COLORS.surface, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: COLORS.border,
    marginHorizontal: SPACING.md, marginTop: SPACING.lg, padding: SPACING.md,
  },
  missionTitle: { fontSize: FONT.sm, fontWeight: '700', color: COLORS.success, marginBottom: SPACING.xs },
  missionText: { fontSize: FONT.md, color: COLORS.textPrimary, lineHeight: FONT.md * 1.6 },

  bottomPad: { height: SPACING.lg },
});
