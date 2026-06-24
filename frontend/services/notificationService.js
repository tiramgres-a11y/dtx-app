// @flow
/**
 * notificationService.js — Local scheduled notifications (Worker 2)
 *
 * Personal-use proactive nudges via on-device LOCAL notifications — no server,
 * no FCM, no push tokens. Covers the spec's time-based touchpoints:
 *   • Daily lesson reminder (morning)
 *   • Evening "engine shutdown" wind-down reminder
 *   • Friday meal-prep planning reminder
 *
 * All scheduling is idempotent: we cancel all existing scheduled notifications
 * and re-create them, so calling configure() repeatedly never duplicates.
 *
 * Hebrew strings come from locales/he.json via t().
 */

import { Platform } from 'react-native';

import { t } from '../utils/i18n';

// expo-notifications: safe import so the app never crashes if unavailable
let Notifications = null;
try {
  Notifications = require('expo-notifications');
} catch (_) { /* not available (e.g. web) */ }

const ANDROID_CHANNEL_ID = 'lumen-reminders';

// Reminder times (24h local). Adjust here if you want different defaults.
const DAILY_LESSON_HOUR   = 8;   // 08:00
const EVENING_HOUR        = 21;  // 21:00 — engine shutdown
const FRIDAY_PREP_HOUR    = 12;  // Friday 12:00
// expo-notifications weekday: 1=Sunday … 6=Friday … 7=Saturday
const FRIDAY_WEEKDAY      = 6;

/**
 * Ensure the Android notification channel exists.
 * No-op on iOS / when the module is unavailable.
 */
async function _ensureChannel() {
  if (!Notifications || Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    name: 'תזכורות Lumen Health',
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: null,
  });
}

/**
 * Request notification permission. Returns true if granted.
 */
export async function requestNotificationPermission() {
  if (!Notifications) return false;
  try {
    const { status: existing } = await Notifications.getPermissionsAsync();
    let status = existing;
    if (existing !== 'granted') {
      const req = await Notifications.requestPermissionsAsync();
      status = req.status;
    }
    return status === 'granted';
  } catch (_err) {
    return false;
  }
}

async function _schedule(hour, minute, title, body, weekday) {
  const trigger = { hour, minute, repeats: true, channelId: ANDROID_CHANNEL_ID };
  if (weekday != null) trigger.weekday = weekday;
  await Notifications.scheduleNotificationAsync({
    content: { title, body },
    trigger,
  });
}

/**
 * Configure all recurring reminders. Idempotent: clears and re-schedules.
 * Safe to call on every app launch. Returns true if reminders are active.
 */
export async function configureReminders() {
  if (!Notifications) return false;

  const granted = await requestNotificationPermission();
  if (!granted) return false;

  await _ensureChannel();

  // Clear any previously scheduled notifications to avoid duplicates
  try {
    await Notifications.cancelAllScheduledNotificationsAsync();
  } catch (_err) { /* ignore */ }

  try {
    await _schedule(
      DAILY_LESSON_HOUR, 0,
      t('NOTIF_LESSON_TITLE'), t('NOTIF_LESSON_BODY'),
    );
    await _schedule(
      EVENING_HOUR, 0,
      t('NOTIF_EVENING_TITLE'), t('NOTIF_EVENING_BODY'),
    );
    await _schedule(
      FRIDAY_PREP_HOUR, 0,
      t('NOTIF_PREP_TITLE'), t('NOTIF_PREP_BODY'),
      FRIDAY_WEEKDAY,
    );
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Cancel all scheduled reminders.
 */
export async function cancelReminders() {
  if (!Notifications) return;
  try {
    await Notifications.cancelAllScheduledNotificationsAsync();
  } catch (_err) { /* ignore */ }
}

export default { configureReminders, cancelReminders, requestNotificationPermission };
