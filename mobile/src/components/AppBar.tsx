/**
 * `AppBar` — the fixed top bar (DESIGN.md §Components). Shows the EBADS brand (or a screen
 * title) and the live online/offline pill. The connectivity state is read from context so the
 * bar is always truthful about the app's mode.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { useConnectivity } from '../state/ConnectivityContext';
import { colors, spacing } from '../theme';
import { AppText } from './AppText';
import { StatusPill } from './StatusPill';

export function AppBar({ title }: { title?: string }): React.ReactElement {
  const { online } = useConnectivity();
  return (
    <View style={styles.bar}>
      <View style={styles.brand}>
        <MaterialIcons name="emergency" size={24} color={colors.clinicalTeal} />
        <AppText variant="headlineMd" color="clinicalTeal">
          {title ?? 'EBADS'}
        </AppText>
      </View>
      <StatusPill online={online} />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 56,
    paddingHorizontal: spacing.marginMobile,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surfaceContainer,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 8, flexShrink: 1 },
});
