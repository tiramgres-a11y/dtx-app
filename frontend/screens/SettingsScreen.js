// @flow
/**
 * SettingsScreen — User config: userId, currentWeek, baselineRHR, server status.
 */

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
} from 'react-native';

import { t }          from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from '../components/tokens';
import { useUser }    from '../context/UserContext';
import { healthCheck } from '../api/endpoints';
import { getInstance } from '../api/client';

const WEEK_OPTIONS = [1,2,3,4,5,6,7,8,9,10,11,12,13];

function SectionHeader({ label }) {
  return <Text style={[styles.sectionHeader, RTL.text]}>{label}</Text>;
}

export default function SettingsScreen() {
  const {
    userId,      setUserId,
    currentWeek, setCurrentWeek,
    baselineRHR, setBaselineRHR,
  } = useUser();

  // RHR save state
  const [rhrInput,   setRhrInput]   = useState(baselineRHR ? String(baselineRHR) : '');
  const [rhrStatus,  setRhrStatus]  = useState(null); // 'saving' | 'saved' | 'error'

  // Server check state
  const [serverStatus, setServerStatus] = useState(null); // 'checking' | 'ok' | 'error'

  const handleSaveRHR = useCallback(async () => {
    const val = parseInt(rhrInput, 10);
    if (isNaN(val) || val < 20 || val > 250) {
      setRhrStatus('error');
      return;
    }
    setRhrStatus('saving');
    try {
      await getInstance().post(
        `/api/v1/user/baseline-rhr?user_id=${encodeURIComponent(userId)}&baseline_rhr=${val}`
      );
      setBaselineRHR(val);
      setRhrStatus('saved');
    } catch (_err) {
      setRhrStatus('error');
    }
  }, [rhrInput, userId, setBaselineRHR]);

  const handleCheckServer = useCallback(async () => {
    setServerStatus('checking');
    try {
      await healthCheck();
      setServerStatus('ok');
    } catch (_err) {
      setServerStatus('error');
    }
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={[styles.headerTitle, RTL.text]}>{t('SETTINGS_TITLE')}</Text>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>

        {/* ── User profile ────────────────────────────────────────── */}
        <SectionHeader label={t('SETTINGS_USER_SECTION')} />
        <View style={styles.card}>
          <Text style={[styles.fieldLabel, RTL.text]}>{t('SETTINGS_USER_ID_LABEL')}</Text>
          <TextInput
            style={[styles.textInput, RTL.text]}
            value={userId}
            onChangeText={setUserId}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="done"
          />

          <Text style={[styles.fieldLabel, { marginTop: SPACING.md }, RTL.text]}>
            {t('SETTINGS_WEEK_LABEL')}
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.weekRow}>
            {WEEK_OPTIONS.map((w) => (
              <TouchableOpacity
                key={w}
                style={[styles.weekChip, currentWeek === w && styles.weekChipActive]}
                onPress={() => setCurrentWeek(w)}
                accessibilityRole="button"
              >
                <Text style={[styles.weekChipText, currentWeek === w && styles.weekChipTextActive]}>
                  {w}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* ── Baseline RHR ────────────────────────────────────────── */}
        <SectionHeader label={t('SETTINGS_RHR_SECTION')} />
        <View style={styles.card}>
          <Text style={[styles.fieldLabel, RTL.text]}>{t('SETTINGS_RHR_LABEL')}</Text>
          <View style={[styles.inputRow, RTL.row]}>
            <TextInput
              style={[styles.textInput, { flex: 1 }, RTL.text]}
              value={rhrInput}
              onChangeText={(v) => { setRhrInput(v); setRhrStatus(null); }}
              keyboardType="numeric"
              maxLength={3}
              returnKeyType="done"
              placeholder="60"
            />
            <TouchableOpacity
              style={[styles.saveBtn, rhrStatus === 'saving' && styles.saveBtnDisabled]}
              onPress={handleSaveRHR}
              disabled={rhrStatus === 'saving'}
              accessibilityRole="button"
            >
              {rhrStatus === 'saving'
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={styles.saveBtnText}>{t('SETTINGS_RHR_SAVE_BTN')}</Text>
              }
            </TouchableOpacity>
          </View>
          {rhrStatus === 'saved' && (
            <Text style={[styles.statusOk, RTL.text]}>{t('SETTINGS_RHR_SAVED')}</Text>
          )}
          {rhrStatus === 'error' && (
            <Text style={[styles.statusErr, RTL.text]}>{t('SETTINGS_RHR_ERROR')}</Text>
          )}
          {baselineRHR && (
            <Text style={[styles.currentVal, RTL.text]}>
              {t('RHR_LABEL')}: {baselineRHR} {t('RHR_UNIT')}
            </Text>
          )}
        </View>

        {/* ── Server ──────────────────────────────────────────────── */}
        <SectionHeader label={t('SETTINGS_SERVER_SECTION')} />
        <View style={styles.card}>
          <View style={[styles.serverRow, RTL.row]}>
            <View style={{ flex: 1 }}>
              {serverStatus === 'ok' && (
                <Text style={[styles.statusOk, RTL.text]}>{t('SETTINGS_SERVER_STATUS_OK')}</Text>
              )}
              {serverStatus === 'error' && (
                <Text style={[styles.statusErr, RTL.text]}>{t('SETTINGS_SERVER_STATUS_ERR')}</Text>
              )}
              {(!serverStatus || serverStatus === 'checking') && (
                <Text style={[styles.fieldLabel, RTL.text]}>192.168.1.201:8000</Text>
              )}
            </View>
            <TouchableOpacity
              style={[styles.saveBtn, serverStatus === 'checking' && styles.saveBtnDisabled]}
              onPress={handleCheckServer}
              disabled={serverStatus === 'checking'}
              accessibilityRole="button"
            >
              {serverStatus === 'checking'
                ? <ActivityIndicator color="#fff" size="small" />
                : <Text style={styles.saveBtnText}>{t('SETTINGS_SERVER_CHECK_BTN')}</Text>
              }
            </TouchableOpacity>
          </View>
        </View>

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

  scroll:        { flex: 1 },
  scrollContent: { padding: SPACING.md },

  sectionHeader: {
    fontSize:     FONT.xs,
    fontWeight:   '700',
    color:        COLORS.textSecondary,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginTop:    SPACING.md,
    marginBottom: SPACING.xs,
    marginStart:  SPACING.xs,
  },

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

  fieldLabel: { fontSize: FONT.sm, color: COLORS.textSecondary, marginBottom: SPACING.xs },

  textInput: {
    borderWidth:     1,
    borderColor:     COLORS.border,
    borderRadius:    RADIUS.sm,
    paddingHorizontal: SPACING.sm,
    paddingVertical: SPACING.xs,
    fontSize:        FONT.md,
    color:           COLORS.text,
    backgroundColor: '#FAFAFA',
  },

  inputRow:  { alignItems: 'center', gap: SPACING.sm },
  serverRow: { alignItems: 'center' },

  weekRow: { marginTop: SPACING.xs },
  weekChip: {
    width:           40,
    height:          40,
    borderRadius:    20,
    borderWidth:     1,
    borderColor:     COLORS.border,
    justifyContent:  'center',
    alignItems:      'center',
    marginEnd:       SPACING.xs,
    backgroundColor: '#fff',
  },
  weekChipActive:     { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  weekChipText:       { fontSize: FONT.sm, color: COLORS.textSecondary, fontWeight: '600' },
  weekChipTextActive: { color: '#fff' },

  saveBtn: {
    backgroundColor: COLORS.primary,
    borderRadius:    RADIUS.sm,
    paddingVertical: SPACING.xs,
    paddingHorizontal: SPACING.sm,
    alignItems:      'center',
    justifyContent:  'center',
    minWidth:        90,
  },
  saveBtnDisabled: { backgroundColor: COLORS.textDisabled },
  saveBtnText:     { color: '#fff', fontSize: FONT.sm, fontWeight: '700' },

  statusOk:   { fontSize: FONT.sm, color: '#059669', fontWeight: '600' },
  statusErr:  { fontSize: FONT.sm, color: COLORS.danger, fontWeight: '600' },
  currentVal: { fontSize: FONT.xs, color: COLORS.textSecondary, marginTop: SPACING.xs },
});
