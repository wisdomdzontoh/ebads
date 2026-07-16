/**
 * Typography presets — the design system's type scale as React Native text styles.
 *
 * Each preset pins a loaded font family (weight is baked into the family name, so we never
 * set fontWeight) plus size/line-height from DESIGN.md §Typography. The dual-font split is
 * intentional: `display`/`headline`/`body`/`overline`/`label` use IBM Plex Sans (interface
 * text); `dataLg`/`dataSm` use IBM Plex Mono for metrics, coordinates, and scores so numeric
 * data reads as precise and "system-generated".
 */

import type { TextStyle } from 'react-native';

import { fonts } from './tokens';

export const textStyles = {
  display: {
    fontFamily: fonts.sansBold,
    fontSize: 40,
    lineHeight: 42,
    letterSpacing: -0.8,
  },
  headlineLg: {
    fontFamily: fonts.sansBold,
    fontSize: 23,
    lineHeight: 28,
  },
  headlineMd: {
    fontFamily: fonts.sansBold,
    fontSize: 20,
    lineHeight: 24,
  },
  bodyLg: {
    fontFamily: fonts.sansRegular,
    fontSize: 16,
    lineHeight: 24,
  },
  bodySm: {
    fontFamily: fonts.sansSemiBold,
    fontSize: 14,
    lineHeight: 20,
  },
  dataLg: {
    fontFamily: fonts.monoSemiBold,
    fontSize: 22,
    lineHeight: 28,
  },
  dataSm: {
    fontFamily: fonts.monoMedium,
    fontSize: 12,
    lineHeight: 16,
  },
  overline: {
    fontFamily: fonts.sansSemiBold,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.32,
    textTransform: 'uppercase',
  },
  label: {
    fontFamily: fonts.sansSemiBold,
    fontSize: 10.5,
    lineHeight: 12,
  },
} satisfies Record<string, TextStyle>;

export type TypeName = keyof typeof textStyles;
