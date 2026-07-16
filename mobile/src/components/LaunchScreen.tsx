/**
 * `LaunchScreen` — the in-app loading surface shown while fonts and persisted settings load.
 *
 * Shows the official EBADS logo centred on white, mirroring the native splash so launch feels
 * seamless (and giving web — which has no native splash — the same branded loading moment).
 * The logo appears here and in onboarding only; in-app surfaces use the text brand.
 */

import React from 'react';
import { ActivityIndicator, Image, StyleSheet, View } from 'react-native';

import { colors } from '../theme';

export function LaunchScreen(): React.ReactElement {
  return (
    <View style={styles.root}>
      <Image
        source={require('../../assets/ebads_logo.png')}
        style={styles.logo}
        resizeMode="contain"
        accessibilityLabel="EBADS — Emergency Bed Allocation Decision Support"
      />
      <ActivityIndicator color={colors.clinicalTeal} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 28,
    // The logo artwork sits on pure white; match it so the mark blends seamlessly.
    backgroundColor: '#ffffff',
  },
  logo: { width: 220, height: 220 },
});
