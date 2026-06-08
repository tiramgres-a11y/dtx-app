// @flow
/**
 * MilestoneChecklist
 * Manual-mode sub-component: checkboxes for physical milestones.
 * Each row is RTL — checkbox on left (start), label on right (end) in LTR terms,
 * but visually Hebrew text is on the right and checkbox is on the left
 * because I18nManager.forceRTL(true) mirrors the layout automatically.
 * All label strings sourced from he.json.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { t } from '../utils/i18n';
import { RTL, COLORS, FONT, SPACING, RADIUS } from './tokens';

const MILESTONES = [
  { key: 'MANUAL_MILESTONE_WALK',     id: 'walk'     },
  { key: 'MANUAL_MILESTONE_STAIRS',   id: 'stairs'   },
  { key: 'MANUAL_MILESTONE_STRETCH',  id: 'stretch'  },
  { key: 'MANUAL_MILESTONE_STRENGTH', id: 'strength' },
];

export default function MilestoneChecklist({ checked, onToggle }) {
  return (
    <View style={styles.wrapper}>
      <Text style={[styles.sectionLabel, RTL.text]}>{t('MANUAL_MILESTONES_LABEL')}</Text>
      {MILESTONES.map(({ key, id }) => {
        const isChecked = checked.includes(id);
        return (
          <TouchableOpacity
            key={id}
            style={[styles.row, RTL.row]}
            onPress={() => onToggle(id)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: isChecked }}
            accessibilityLabel={t(key)}
            activeOpacity={0.7}
          >
            {/* Checkbox box — on the leading (right in RTL) edge */}
            <View style={[styles.checkbox, isChecked && styles.checkboxChecked]}>
              {isChecked && <Text style={styles.checkMark}>✓</Text>}
            </View>
            <Text style={[styles.label, RTL.text, isChecked && styles.labelChecked]}>
              {t(key)}
            </Text>
          </TouchableOpacity>
        );
      })}
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
  row: {
    alignItems: 'center',
    paddingVertical: SPACING.xs,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: RADIUS.sm,
    borderWidth: 2,
    borderColor: COLORS.checkboxOff,
    backgroundColor: COLORS.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginEnd: SPACING.sm,
    flexShrink: 0,
  },
  checkboxChecked: {
    backgroundColor: COLORS.checkboxOn,
    borderColor: COLORS.checkboxOn,
  },
  checkMark: {
    color: COLORS.surface,
    fontSize: FONT.xs,
    fontWeight: '700',
    lineHeight: 16,
  },
  label: {
    flex: 1,
    fontSize: FONT.md,
    color: COLORS.textPrimary,
  },
  labelChecked: {
    color: COLORS.textSecondary,
    textDecorationLine: 'line-through',
  },
});
