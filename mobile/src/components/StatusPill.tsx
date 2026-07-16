/**
 * `StatusPill` — the pill-shaped online/offline badge in the app bar (DESIGN.md §Shapes,
 * §Components). Green tint + pulsing dot when online; slate when offline. Pills are reserved
 * for status (never actions), distinguishing them from rectangular buttons.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { colors, radius } from '../theme';
import { AppText } from './AppText';

export function StatusPill({ online }: { online: boolean }): React.ReactElement {
  return (
    <View
      style={[
        styles.pill,
        {
          backgroundColor: online ? colors.greenTint : colors.surfaceContainerHigh,
          borderColor: online ? colors.standardGreen : colors.outlineVariant,
        },
      ]}
    >
      <View
        style={[styles.dot, { backgroundColor: online ? colors.standardGreen : colors.slate400 }]}
      />
      <AppText variant="label" color={online ? 'standardGreen' : 'onSurfaceVariant'}>
        {online ? 'ONLINE' : 'OFFLINE'}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
  },
  dot: { width: 8, height: 8, borderRadius: radius.pill },
});
