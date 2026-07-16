/**
 * Shared onboarding step layout (docs/05, onboarding_* designs).
 *
 * A centred illustration glyph, a headline, a supporting paragraph, a primary action, and a
 * skip/secondary link — plus a step-progress bar. Each concrete step supplies its content.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React from 'react';
import { Image, Pressable, StyleSheet, View, type ImageSourcePropType } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText, Button } from '../../components';
import { colors, radius, spacing } from '../../theme';

export function StepProgress({ total, index }: { total: number; index: number }): React.ReactElement {
  return (
    <View style={styles.progress}>
      {Array.from({ length: total }).map((_, i) => (
        <View
          key={i}
          style={[
            styles.progressBar,
            { backgroundColor: i <= index ? colors.clinicalTeal : colors.outlineVariant },
          ]}
        />
      ))}
    </View>
  );
}

export function OnboardingStep({
  icon,
  logo,
  title,
  body,
  primaryLabel,
  onPrimary,
  primaryLoading,
  secondaryLabel,
  onSecondary,
  footer,
  progress,
}: {
  icon?: keyof typeof MaterialIcons.glyphMap;
  /** Official brand mark — used on the welcome step instead of a glyph. */
  logo?: ImageSourcePropType;
  title: string;
  body: string;
  primaryLabel: string;
  onPrimary: () => void;
  primaryLoading?: boolean;
  secondaryLabel?: string;
  onSecondary?: () => void;
  footer?: React.ReactNode;
  progress?: { total: number; index: number };
}): React.ReactElement {
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.root, { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 24 }]}>
      {progress ? <StepProgress total={progress.total} index={progress.index} /> : null}
      <View style={styles.body}>
        {logo ? (
          <Image
            source={logo}
            style={styles.logo}
            resizeMode="contain"
            accessibilityLabel="EBADS — Emergency Bed Allocation Decision Support"
          />
        ) : icon ? (
          <View style={styles.illustration}>
            <MaterialIcons name={icon} size={72} color={colors.clinicalTeal} />
          </View>
        ) : null}
        <AppText variant="display" color="slate900" style={styles.title}>
          {title}
        </AppText>
        <AppText variant="bodyLg" color="onSurfaceVariant" style={styles.paragraph}>
          {body}
        </AppText>
      </View>
      <View style={styles.actions}>
        {footer}
        <Button label={primaryLabel} onPress={onPrimary} loading={primaryLoading} icon="arrow-forward" />
        {secondaryLabel && onSecondary ? (
          <Pressable onPress={onSecondary} style={styles.secondary} hitSlop={8}>
            <AppText variant="bodySm" color="onSurfaceVariant">
              {secondaryLabel}
            </AppText>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    paddingHorizontal: spacing.gutter,
    backgroundColor: colors.surface,
    justifyContent: 'space-between',
  },
  progress: { flexDirection: 'row', gap: 8 },
  progressBar: { flex: 1, height: 4, borderRadius: radius.pill },
  body: { flex: 1, justifyContent: 'center', gap: 20 },
  illustration: {
    width: 140,
    height: 140,
    borderRadius: radius.card,
    backgroundColor: colors.surfaceContainerLowest,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'flex-start',
  },
  // The logo artwork sits on white; a white card keeps the mark crisp on the app surface.
  logo: {
    width: 180,
    height: 180,
    borderRadius: radius.card,
    backgroundColor: '#ffffff',
    alignSelf: 'flex-start',
  },
  title: { fontSize: 34, lineHeight: 38 },
  paragraph: {},
  actions: { gap: 16 },
  secondary: { alignItems: 'center', paddingVertical: 8 },
});
