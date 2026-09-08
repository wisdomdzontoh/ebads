/**
 * `Screen` — the standard page scaffold every tab renders inside.
 *
 * Composes the safe-area top inset, the `AppBar`, the `OfflineBanner` (shown automatically
 * whenever the device is offline, docs/05 §3), and a scrollable content canvas with the
 * design's 12px margins. Screens just pass their content and an optional title.
 *
 * Wraps the content in `KeyboardAvoidingView` (iOS: `padding`, offset by the bar's own
 * height so it lifts exactly clear of the keyboard, not further) — without it, a `TextInput`
 * near the bottom of a form (e.g. Settings' change-password fields) is hidden behind the
 * keyboard the moment it's focused, with no way to see what's being typed. Android instead
 * relies on `android.softwareKeyboardLayoutMode: "resize"` (app.json) — the OS resizes the
 * window itself, which is the more reliable of the two platforms' approaches; stacking
 * `KeyboardAvoidingView` on top of that would double-compensate.
 */

import React from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useConnectivity } from '../state/ConnectivityContext';
import { colors, spacing } from '../theme';
import { AppBar, APP_BAR_HEIGHT } from './AppBar';
import { OfflineBanner } from './OfflineBanner';

interface ScreenProps {
  scroll?: boolean;
  children: React.ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Screen({ scroll = true, children, contentStyle }: ScreenProps): React.ReactElement {
  const { online } = useConnectivity();
  const insets = useSafeAreaInsets();

  return (
    <View style={styles.root}>
      <View style={{ paddingTop: insets.top }}>
        <AppBar />
      </View>
      {!online ? <OfflineBanner /> : null}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={insets.top + APP_BAR_HEIGHT}
      >
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
      </KeyboardAvoidingView>
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
