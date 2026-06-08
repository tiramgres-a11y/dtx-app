// @flow
/**
 * client.js — Centralised Axios HTTP client (Worker 2 / Frontend Manager)
 *
 * ARCHITECTURE RULES (per ROADMAP.md):
 *   ✓ No clinical logic, no OARS decisions, no Hebrew string literals
 *   ✓ Error messages are locale-key references only (resolved via locales/he.json)
 *   ✓ UI state mutation is injected via setFallbackHandler() — never imported here
 *   ✓ This module is the single network gateway; all endpoints go through it
 *
 * Fallback contract:
 *   On 5xx or network timeout the client fires the registered fallbackHandler.
 *   The handler receives { errorKey, statusCode } and is responsible for calling
 *   setSensorActive(false) on the DashboardScreen — keeping UI logic out of here.
 *
 * Usage:
 *   import { setFallbackHandler, apiClient } from './client';
 *   setFallbackHandler(({ errorKey }) => setSensorActive(false));
 */

'use strict';

let axios;
try {
  axios = require('axios');
  if (axios.default) axios = axios.default; // handle ESM interop
} catch (_) {
  // Injected by tests via setAxios()
}

// ---------------------------------------------------------------------------
// Error-key map — all user-visible strings are keys into locales/he.json
// ---------------------------------------------------------------------------
const ERROR_KEYS = {
  TIMEOUT:    'NET_ERROR_TIMEOUT',
  SERVER:     'NET_ERROR_SERVER',
  E400:       'NET_ERROR_CLIENT_400',
  E401:       'NET_ERROR_CLIENT_401',
  E403:       'NET_ERROR_CLIENT_403',
  E404:       'NET_ERROR_CLIENT_404',
  E422:       'NET_ERROR_CLIENT_422',
  UNKNOWN:    'NET_ERROR_UNKNOWN',
  FALLBACK:   'NET_FALLBACK_ACTIVATED',
};

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------
let _axiosInstance   = null;   // created lazily or after setAxios()
let _fallbackHandler = null;   // injected by DashboardScreen / App bootstrap
let _axiosLib        = axios;  // replaceable by tests

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
// Base URL resolution priority:
//   1. EXPO_PUBLIC_API_URL — set in frontend/.env (production Render URL)
//   2. DEV_API_URL         — optional override for local dev (rarely needed)
//   3. http://10.0.2.2:8000 — Android emulator loopback to host machine
//
// EXPO_PUBLIC_* variables are inlined into the bundle at Expo build time.
// They are read at module-evaluation time, so the resolved value is baked in
// for managed-workflow builds (EAS Build / expo export).
//
// For local physical-device dev: set EXPO_PUBLIC_API_URL=http://<LAN_IP>:8000
// in frontend/.env — this file is gitignored and never committed.
const BACKEND_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  process.env.DEV_API_URL          ||
  'http://10.0.2.2:8000';

const DEFAULT_CONFIG = {
  baseURL:         BACKEND_URL,
  timeout:         10000,                     // 10 000 ms — Render free tier cold-starts ~5s
  headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Accept':       'application/json',
    'Accept-Charset': 'utf-8',
  },
};

// ---------------------------------------------------------------------------
// Fallback signal — fires on 5xx / network error; UI side calls setSensorActive(false)
// ---------------------------------------------------------------------------

/**
 * Register the global fallback handler.
 * Called once at app bootstrap (e.g. inside App.js or DashboardScreen).
 *
 * @param {function({ errorKey: string, statusCode: number|null }): void} handler
 */
function setFallbackHandler(handler) {
  if (typeof handler !== 'function') {
    throw new TypeError('setFallbackHandler: handler must be a function');
  }
  _fallbackHandler = handler;
}

function _triggerFallback(errorKey, statusCode = null) {
  if (typeof _fallbackHandler === 'function') {
    _fallbackHandler({ errorKey, statusCode });
  }
}

// ---------------------------------------------------------------------------
// Error classification
// ---------------------------------------------------------------------------

/**
 * Map an Axios error to a locale error-key and decide whether to fire fallback.
 * Returns { errorKey, statusCode, triggerFallback }.
 */
