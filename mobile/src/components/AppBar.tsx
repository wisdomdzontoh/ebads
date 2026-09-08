/**
 * `AppBar` — the slim top strip every screen renders under. Shows the live online/offline pill
 * (docs/05 §3 truthfulness requirement) and a bell icon into the Notifications screen, badged
 * with the unread count. No icon/title beyond that — the EBADS mark lives only on
 * launch/onboarding; per-screen titles took vertical space away from map/list/card content
 * without adding information the tab bar's own label doesn't already give, so both were
 * dropped to leave more room for the screen itself.
 */

import { MaterialIcons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { RootStackParamList } from '../navigation/RootNavigator';
import { unreadNotificationCount } from '../services/notificationHistory';
import { useConnectivity } from '../state/ConnectivityContext';
import { colors, spacing } from '../theme';
import { AppText } from './AppText';
import { StatusPill } from './StatusPill';

export const APP_BAR_HEIGHT = 34;

/** How often to re-check the unread count while a screen sits idle — the same order of
 * magnitude as this app's other background polls (e.g. DispatchScreen's revocation check). */
const REFRESH_INTERVAL_MS = 15_000;

export function AppBar(): React.ReactElement {
  const { online } = useConnectivity();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [unread, setUnread] = useState(0);

  const refresh = useCallback(() => {
    void unreadNotificationCount()
      .then(setUnread)
      .catch(() => undefined);
  }, []);

  // Re-check whenever this screen (any tab — AppBar is rendered by every one of them) regains
  // focus, e.g. coming back from the Notifications screen having just read everything.
  useFocusEffect(refresh);

  useEffect(() => {
    const interval = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <View style={styles.bar}>
      <StatusPill online={online} />
      <Pressable
        onPress={() => navigation.navigate('Notifications')}
        accessibilityRole="button"
        accessibilityLabel={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
        hitSlop={8}
        style={styles.bell}
      >
        <MaterialIcons name="notifications-none" size={20} color={colors.slate900} />
        {unread > 0 ? (
          <View style={styles.badge}>
            <AppText variant="dataSm" color="onError" style={styles.badgeText}>
              {unread > 9 ? '9+' : unread}
            </AppText>
          </View>
        ) : null}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: APP_BAR_HEIGHT,
    paddingHorizontal: spacing.marginMobile,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surfaceContainer,
  },
  bell: { padding: 4 },
  badge: {
    position: 'absolute',
    top: 0,
    right: 0,
    minWidth: 15,
    height: 15,
    borderRadius: 8,
    paddingHorizontal: 3,
    backgroundColor: colors.criticalRed,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: { fontSize: 9, lineHeight: 11 },
});
