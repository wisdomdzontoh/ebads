/**
 * `DraggableSheet` — a bottom sheet that collapses when dragged down and expands when dragged
 * up, snapping to the nearer of two heights on release — the ride-hailing "drag the card"
 * interaction (Bolt/Uber). Two ways to trigger it, because neither should be the ONLY way:
 *
 * 1. Drag ANYWHERE on the sheet — not just the thin handle strip. When the sheet is collapsed,
 *    any vertical drag on it expands it. When expanded, a downward drag is claimed by the
 *    sheet (to collapse it) only once its internal content is scrolled to the very top —
 *    otherwise the drag scrolls the content, same as any normal scrollable. This is a
 *    heuristic, not a full gesture-arbitration engine: `react-native-gesture-handler` +
 *    `react-native-reanimated` would resolve this more precisely (simultaneous recognizers,
 *    velocity-aware direction locking), but neither is part of the pinned Expo SDK 56 native
 *    dependency set (AGENTS.md) — adding either means a fresh native build before it takes
 *    effect, so this stays PanResponder + Animated (both React Native core) until that
 *    trade-off is worth making deliberately, not as a side effect of a UX polish pass.
 * 2. An explicit close (X) button, top-right — collapses the sheet with a guaranteed tap,
 *    regardless of whether the drag heuristic above judged the gesture correctly. This is the
 *    fallback that makes the whole thing reliable even when 1 is imperfect.
 *
 * Owns its own internal `ScrollView` (rather than the caller wrapping one) specifically so it
 * can track scroll position for the heuristic above — every current caller only ever wrapped a
 * single ScrollView around plain content anyway, so this loses no flexibility.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useRef } from 'react';
import {
  Animated,
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, radius, spacing } from '../theme';

/** A drag shorter than this (px) is treated as a tap/scroll, not a collapse/expand gesture. */
const DRAG_THRESHOLD = 6;
/** A release faster than this (px/ms) commits to the direction of the flick regardless of
 * how far the sheet had moved — matches native "flick to dismiss" sheets. */
const FLING_VELOCITY = 0.6;

interface DraggableSheetProps {
  /** Peek height when collapsed — must still show something meaningful at the top of `children`. */
  collapsedHeight: number;
  /** Height when fully expanded. */
  expandedHeight: number;
  /** Start (or snap back to) expanded whenever this changes — e.g. the caller's content switched
   * from a form to a result and should present itself fully open again. */
  resetKey?: string | number;
  /** Start collapsed instead of expanded the first time `resetKey` takes a given value. */
  startCollapsed?: boolean;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  contentContainerStyle?: StyleProp<ViewStyle>;
  keyboardShouldPersistTaps?: 'never' | 'always' | 'handled';
  /** Called after the close (X) button collapses the sheet — optional, since collapsing is
   * already the entire effect; callers with nothing extra to do can omit it. */
  onClose?: () => void;
}

export function DraggableSheet({
  collapsedHeight,
  expandedHeight,
  resetKey,
  startCollapsed = false,
  children,
  style,
  contentContainerStyle,
  keyboardShouldPersistTaps,
  onClose,
}: DraggableSheetProps): React.ReactElement {
  const travel = Math.max(0, expandedHeight - collapsedHeight);
  const translateY = useRef(new Animated.Value(startCollapsed ? travel : 0)).current;
  const startValue = useRef(startCollapsed ? travel : 0);
  // Which mode the whole-sheet drag heuristic is currently in — a ref, not state: the
  // PanResponder callbacks close over it and must see the latest value synchronously, and
  // nothing here needs a re-render off the back of it (the close button is always shown, drag
  // itself is purely imperative via `translateY`).
  const collapsedRef = useRef(startCollapsed);
  const scrollYRef = useRef(0);

  const settle = (collapse: boolean): void => {
    const target = collapse ? travel : 0;
    startValue.current = target;
    collapsedRef.current = collapse;
    Animated.spring(translateY, { toValue: target, useNativeDriver: true, bounciness: 4 }).start();
  };

  React.useEffect(() => {
    settle(startCollapsed);
    // Only `resetKey` changing should re-open/re-collapse the sheet.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  const handleScroll = (event: NativeSyntheticEvent<NativeScrollEvent>): void => {
    scrollYRef.current = event.nativeEvent.contentOffset.y;
  };

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponderCapture: (_evt, gesture) => {
        if (Math.abs(gesture.dy) < DRAG_THRESHOLD || Math.abs(gesture.dy) <= Math.abs(gesture.dx)) {
          return false;
        }
        // Collapsed: the peek has nothing worth scrolling, so any vertical drag opens it.
        if (collapsedRef.current) return true;
        // Expanded: only claim a downward drag once the content can't scroll up any further —
        // otherwise this steals an ordinary scroll gesture the moment it starts.
        return gesture.dy > 0 && scrollYRef.current <= 0;
      },
      onPanResponderGrant: () => {
        translateY.stopAnimation((value) => {
          startValue.current = value;
        });
      },
      onPanResponderMove: (_evt, gesture) => {
        const next = Math.min(travel, Math.max(0, startValue.current + gesture.dy));
        translateY.setValue(next);
      },
      onPanResponderRelease: (_evt, gesture) => {
        const current = Math.min(travel, Math.max(0, startValue.current + gesture.dy));
        const collapse = gesture.vy > FLING_VELOCITY || (gesture.vy > -FLING_VELOCITY && current > travel / 2);
        settle(collapse);
      },
    }),
  ).current;

  return (
    <Animated.View
      style={[styles.root, { height: expandedHeight, transform: [{ translateY }] }, style]}
      {...panResponder.panHandlers}
    >
      <View style={styles.headerRow}>
        <View style={styles.handle} />
      </View>
      {/* Always present, in both states — a guaranteed tap to collapse regardless of whether
          the whole-sheet drag heuristic judged a given gesture correctly (see module
          docstring); a no-op if already collapsed, never hidden or repositioned as the sheet
          animates so it isn't a moving target. */}
      <Pressable
        onPress={() => {
          settle(true);
          onClose?.();
        }}
        accessibilityRole="button"
        accessibilityLabel="Collapse sheet"
        hitSlop={10}
        style={styles.closeButton}
      >
        <MaterialIcons name="close" size={18} color={colors.slate900} />
      </Pressable>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={contentContainerStyle}
        onScroll={handleScroll}
        scrollEventThrottle={16}
        keyboardShouldPersistTaps={keyboardShouldPersistTaps}
        showsVerticalScrollIndicator={false}
      >
        {children}
      </ScrollView>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  headerRow: { paddingTop: 10, paddingBottom: 6, alignItems: 'center' },
  handle: { width: 40, height: 4, borderRadius: radius.pill, backgroundColor: colors.outlineVariant },
  closeButton: {
    position: 'absolute',
    top: 8,
    right: spacing.marginMobile,
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceContainer,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: { flex: 1 },
});