function classifyError(error) {
  // Network error / no response (timeout, DNS failure, ECONNREFUSED …)
  if (!error.response) {
    const isTimeout =
      error.code === 'ECONNABORTED' ||
      error.code === 'ETIMEDOUT'    ||
      (error.message && error.message.toLowerCase().includes('timeout'));

    return {
      errorKey:        isTimeout ? ERROR_KEYS.TIMEOUT : ERROR_KEYS.UNKNOWN,
      statusCode:      null,
      triggerFallback: true,     // no connection → switch to manual mode
    };
  }

  const status = error.response.status;

  if (status >= 500) {
    return { errorKey: ERROR_KEYS.SERVER,  statusCode: status, triggerFallback: true  };
  }
  if (status === 400) {
    return { errorKey: ERROR_KEYS.E400,    statusCode: status, triggerFallback: false };
  }
  if (status === 401) {
    return { errorKey: ERROR_KEYS.E401,    statusCode: status, triggerFallback: false };
  }
  if (status === 403) {
    return { errorKey: ERROR_KEYS.E403,    statusCode: status, triggerFallback: false };
  }
  if (status === 404) {
    return { errorKey: ERROR_KEYS.E404,    statusCode: status, triggerFallback: false };
  }
  if (status === 422) {
    return { errorKey: ERROR_KEYS.E422,    statusCode: status, triggerFallback: false };
  }

  // Any other 4xx
  return { errorKey: ERROR_KEYS.UNKNOWN,   statusCode: status, triggerFallback: false };
}

// ---------------------------------------------------------------------------
// Interceptor setup — extracted so it can be applied to any instance
// ---------------------------------------------------------------------------

/**
 * Attach the Lumen Health response interceptors to an Axios instance.
 * Called by both _getInstance() (factory path) and setInstance() (inject path).
 * @param {import('axios').AxiosInstance} instance
 */
function _attachInterceptors(instance) {
  instance.interceptors.response.use(
    // Success path — pass through untouched
    (response) => response,

    // Error path — classify, optionally fire fallback, always re-throw
    (error) => {
      const { errorKey, statusCode, triggerFallback } = classifyError(error);

      // Attach classification metadata so callers can inspect it
      error._dtx = { errorKey, statusCode };

      if (triggerFallback) {
        _triggerFallback(errorKey, statusCode);
      }

      return Promise.reject(error);
    },
  );
}

// ---------------------------------------------------------------------------
// Instance factory
// ---------------------------------------------------------------------------

/**
 * Build (or return cached) Axios instance with interceptors attached.
 * @returns {import('axios').AxiosInstance}
 */
function _getInstance() {
  if (_axiosInstance) return _axiosInstance;
  if (!_axiosLib) throw new Error('Axios not available. Call setAxios() before use.');

  const instance = _axiosLib.create(DEFAULT_CONFIG);
  _attachInterceptors(instance);

  _axiosInstance = instance;
  return instance;
}

// ---------------------------------------------------------------------------
// Test helpers — allow replacing axios and resetting module state
// ---------------------------------------------------------------------------

/** Inject a mock axios library (used in test_network.js). */
function setAxios(lib) {
  _axiosLib      = lib;
  _axiosInstance = null; // force re-creation with new lib
}

/**
 * Directly inject a pre-configured Axios instance (e.g. one wrapped with
 * MockAdapter). Because _getInstance() returns _axiosInstance when set, all
 * callers — including endpoints.js — will use this instance immediately.
 * @param {import('axios').AxiosInstance} instance
 */
function setInstance(instance) {
  _attachInterceptors(instance); // ensure interceptors are present on injected instances
  _axiosInstance = instance;
}

/** Reset all module state between tests. */
function _reset() {
  _axiosInstance   = null;
  _fallbackHandler = null;
  // Leave _axiosLib intact — tests set it once before reset
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
module.exports = {
  // Primary API — used by endpoints.js
  getInstance:        _getInstance,

  // Bootstrap
  setFallbackHandler,

  // Test utilities
  setAxios,
  setInstance,
  _reset,
  classifyError,
  ERROR_KEYS,
  DEFAULT_CONFIG,
};
