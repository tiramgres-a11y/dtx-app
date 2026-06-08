// @flow
/**
 * SensorStatusBadge
 * RTL-aware pill indicator showing watch connection state.
 * Text sourced exclusively from locales/he.json.
 */

import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { t } from '../utils/i18n';
import { RTL, COLORS, FONT, RADIUS, SPACING } from './tokens';

export default function SensorStatusBadge({ isActive, onConnectPress }) {
  return (
    <View style={[styles.row, RTL.row]}>
      <View style={[styles.dot, isActive ? styles.dotActive : styles.dotInactive]} />
      <Text style={[styles.label, isActive ? styles.labelActive : styles.labelInactive]}>
        {isActive ? t('SENSOR_STATUS_ACTIVE') : t('SENSOR_STATUS_INACTIVE')}
      </Text>
      {!isActive && (
        <TouchableOpacity
          style={styles.cta}
          onPress={onConnectPress}
          accessibilityRole="button"
          accessibilityLabel={t('SENSOR_CONNECT_CTA')}
        >
          <Text style={styles.ctaText}>{t('SENSOR_CONNECT_CTA')}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    alignItems: 'center',
    paddingVertical: SPACING.xs,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginEnd: SPACING.xs,
  },
  dotActive: { backgroundColor: COLORS.success },
  dotInactive: { backgroundColor: COLORS.warning },
  label: {
    fontSize: FONT.sm,
    flex: 1,
  },
  labelActive: { color: COLORS.success },
  labelInactive: { color: COLORS.warning },
  cta: {
    backgroundColor: COLORS.primaryLight,
    paddingHorizontal: SPACING.sm,
    paddingVertical: SPACING.xxs,
    borderRadius: RADIUS.pill,
    marginStart: SPACING.sm,
  },
  ctaText: {
    color: COLORS.primary,
    fontSize: FONT.xs,
    fontWeight: '600',
  },
});
