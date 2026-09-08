/**
 * Root stack — wraps the tab bar (`RootTabs`) so `Notifications` can be reached from
 * anywhere (a bell icon in `AppBar`, or tapping an OS notification — `App.tsx`'s response
 * listener navigates here by name) without being a permanent 5th tab. Presented as a modal:
 * it's a browsable history layered over whatever tab the dispatcher was already on, not a
 * primary destination they'd sit in.
 */

import type { NavigatorScreenParams } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { NotificationsScreen } from '../screens/NotificationsScreen';
import { RootTabs, type RootTabParamList } from './RootTabs';

export type RootStackParamList = {
  MainTabs: NavigatorScreenParams<RootTabParamList> | undefined;
  Notifications: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator(): React.ReactElement {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MainTabs" component={RootTabs} />
      <Stack.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{ presentation: 'modal' }}
      />
    </Stack.Navigator>
  );
}
