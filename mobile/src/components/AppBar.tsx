/**
 * `AppBar` — the slim top strip every screen renders under. Shows only the live online/offline
 * pill (docs/05 §3 truthfulness requirement) — no icon, no title text. The EBADS mark lives
 * only on launch/onboarding; per-screen titles took vertical space away from map/list/card
 * content without adding information the tab bar's own label doesn't already give, so both were
 * dropped to leave more room for the screen itself (facility list, history, dispatch sheet).
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { useConnectivity } from '../state/ConnectivityContext';
import { colors, spacing } from '../theme';
import { StatusPill } from './StatusPill';

export const APP_BAR_HEIGHT = 34;

export function AppBar(): React.ReactElement {
  const { online } = useConnectivity();
  return (
    <View style={styles.bar}>
      <StatusPill online={online} />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: APP_BAR_HEIGHT,
    paddingHorizontal: spacing.marginMobile,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    backgroundColor: colors.surfaceContainer,
  },
});
