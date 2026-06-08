// @flow
/**
 * SleepQuickTap
 * Manual-mode sub-component: horizontal row of tap buttons for sleep reporting.
 * All button labels sourced from he.json. Selected button is highlighted.
 * Layout is RTL — buttons flow right-to-left in reading order.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { t } from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';

const SLEEP_OPTIONS = [
  { key: 'MANUAL_SLEEP_BTN_4', value: 3.5 },
  { key: 'MANUAL_SLEEP_BTN_5', value: 4.5 },
  { key: 'MANUAL_SLEEP_BTN_6', value: 5.5 },
  { key: 'MANUAL_SLEEP_BTN_7', value: 6.5 },
  { key: 'MANUAL_SLEEP_BTN_8', value: 7.5 },
];

export default function SleepQuickTap({ selectedValue, onSelect }) {
  return (
    <View style={styles.wrapper}>
      <Text style={[styles.sectionLabel, RTL.text]}>{t('MANUAL_SLEEP_LABEL')}</Text>
      {/* ScrollView handles narrow screens without clipping */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={[styles.optionRow, RTL.row]}
      >
        {SLEEP_OPTIONS.map(({ key, value }) => {
          const isSelected = selectedValue === value;
          return (
            <TouchableOpacity
              key={key}
              style={[styles.btn, isSelected && styles.btnSelected]}
              onPress={() => onSelect(value)}
              accessibilityRole="radio"
              accessibilityState={{ checked: isSelected }}
              accessibilityLabel={t(key)}
            >
              <Text style={[styles.btnText, isSelected && styles.btnTextSelected]}>
                {t(key)}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginBottom: SPACING.md,
  },
  sectionLabel: {
    fontSize: FONT.sm,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: SPACING.xs,
  },
  optionRow: {
    gap: SPACING.xs,
    paddingBottom: SPACING.xxs,
  },
  btn: {
    paddingHorizontal: SPACING.sm,
    paddingVertical: SPACING.xs,
    borderRadius: RADIUS.pill,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  btnSelected: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  btnText: {
    fontSize: FONT.sm,
    color: COLORS.textSecondary,
    textAlign: 'center',
  },
  btnTextSelected: {
    color: COLORS.surface,
    fontWeight: '700',
  },
});
