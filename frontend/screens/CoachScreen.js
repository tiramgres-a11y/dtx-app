// @flow
/**
 * CoachScreen.js — AI Mentor Coach chat (Worker 2 / Frontend Manager)
 *
 * RTL Hebrew chat interface over POST /api/v1/mentor/chat.
 * The backend "cognitive control room" (llm_router.py) produces the
 * OARS-compliant response; this screen renders it — zero clinical logic here.
 *
 * Message shape (local state only — no persistence yet):
 *   { id: string, role: 'user'|'coach'|'error', text: string,
 *     actionUrl?: string|null, actionLabel?: string|null }
 *
 * ARCHITECTURE RULES (per ROADMAP.md):
 *   ✓ All static UI strings come from locales/he.json via t()
 *   ✓ Coach message text comes from the Orchestrator response — never local
 *   ✓ RTL layout via tokens.RTL; no marginLeft/Right — only Start/End
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { sendMentorMessage, fetchMentorHistory } from '../api/endpoints';
import { useUser }                              from '../context/UserContext';
import ExternalResourceButton                   from '../components/ExternalResourceButton';
import { COLORS, FONT, SPACING, RADIUS, RTL }   from '../components/tokens';
import { t }                                    from '../utils/i18n';

let _msgCounter = 0;
const nextId = () => `msg-${Date.now()}-${_msgCounter++}`;

export default function CoachScreen() {
  const { userId, currentWeek, baselineRHR } = useUser();

  const [messages,  setMessages]  = useState([]);   // newest LAST
  const [draft,     setDraft]     = useState('');
  const [isSending, setIsSending] = useState(false);

  const listRef = useRef(null);

  // Restore persisted conversation on mount — chat survives app restarts.
  // Silent failure: an empty chat with the welcome state is a fine fallback.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchMentorHistory(userId);
        if (cancelled || !res?.messages?.length) return;
        setMessages(res.messages.map((m) => ({
          id:          nextId(),
          role:        m.role === 'coach' ? 'coach' : 'user',
          text:        m.content,
          actionUrl:   m.action_url   || null,
          actionLabel: m.action_label || null,
        })));
      } catch (_err) { /* offline / first run — keep empty state */ }
    })();
    return () => { cancelled = true; };
  }, [userId]);

  const scrollToEnd = useCallback(() => {
    // Defer so FlatList has rendered the new row first
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, []);

  // Core send routine — used by both the input bar and the quick-action chips
  const sendText = useCallback(async (text) => {
    if (!text || isSending) return;
    setIsSending(true);
    setMessages((prev) => [...prev, { id: nextId(), role: 'user', text }]);
    scrollToEnd();

    try {
      const res = await sendMentorMessage({
        user_id:      userId,
        current_week: currentWeek,
        free_text:    text,
        ...(baselineRHR != null ? { baseline_rhr: baselineRHR } : {}),
      });
      setMessages((prev) => [...prev, {
        id:          nextId(),
        role:        'coach',
        text:        res.mentor_text,
        actionUrl:   res.action_url   || null,
        actionLabel: res.action_label || null,
      }]);
    } catch (_err) {
      setMessages((prev) => [...prev, {
        id:   nextId(),
        role: 'error',
        text: t('COACH_ERROR'),
      }]);
    } finally {
      setIsSending(false);
      scrollToEnd();
    }
  }, [isSending, userId, currentWeek, baselineRHR, scrollToEnd]);

  const handleSend = useCallback(() => {
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    sendText(text);
  }, [draft, sendText]);

  const handleChip = useCallback((promptKey) => {
    sendText(t(promptKey));
  }, [sendText]);

  const renderMessage = useCallback(({ item }) => {
    if (item.role === 'user') {
      return (
        <View style={[styles.bubble, styles.userBubble]}>
          <Text style={[styles.userText, RTL.text]}>{item.text}</Text>
        </View>
      );
    }
    if (item.role === 'error') {
      return (
        <View style={[styles.bubble, styles.errorBubble]}>
          <Text style={[styles.errorText, RTL.text]}>{item.text}</Text>
        </View>
      );
    }
    return (
      <View style={[styles.bubble, styles.coachBubble]}>
        <Text style={[styles.coachText, RTL.text]}>{item.text}</Text>
        <ExternalResourceButton url={item.actionUrl} label={item.actionLabel} />
      </View>
    );
  }, []);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Text style={[styles.title, RTL.text]}>{t('COACH_SCREEN_TITLE')}</Text>

        <FlatList
          ref={listRef}
          style={styles.flex}
          contentContainerStyle={styles.listContent}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={renderMessage}
          onContentSizeChange={scrollToEnd}
          ListEmptyComponent={
            <View style={styles.emptyWrap}>
              <Text style={styles.emptyEmoji}>💬</Text>
              <Text style={[styles.emptyText, RTL.text]}>{t('COACH_EMPTY_STATE')}</Text>
            </View>
          }
        />

        {isSending && (
          <View style={[styles.typingRow, RTL.row]}>
            <ActivityIndicator size="small" color={COLORS.primary} />
            <Text style={[styles.typingText, RTL.text]}>{t('COACH_TYPING')}</Text>
          </View>
        )}

        {/* Quick-action chips — pre-planning protocol + common questions */}
        <View style={[styles.chipsRow, RTL.row]}>
          {[
            ['COACH_CHIP_WEEKLY_PLAN', 'COACH_PROMPT_WEEKLY_PLAN'],
            ['COACH_CHIP_MEAL_NOW',    'COACH_PROMPT_MEAL_NOW'],
            ['COACH_CHIP_WORKOUT',     'COACH_PROMPT_WORKOUT'],
          ].map(([labelKey, promptKey]) => (
            <TouchableOpacity
              key={labelKey}
              style={[styles.chip, isSending && styles.chipDisabled]}
              onPress={() => handleChip(promptKey)}
              disabled={isSending}
              accessibilityRole="button"
              accessibilityLabel={t(labelKey)}
            >
              <Text style={styles.chipText}>{t(labelKey)}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={[styles.inputRow, RTL.row]}>
          <TextInput
            style={[styles.input, RTL.text]}
            value={draft}
            onChangeText={setDraft}
            placeholder={t('COACH_INPUT_PLACEHOLDER')}
            placeholderTextColor={COLORS.textSecondary}
            multiline
            maxLength={500}
            editable={!isSending}
            onSubmitEditing={handleSend}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!draft.trim() || isSending) && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={!draft.trim() || isSending}
            accessibilityRole="button"
            accessibilityLabel={t('COACH_SEND_BTN')}
          >
            <Text style={styles.sendBtnText}>{t('COACH_SEND_BTN')}</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.surfaceAlt },
  flex: { flex: 1 },

  title: {
    fontSize:          FONT.xl,
    fontWeight:        '700',
    color:             COLORS.textPrimary,
    paddingHorizontal: SPACING.md,
    paddingTop:        SPACING.md,
    paddingBottom:     SPACING.sm,
  },

  listContent: {
    paddingHorizontal: SPACING.md,
    paddingBottom:     SPACING.sm,
    flexGrow:          1,
  },

  // ── Bubbles ──
  bubble: {
    maxWidth:      '85%',
    borderRadius:  RADIUS.lg,
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xs,
    marginBottom:  SPACING.xs,
  },
  userBubble: {
    alignSelf:       'flex-start',   // RTL: visually the right side
    backgroundColor: COLORS.primary,
    borderBottomStartRadius: RADIUS.sm,
  },
  coachBubble: {
    alignSelf:       'flex-end',     // RTL: visually the left side
    backgroundColor: COLORS.surface,
    borderWidth:     1,
    borderColor:     COLORS.border,
    borderBottomEndRadius: RADIUS.sm,
  },
  errorBubble: {
    alignSelf:       'flex-end',
    backgroundColor: '#FEF2F2',
    borderWidth:     1,
    borderColor:     COLORS.danger,
  },

  userText:  { color: '#FFFFFF',          fontSize: FONT.md, lineHeight: FONT.md * 1.5 },
  coachText: { color: COLORS.textPrimary, fontSize: FONT.md, lineHeight: FONT.md * 1.5 },
  errorText: { color: COLORS.danger,      fontSize: FONT.sm, lineHeight: FONT.sm * 1.5 },

  // ── Empty state ──
  emptyWrap: {
    flex:           1,
    alignItems:     'center',
    justifyContent: 'center',
    paddingHorizontal: SPACING.lg,
  },
  emptyEmoji: { fontSize: 48, marginBottom: SPACING.sm },
  emptyText:  {
    fontSize:   FONT.md,
    color:      COLORS.textSecondary,
    textAlign:  'center',
    lineHeight: FONT.md * 1.6,
  },

  // ── Typing indicator ──
  typingRow: {
    alignItems:        'center',
    paddingHorizontal: SPACING.md,
    paddingBottom:     SPACING.xs,
  },
  typingText: {
    fontSize:    FONT.xs,
    color:       COLORS.textSecondary,
    marginStart: SPACING.xs,
  },

  // ── Quick-action chips ──
  chipsRow: {
    flexWrap:          'wrap',
    paddingHorizontal: SPACING.md,
    paddingBottom:     SPACING.xs,
  },
  chip: {
    backgroundColor:   COLORS.primaryLight,
    borderColor:       COLORS.primary,
    borderWidth:       1,
    borderRadius:      RADIUS.pill,
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xxs,
    marginEnd:         SPACING.xs,
    marginBottom:      SPACING.xxs,
  },
  chipDisabled: { opacity: 0.5 },
  chipText: {
    fontSize:   FONT.xs,
    fontWeight: '600',
    color:      COLORS.primary,
  },

  // ── Input bar ──
  inputRow: {
    alignItems:        'flex-end',
    paddingHorizontal: SPACING.md,
    paddingBottom:     SPACING.sm,
    paddingTop:        SPACING.xs,
    backgroundColor:   COLORS.surface,
    borderTopWidth:    1,
    borderTopColor:    COLORS.border,
  },
  input: {
    flex:              1,
    minHeight:         44,
    maxHeight:         120,
    backgroundColor:   COLORS.surfaceAlt,
    borderRadius:      RADIUS.lg,
    borderWidth:       1,
    borderColor:       COLORS.border,
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xs,
    fontSize:          FONT.md,
    color:             COLORS.textPrimary,
  },
  sendBtn: {
    marginStart:       SPACING.xs,
    backgroundColor:   COLORS.primary,
    borderRadius:      RADIUS.pill,
    paddingHorizontal: SPACING.md,
    height:            44,
    alignItems:        'center',
    justifyContent:    'center',
  },
  sendBtnDisabled: { backgroundColor: COLORS.textDisabled },
  sendBtnText:     { color: '#FFFFFF', fontSize: FONT.sm, fontWeight: '700' },
});
