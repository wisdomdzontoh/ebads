/**
 * `InlineNotice` — an inline error/info banner rendered next to the action that failed.
 *
 * Used instead of `Alert.alert`, which is a silent no-op on react-native-web: an inline
 * notice is visible on every platform, persists until the user retries, and sits in the
 * user's line of sight (docs/05 §5 — failures are surfaced, never hidden).
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { colors, radius } from '../theme';
import { AppText } from './AppText';

type Tone = 'error' | 'info' | 'success';

const TONE_STYLE: Record<Tone, { bg: string; fg: string; icon: keyof typeof MaterialIcons.glyphMap }> = {
  error: { bg: colors.redTint, fg: colors.criticalRed, icon: 'error-outline' },
  info: { bg: colors.surfaceContainer, fg: colors.onSurfaceVariant, icon: 'info-outline' },
  success: { bg: colors.greenTint, fg: colors.standardGreen, icon: 'check-circle' },
};

export function InlineNotice({
  tone = 'error',
  title,
  message,
}: {
  tone?: Tone;
  title: string;
  message?: string;
}): React.ReactElement {
  const style = TONE_STYLE[tone];
  return (
    <View style={[styles.notice, { backgroundColor: style.bg }]} accessibilityRole="alert">
      <MaterialIcons name={style.icon} size={20} color={style.fg} />
      <View style={styles.text}>
        <AppText variant="headlineMd" style={{ color: style.fg }}>
          {title}
        </AppText>
        {message ? (
          <AppText variant="bodySm" color="onSurfaceVariant">
            {message}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  notice: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
    borderRadius: radius.control,
    padding: 14,
  },
  text: { flex: 1, gap: 2 },
});
