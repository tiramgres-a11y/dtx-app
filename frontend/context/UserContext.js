// @flow
/**
 * UserContext — global user config shared across all screens.
 * Stores: userId, currentWeek, baselineRHR, programStartDate.
 *
 * currentWeek is NOT hardcoded — on launch it is fetched from the backend,
 * which computes it live from the stored program start date so the week
 * advances on its own as the days pass.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

import { fetchUserState } from '../api/endpoints';

const UserContext = createContext(null);

// Single personal user — fixed identifier (no multi-user auth needed).
const USER_ID = 'user-demo-001';

export function UserProvider({ children }) {
  const [userId]                              = useState(USER_ID);
  const [currentWeek,     setCurrentWeek]     = useState(1);
  const [baselineRHR,     setBaselineRHR]     = useState(null);
  const [programStartDate, setProgramStartDate] = useState(null);

  // Pull the live program state (computed week + start date) from the backend.
  const refreshUserState = useCallback(async () => {
    try {
      const state = await fetchUserState(USER_ID);
      if (state?.current_week)        setCurrentWeek(state.current_week);
      if (state?.program_start_date)  setProgramStartDate(state.program_start_date);
      if (state?.baseline_rhr != null) setBaselineRHR(state.baseline_rhr);
    } catch (_err) {
      // Offline / cold start — keep whatever we have; user can retry.
    }
  }, []);

  useEffect(() => { refreshUserState(); }, [refreshUserState]);

  return (
    <UserContext.Provider value={{
      userId,
      currentWeek,      setCurrentWeek,
      baselineRHR,      setBaselineRHR,
      programStartDate, setProgramStartDate,
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
