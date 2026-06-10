// @flow
/**
 * AppNavigator — Bottom-tab navigation for Lumen Health.
 * Tabs: Dashboard | Coach | SOS | History | Settings
 */

import React from 'react';
import { Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import DashboardScreen from '../screens/DashboardScreen';
import CoachScreen     from '../screens/CoachScreen';
import SOSScreen       from '../screens/SOSScreen';
import HistoryScreen   from '../screens/HistoryScreen';
import SettingsScreen  from '../screens/SettingsScreen';

import { COLORS } from '../components/tokens';
import { t }      from '../utils/i18n';

const Tab = createBottomTabNavigator();

function TabIcon({ emoji, focused }) {
  return (
    <Text style={{ fontSize: focused ? 26 : 22, opacity: focused ? 1 : 0.6 }}>
      {emoji}
    </Text>
  );
}

export default function AppNavigator() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown:          false,
        tabBarActiveTintColor:   COLORS.primary,
        tabBarInactiveTintColor: '#888',
        tabBarStyle: {
          backgroundColor: '#fff',
          borderTopWidth:  1,
          borderTopColor:  '#eee',
          paddingBottom:   6,
          paddingTop:      4,
          height:          60,
        },
        tabBarLabelStyle: {
          fontSize:   11,
          fontWeight: '600',
        },
      }}
    >
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarLabel: t('TAB_DASHBOARD'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="🏠" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Coach"
        component={CoachScreen}
        options={{
          tabBarLabel: t('TAB_COACH'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="💬" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="SOS"
        component={SOSScreen}
        options={{
          tabBarLabel: t('TAB_SOS'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="🆘" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="History"
        component={HistoryScreen}
        options={{
          tabBarLabel: t('TAB_HISTORY'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="📊" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarLabel: t('TAB_SETTINGS'),
          tabBarIcon:  ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}
