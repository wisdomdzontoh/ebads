/**
 * Bottom-tab navigation (docs/05 §2): Dispatch, Map, Simulation, Settings.
 *
 * The four dispatcher surfaces. Each screen renders its own `AppBar` (headers are off here),
 * so this file only owns the tab bar styling — the active tab gets the secondary-container
 * pill treatment from the design, inactive tabs use muted on-surface-variant.
 */

import { MaterialIcons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';

import { DispatchScreen } from '../screens/DispatchScreen';
import { FacilityMapScreen } from '../screens/FacilityMapScreen';
import { SettingsScreen } from '../screens/SettingsScreen';
import { SimulationScreen } from '../screens/SimulationScreen';
import { colors, spacing } from '../theme';

export type RootTabParamList = {
  Dispatch: undefined;
  Map: undefined;
  Simulation: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<RootTabParamList>();

const ICONS: Record<keyof RootTabParamList, keyof typeof MaterialIcons.glyphMap> = {
  Dispatch: 'assignment',
  Map: 'map',
  Simulation: 'analytics',
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
      <Tab.Screen name="Simulation" component={SimulationScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
