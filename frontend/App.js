// @flow
/**
 * App.js — Lumen Health
 * Root entry point for Expo.
 *
 * Bootstraps:
 *   1. RTL layout (I18nManager.forceRTL via tokens.js import)
 *   2. Axios fallback handler → setSensorActive(false) on network failure
 *   3. React Navigation (NavigationContainer + bottom tabs)
 *   4. UserContext — shared userId, currentWeek, baselineRHR
 */

import React, { useCallback } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';

// Bootstrap RTL (tokens.js calls I18nManager.forceRTL(true) at module load)
import './components/tokens';

// Axios client — register fallback before any API call
import { setFallbackHandler } from './api/client';

// User context
import { UserProvider } from './context/UserContext';

// Navigation
import AppNavigator from './navigation/AppNavigator';

export default function App() {
  // Wire network fallback: 5xx / timeout → components handle gracefully
  const handleNetworkFallback = useCallback(({ errorKey }) => {
    console.warn('[Lumen Health] Network fallback triggered:', errorKey);
  }, []);

  setFallbackHandler(handleNetworkFallback);

  return (
    <SafeAreaProvider>
      <UserProvider>
        <NavigationContainer>
          <StatusBar style="dark" />
          <AppNavigator />
        </NavigationContainer>
      </UserProvider>
    </SafeAreaProvider>
  );
}
