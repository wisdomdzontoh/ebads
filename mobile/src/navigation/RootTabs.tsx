/**
 * Bottom-tab navigation (docs/05 §2): Dispatch, Map, History, Settings.
 *
 * The dispatcher surfaces. Each screen renders its own `AppBar` (headers are off here), so
 * this file only owns the tab bar styling — the active tab gets the secondary-container pill
 * treatment from the design, inactive tabs use muted on-surface-variant.
 *
 * Simulation is deliberately NOT a tab (Increment 1's RBAC retrofit): `/simulation/...` is
 * gated to `system_administrator` only (backend/app/db/migrations/versions/20260818_0005_auth_
 * rbac.py — "simulation" was never a docs/02 §2.2 resource; it was scoped to *a* role rather
 * than left open), and this app is dispatcher-only (docs/EBADS_PRD.md §2 — the web portal
 * covers the other three roles). Every request `SimulationScreen` makes would 403 for the only
 * role that ever signs into this app, so surfacing it as a live tab would show a permanently
 * broken feature, not a working one. The screen and its components are left in place (not
 * deleted) in case a research/admin build ever wants them; they are just unreachable from here.
 */

import { MaterialIcons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';

import { DispatchScreen } from '../screens/DispatchScreen';
import { FacilityMapScreen } from '../screens/FacilityMapScreen';
import { HistoryScreen } from '../screens/HistoryScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { colors, spacing } from '../theme';

export type RootTabParamList = {
  Dispatch: undefined;
  Map: undefined;
  History: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<RootTabParamList>();

const ICONS: Record<keyof RootTabParamList, keyof typeof MaterialIcons.glyphMap> = {
  Dispatch: 'assignment',
  Map: 'map',
  History: 'history',
  Settings: 'settings',
};

export function RootTabs(): React.ReactElement {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.clinicalTeal,
        tabBarInactiveTintColor: colors.onSurfaceVariant,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.outlineVariant,
          height: 64 + spacing.safeAreaBottom,
          paddingTop: 8,
          paddingBottom: spacing.safeAreaBottom,
        },
        tabBarLabelStyle: { fontFamily: 'IBMPlexSans_600SemiBold', fontSize: 11 },
        tabBarIcon: ({ color, size }) => (
          <MaterialIcons name={ICONS[route.name]} size={size} color={color} />
        ),
      })}
    >
      <Tab.Screen name="Dispatch" component={DispatchScreen} />
      <Tab.Screen name="Map" component={FacilityMapScreen} />
      <Tab.Screen name="History" component={HistoryScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
