/**
 * `ConfirmDialog` — a centred, modal confirmation prompt for an action that shouldn't happen
 * by reflex (e.g. starting a new dispatch while the previous one is still held at a facility).
 * `Alert.alert` — React Native's usual quick-confirm — is a silent no-op on web (this app runs
 * there too, DispatchScreen's own submit-error handling already notes the same limitation), so
 * this renders real content in a `Modal` instead, which works identically on every platform.
 */

import React from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { colors, radius, shadow, spacing } from '../theme';
import { AppText } from './AppText';
import { Button } from './Button';

interface ConfirmDialogProps {
  visible: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Renders the confirm button in the `danger` variant instead of `primary`. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps): React.ReactElement {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <Pressable style={styles.backdrop} onPress={onCancel}>
        {/* Swallow taps on the card itself so they don't bubble to the backdrop's dismiss. */}
        <Pressable style={styles.card} onPress={() => undefined}>
          <AppText variant="headlineMd" color="slate900">
            {title}
          </AppText>
          <AppText variant="bodySm" color="onSurfaceVariant" style={styles.message}>
            {message}
          </AppText>
          <View style={styles.actions}>
            <Button label={cancelLabel} variant="secondary" onPress={onCancel} style={styles.action} />
            <Button
              label={confirmLabel}
              variant={destructive ? 'danger' : 'primary'}
              onPress={onConfirm}
              style={styles.action}
            />
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(16, 24, 38, 0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.gutter,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    backgroundColor: colors.surfaceContainerLowest,
    borderRadius: radius.card,
    padding: spacing.gutter,
    gap: 8,
    ...shadow.card,
  },
  message: { marginBottom: 8 },
  actions: { flexDirection: 'row', gap: 12, marginTop: 8 },
  action: { flex: 1 },
});
