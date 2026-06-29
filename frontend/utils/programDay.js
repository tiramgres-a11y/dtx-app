// @flow
/**
 * programDay.js — client-side program day/week computation.
 *
 * Mirrors the backend (db_service.compute_current_week / compute_program_day)
 * so the app can show the correct day instantly from a locally-stored start
 * date, without waiting on a (cold-starting) backend call.
 *
 *   day  1-7   -> week 1, day 8-14 -> week 2, … capped at week 13 / day 91.
 */

/** Whole days elapsed since the start date (local midnight to local midnight). */
function _daysSince(startDate) {
  if (!startDate) return 0;
  const start = new Date(`${startDate}T00:00:00`);
  if (isNaN(start.getTime())) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.floor((today.getTime() - start.getTime()) / 86400000);
}

/** Current program week (1-13) from a YYYY-MM-DD start date. */
export function computeWeek(startDate) {
  if (!startDate) return 1;
  const week = Math.floor(_daysSince(startDate) / 7) + 1;
  return Math.max(1, Math.min(13, week));
}

/** Current absolute program day (1-91) from a YYYY-MM-DD start date. */
export function computeDay(startDate) {
  if (!startDate) return 1;
  const day = _daysSince(startDate) + 1;
  return Math.max(1, Math.min(91, day));
}
