// @flow
/**
 * localStore.js — tiny on-device persistence using expo-file-system.
 *
 * Persists the program start date so the program day/week survive app
 * restarts and are available instantly on launch — independent of the
 * (cold-starting) backend. The backend remains the source of truth and
 * refreshes this cache in the background.
 */

let FileSystem = null;
try {
  FileSystem = require('expo-file-system');
} catch (_) { /* unavailable (e.g. web) — fall back to no-op */ }

const _FILE = FileSystem ? `${FileSystem.documentDirectory}lumen_state.json` : null;

async function _readAll() {
  if (!FileSystem || !_FILE) return {};
  try {
    const info = await FileSystem.getInfoAsync(_FILE);
    if (!info.exists) return {};
    const raw = await FileSystem.readAsStringAsync(_FILE);
    return JSON.parse(raw) || {};
  } catch (_err) {
    return {};
  }
}

async function _writeAll(obj) {
  if (!FileSystem || !_FILE) return;
  try {
    await FileSystem.writeAsStringAsync(_FILE, JSON.stringify(obj));
  } catch (_err) { /* best-effort */ }
}

/** Returns the cached program start date (YYYY-MM-DD) or null. */
export async function getProgramStart() {
  const data = await _readAll();
  return data.program_start_date || null;
}

/** Persist the program start date locally. */
export async function setProgramStart(date) {
  const data = await _readAll();
  data.program_start_date = date;
  await _writeAll(data);
}
