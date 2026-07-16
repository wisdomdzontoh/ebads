/**
 * Design tokens — the single source of truth for the EBADS mobile visual language.
 *
 * These values are transcribed verbatim from the design system
 * (`artifacts/Mobile app UI design system/DESIGN.md`): a Material-3 palette with a
 * clinical-teal brand, semantic triage colours (critical/urgent/standard), and a dual-font
 * strategy — IBM Plex Sans for interface text, IBM Plex Mono for "system-generated" data
 * (metrics, coordinates, scores). Colour here is never decorative: it is a triage/availability
 * signal (DESIGN.md §Colors). Every screen and component reads from this file so the UI stays
 * one coherent system.
 */

/** Semantic + neutral palette (DESIGN.md colour tokens). */
export const colors = {
  // Surfaces / scaffolding
  surface: '#f7f9fd',
  surfaceContainerLowest: '#ffffff',
  surfaceContainerLow: '#f2f4f8',
  surfaceContainer: '#eceef2',
  surfaceContainerHigh: '#e6e8ec',
  surfaceContainerHighest: '#e0e3e6',

  // Text / lines
  onSurface: '#191c1f',
  onSurfaceVariant: '#3f484a',
  outline: '#6f797a',
  outlineVariant: '#bec8ca',
  slate900: '#101826',
  slate400: '#8A94A3',

  // Brand (clinical teal = "the system" and its recommendations)
  clinicalTeal: '#0A616B',
  primary: '#004850',
  inkTeal: '#083F47',
  onPrimary: '#ffffff',

  // Semantic triage / availability
  criticalRed: '#E5484D',
  urgentOrange: '#D98324',
  standardGreen: '#2F9E6B',

  // Tints (selected states / soft backgrounds)
  redTint: '#FDECEC',
  orangeTint: '#FDF2E3',
  greenTint: '#E7F5EE',

  // Error
  error: '#ba1a1a',
  onError: '#ffffff',
} as const;

/** Font family names as registered by @expo-google-fonts (loaded in App root). */
export const fonts = {
  sansRegular: 'IBMPlexSans_400Regular',
  sansSemiBold: 'IBMPlexSans_600SemiBold',
  sansBold: 'IBMPlexSans_700Bold',
  monoMedium: 'IBMPlexMono_500Medium',
  monoSemiBold: 'IBMPlexMono_600SemiBold',
} as const;

/** 4px baseline grid + named layout gaps (DESIGN.md §Layout & Spacing). */
export const spacing = {
  base: 4,
  cardGap: 10,
  marginMobile: 12,
  gutter: 18,
  sectionGap: 24,
  safeAreaBottom: 26,
} as const;

/**
 * Corner radii (DESIGN.md §Shapes): 16px primary cards, 12px internal controls,
 * 999px pills/status. Kept small→large for occasional inner elements.
 */
export const radius = {
  sm: 8,
  control: 12,
  card: 16,
  pill: 9999,
} as const;

/** Standard card shadow (DESIGN.md §Elevation): soft, low-contrast slate. */
export const shadow = {
  card: {
    shadowColor: '#101826',
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  // Tinted teal "press" glow for the primary CTA (DESIGN.md §Elevation).
  primaryCta: {
    shadowColor: '#0A616B',
    shadowOpacity: 0.4,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
} as const;

export type ColorName = keyof typeof colors;
