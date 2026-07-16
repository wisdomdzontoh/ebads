/**
 * `AppText` — every piece of text in the app goes through here so the type scale and the
 * dual-font strategy are applied consistently (DESIGN.md §Typography). Pick a `variant` from
 * the design's type presets and an optional semantic `color` token; data-style variants
 * (`dataLg`/`dataSm`) render in IBM Plex Mono automatically.
 */

import React from 'react';
import { Text, type TextProps } from 'react-native';

import { colors, textStyles } from '../theme';
import type { ColorName, TypeName } from '../theme';

interface AppTextProps extends TextProps {
  variant?: TypeName;
  color?: ColorName | string;
}

export function AppText({
  variant = 'bodyLg',
  color = 'onSurface',
  style,
  ...rest
}: AppTextProps): React.ReactElement {
  const resolved = (colors as Record<string, string>)[color] ?? color;
  return <Text {...rest} style={[textStyles[variant], { color: resolved }, style]} />;
}
