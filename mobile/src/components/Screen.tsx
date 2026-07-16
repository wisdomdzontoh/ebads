/**
 * `Screen` — the standard page scaffold every tab renders inside.
 *
 * Composes the safe-area top inset, the `AppBar`, the `OfflineBanner` (shown automatically
 * whenever the device is offline, docs/05 §3), and a scrollable content canvas with the
 * design's 12px margins. Screens just pass their content and an optional title.
 */

import React from 'react';
import { ScrollView, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useConnectivity } from '../state/ConnectivityContext';
import { colors, spacing } from '../theme';
import { AppBar } from './AppBar';
import { OfflineBanner } from './OfflineBanner';

interface ScreenProps {
  title?: string;
  scroll?: boolean;
  children: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Screen({
  title,
  scroll = true,
  children,
  contentStyle,
}: ScreenProps): React.ReactElement {
  const { online } = useConnectivity();
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.root}>
      <View style={{ paddingTop: insets.top }}>
        <AppBar title={title} />
      </View>
      {!online ? <OfflineBanner /> : null}
      {scroll ? (
        <ScrollView
          contentContainerStyle={[styles.content, contentStyle]}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.flex, contentStyle]}>{children}</View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: spacing.marginMobile,
    paddingTop: spacing.sectionGap,
    paddingBottom: 120,
    gap: spacing.sectionGap,
  },
});
