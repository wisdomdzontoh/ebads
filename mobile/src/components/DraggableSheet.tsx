/**
 * `DraggableSheet` — a bottom sheet that collapses when the dispatcher drags its handle down
 * and expands when dragged up, snapping to the nearer of two heights on release. This is the
 * ride-hailing "drag the card" interaction (Bolt/Uber) that Dispatch's form/result card and
 * live navigation's info bar are modelled on.
 *
 * Deliberately dependency-free: `PanResponder` + `Animated` are both react-native core, so this
 * needed no `react-native-gesture-handler`/`react-native-reanimated` addition — the mobile app
 * targets a pinned Expo SDK 56 native dependency set (AGENTS.md), and a new native module means
 * a fresh prebuild for every install. The gesture is captured only on the handle strip (not the
 * whole card), which sidesteps the classic pan-vs-scroll conflict a `ScrollView` full of content
 * would otherwise create without gesture-handler's simultaneous-recognizer support.
 *
 * A FIXED-height container is used throughout; collapsing TRANSLATES it down by
 * `(expandedHeight - collapsedHeight)` rather than resizing the container — the hidden portion
 * simply moves below the screen's bottom edge. Resizing a container that has a `ScrollView`
 * (and sometimes a focused `TextInput`) inside fights the layout system far more than a
 * transform does.
 */

import React, { useEffect, useRef } from 'react';
import {
  Animated,
  PanResponder,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, radius } from '../theme';

interface DraggableSheetProps {
  /** Peek height when collapsed — must still show something meaningful at the top of `children`. */
  collapsedHeight: number;
  /** Height when fully expanded. */
  expandedHeight: number;
  /** Start (or snap backto) expanded whenever this changes — e.g. the caller's content switched
   * from a form to a result and should present itself fully open again. */
  resetKey?: string | number;
  /** Start collapsed instead of expanded the first time `resetKey` takes a given value. */
  startCollapsed?: boolean;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function DraggableSheet({
  collapsedHeight,
  expandedHeight,
  resetKey,
  startCollapsed = false,
  children,
  style,
}: DraggableSheetProps): React.ReactElement {
  const travel = Math.max(0, expandedHeight - collapsedHeight);
  const translateY = useRef(new Animated.Value(startCollapsed ? travel : 0)).current;
  const startValue = useRef(startCollapsed ? travel : 0);

  useEffect(() => {
    const target = startCollapsed ? travel : 0;
    startValue.current = target;
    Animated.spring(translateY, { toValue: target, useNativeDriver: true, bounciness: 4 }).start();
    // Only the identity of `resetKey` changing should re-open/re-collapse the sheet — `travel`
    // and `startCollapsed` are read at that moment, not tracked continuously.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onMoveShouldSetPanResponderCapture: (_evt, gesture) => Math.abs(gesture.dy) > 6,
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
        // A decisive flick wins regardless of position; otherwise snap to whichever end is closer.
        const collapse =
          gesture.vy > 0.6 || (gesture.vy > -0.6 && current > travel / 2);
        const target = collapse ? travel : 0;
        startValue.current = target;
        Animated.spring(translateY, { toValue: target, useNativeDriver: true, bounciness: 4 }).start();
      },
    }),
  ).current;

  return (
    <Animated.View
      style={[styles.root, { height: expandedHeight, transform: [{ translateY }] }, style]}
    >
      <View {...panResponder.panHandlers} style={styles.handleArea}>
        <View style={styles.handle} />
      </View>
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { position: 'absolute', left: 0, right: 0, bottom: 0 },
  handleArea: { paddingVertical: 10, alignItems: 'center' },
  handle: { width: 40, height: 4, borderRadius: radius.pill, backgroundColor: colors.outlineVariant },
});
