// @flow
/**
 * Lightweight i18n loader for React Native (no expo-localization dependency yet).
 * Reads strictly from /locales/he.json — Hebrew is the only supported locale.
 * Returns the raw string for a key, or a visible error sentinel so missing keys
 * are caught during development rather than silently rendering blank.
 *
 * Usage:  import { t } from '../utils/i18n';
 *         <Text>{t('DASHBOARD_TITLE')}</Text>
 */

import heJson from '../locales/he.json';

const LOCALE = heJson;

/**
 * Translate a key to its Hebrew string.
 * @param {string} key   - Key from locales/he.json
 * @param {Object} [vars] - Optional interpolation map: { COUNT: 5 } replaces {{COUNT}}
 * @returns {string}
 */
export function t(key, vars = {}) {
  const raw = LOCALE[key];
  if (raw === undefined) {
    // Loud sentinel — never silently swallow a missing key in development
    return `[MISSING:${key}]`;
  }
  // Simple {{VAR}} interpolation
  return Object.entries(vars).reduce(
    (str, [k, v]) => str.replace(new RegExp(`{{${k}}}`, 'g'), String(v)),
    raw,
  );
}

export default t;
