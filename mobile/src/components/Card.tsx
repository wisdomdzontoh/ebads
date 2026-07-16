/**
 * `Card` — the white, 16px-radius container that "pulls forward" from the tonal surface
 * (DESIGN.md §Elevation, §Shapes). Soft low-contrast shadow, consistent padding. Screens pass
 * a `style` override for tinted variants (e.g. the red-tint escalation card).
 */

import React from 'react';
import { StyleSheet, View, type ViewProps } from 'react-native';

import { colors, radius, shadow, spacing } from '../theme';

export function Card({ style, children, ...rest }: ViewProps): React.ReactElement {
  return (
    <View {...rest} style={[styles.card, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surfaceContainerLowest,
    borderRadius: radius.card,
    padding: spacing.gutter,
    ...shadow.card,
  },
});
