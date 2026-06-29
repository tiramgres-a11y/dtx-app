// @flow
/**
 * UserContext — global user config shared across all screens.
 * Stores: userId, currentWeek, currentDay, baselineRHR, programStartDate.
 *
 * The program week/day are computed CLIENT-SIDE from a locally-persisted
 * start date (instant, offline-resilient). The backend remains the source of
 * truth and refreshes the cache in the background — so a cold-starting server
 * never resets the counter to day 1.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

import { fetchUserState } from '../api/endpoints';
import { computeWeek, computeDay } from '../utils/programDay';
import * as localStore from '../services/localStore';

const UserContext = createContext(null);

// Single personal user — fixed identifier (no multi-user auth needed).
const USER_ID = 'user-demo-001';

export function UserProvider({ children }) {
  const [userId]                                = useState(USER_ID);
  const [programStartDate, setProgramStartDate] = useState(null);
  const [currentWeek,      setCurrentWeek]      = useState(1);
  const [currentDay,       setCurrentDay]       = useState(1);
  const [baselineRHR,      setBaselineRHR]      = useState(null);

  // Apply a start date: recompute week/day locally and persist to the device.
  const applyProgramStart = useCallback((startDate) => {
    if (!startDate) return;
    setProgramStartDate(startDate);
    setCurrentWeek(computeWeek(startDate));
    setCurrentDay(computeDay(startDate));
    localStore.setProgramStart(startDate);
  }, []);

  // 1) Instant: load the locally-cached start date and compute the day offline.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const cached = await localStore.getProgramStart();
      if (!cancelled && cached) {
        setProgramStartDate(cached);
        setCurrentWeek(computeWeek(cached));
        setCurrentDay(computeDay(cached));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // 2) Background: refresh from the backend (source of truth) and re-cache.
  const refreshUserState = useCallback(async () => {
    try {
      const state = await fetchUserState(USER_ID);
      if (state?.program_start_date) {
        applyProgramStart(state.program_start_date);
      }
      if (state?.baseline_rhr != null) setBaselineRHR(state.baseline_rhr);
    } catch (_err) {
      // Offline / cold start — keep the locally-computed values.
    }
  }, [applyProgramStart]);

  useEffect(() => { refreshUserState(); }, [refreshUserState]);

  return (
    <UserContext.Provider value={{
      userId,
      currentWeek,      setCurrentWeek,
      currentDay,
      baselineRHR,      setBaselineRHR,
      programStartDate,
      applyProgramStart,
      refreshUserState,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used inside <UserProvider>');
  return ctx;
}
