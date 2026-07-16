/**
 * `SectionLabel` — the uppercase overline that heads each input group (e.g. "PATIENT
 * LOCATION", "URGENCY"). Uses the `overline` type preset in muted on-surface-variant.
 */

import React from 'react';

import { AppText } from './AppText';

export function SectionLabel({ children }: { children: string }): React.ReactElement {
  return (
    <AppText variant="overline" color="onSurfaceVariant">
      {children}
    </AppText>
  );
}
