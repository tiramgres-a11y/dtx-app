// @flow
/**
 * UserContext — global user config shared across all screens.
 * Stores: userId, currentWeek, baselineRHR
 */

import React, { createContext, useContext, useState } from 'react';

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [userId,      setUserId]      = useState('user-demo-001');
  const [currentWeek, setCurrentWeek] = useState(6);
  const [baselineRHR, setBaselineRHR] = useState(null); // null = not set yet

  return (
    <UserContext.Provider value={{
      userId,      setUserId,
      currentWeek, setCurrentWeek,
      baselineRHR, setBaselineRHR,
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
