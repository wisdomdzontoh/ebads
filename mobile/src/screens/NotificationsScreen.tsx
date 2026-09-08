/**
 * Notifications — a browsable history of every in-app alert (recommendation, escalation,
 * revocation) the dispatcher has been shown, independent of whatever the OS notification tray
 * still holds. Reached via `AppBar`'s bell icon, or by tapping an OS notification itself
 * (`App.tsx`'s response listener navigates here by name — see its own docstring for why a
 * dedicated screen exists instead of just deep-linking straight past it). Tapping an entry
 * marks it read and navigates to where it's about (Dispatch, for every kind today).
 */

import { MaterialIcons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useCallback, useState } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '../components';
import type { RootStackParamList } from '../navigation/RootNavigator';
import {
  listNotifications,
  markAllNotificationsRead,
  type NotificationKind,
  type NotificationRecord,
} from '../services/notificationHistory';
import { colors, radius, spacing } from '../theme';

const KIND_ICON: Record<NotificationKind, keyof typeof MaterialIcons.glyphMap> = {
  recommendation: 'check-circle',
  escalation: 'error-outline',
  revocation: 'cancel',
  arrival: 'task-alt',
  other: 'notifications',
};

const KIND_COLOR: Record<NotificationKind, string> = {
  recommendation: colors.standardGreen,
  escalation: colors.urgentOrange,
  revocation: colors.criticalRed,
  arrival: colors.clinicalTeal,
  other: colors.slate400,
};

/** `2m ago` / `3h ago` / `5d ago` — coarse, not a live-ticking clock (this is a static history
 * list, not a countdown). */
function relativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function NotificationsScreen(): React.ReactElement {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [notifications, setNotifications] = useState<NotificationRecord[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Reload every time the screen gains focus (a new alert may have arrived since it was last
  // open), and mark everything read — opening the inbox is what "seeing" it means here, matching
  // the badge count on AppBar's bell, which reads the same unread total.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      void listNotifications()
        .then((rows) => {
          if (active) setNotifications(rows);
        })
        .catch(() => undefined)
        .finally(() => {
          if (active) setLoaded(true);
        });
      void markAllNotificationsRead();
      return () => {
        active = false;
      };
    }, []),
  );

  const openNotification = (record: NotificationRecord): void => {
    navigation.goBack();
    if (record.target) {
      navigation.navigate('MainTabs', { screen: record.target.screen });
    }
  };

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <AppText variant="headlineLg" color="slate900">
          Notifications
        </AppText>
        <Pressable
          onPress={() => navigation.goBack()}
          accessibilityRole="button"
          accessibilityLabel="Close notifications"
          hitSlop={10}
          style={styles.closeButton}
        >
          <MaterialIcons name="close" size={20} color={colors.slate900} />
        </Pressable>
      </View>

      {loaded && notifications.length === 0 ? (
        <View style={styles.empty}>
          <MaterialIcons name="notifications-none" size={40} color={colors.slate400} />
          <AppText variant="bodySm" color="onSurfaceVariant">
            Nothing yet — dispatch alerts will show up here.
          </AppText>
        </View>
      ) : (
        <FlatList
          data={notifications}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => openNotification(item)}
              accessibilityRole="button"
              accessibilityLabel={item.title}
              style={[styles.row, !item.read ? styles.rowUnread : null]}
            >
              <MaterialIcons name={KIND_ICON[item.kind]} size={22} color={KIND_COLOR[item.kind]} />
              <View style={styles.rowText}>
                <AppText variant="bodySm" color="slate900">
                  {item.title}
                </AppText>
                <AppText variant="dataSm" color="onSurfaceVariant" numberOfLines={2}>
                  {item.body}
                </AppText>
              </View>
              <AppText variant="dataSm" color="slate400">
                {relativeTime(item.createdAt)}
              </AppText>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface, paddingTop: 54 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.marginMobile,
    paddingBottom: spacing.sectionGap,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceContainer,
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, padding: 40 },
  listContent: { paddingHorizontal: spacing.marginMobile, paddingBottom: 40 },
  separator: { height: spacing.cardGap },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    padding: 14,
    borderRadius: radius.control,
    backgroundColor: colors.surfaceContainerLowest,
  },
  rowUnread: { backgroundColor: colors.greenTint },
  rowText: { flex: 1, gap: 2 },
});
