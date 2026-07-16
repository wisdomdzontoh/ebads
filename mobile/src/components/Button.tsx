/**
 * `Button` — the three button roles from the design system (DESIGN.md §Buttons): `primary`
 * (solid clinical-teal), `secondary` (white with outline), and `danger` (solid critical-red).
 * Minimum 44px hit area, 12px radius, optional leading icon, and a disabled/loading state used
 * while an allocation request is in flight.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, radius } from '../theme';
import { AppText } from './AppText';

type Variant = 'primary' | 'secondary' | 'danger';

interface ButtonProps {
  label: string;
  onPress: () => void;
  variant?: Variant;
  icon?: keyof typeof MaterialIcons.glyphMap;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}

const BG: Record<Variant, string> = {
  primary: colors.clinicalTeal,
  secondary: colors.surfaceContainerLowest,
  danger: colors.criticalRed,
};

const FG: Record<Variant, string> = {
  primary: colors.onPrimary,
  secondary: colors.slate900,
  danger: colors.onError,
};

export function Button({
  label,
  onPress,
  variant = 'primary',
  icon,
  disabled = false,
  loading = false,
  style,
}: ButtonProps): React.ReactElement {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.base,
        {
          backgroundColor: BG[variant],
          borderWidth: variant === 'secondary' ? 1 : 0,
          borderColor: colors.outlineVariant,
          opacity: isDisabled ? 0.5 : pressed ? 0.9 : 1,
          transform: [{ scale: pressed && !isDisabled ? 0.98 : 1 }],
        },
        style,
      ]}
    >
      <View style={styles.content}>
        {loading ? (
          <ActivityIndicator color={FG[variant]} size="small" />
        ) : (
          <>
            {icon ? <MaterialIcons name={icon} size={20} color={FG[variant]} /> : null}
            <AppText variant="bodySm" color={FG[variant]}>
              {label}
            </AppText>
          </>
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 44,
    borderRadius: radius.control,
    paddingHorizontal: 16,
    justifyContent: 'center',
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
});
