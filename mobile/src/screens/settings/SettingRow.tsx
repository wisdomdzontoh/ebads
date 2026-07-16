/**
 * Small labelled setting primitives used across the Settings screen (docs/05 §2.4).
 * A titled block, a text field with an icon, and a masked (secret) field with show/hide.
 */

import { MaterialIcons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { AppText, SectionLabel } from '../../components';
import { colors, radius } from '../../theme';

export function LabeledField({
  label,
  value,
  onChangeText,
  onEndEditing,
  icon,
  placeholder,
  keyboardType,
  autoCapitalize = 'none',
}: {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  onEndEditing?: () => void;
  icon?: keyof typeof MaterialIcons.glyphMap;
  placeholder?: string;
  keyboardType?: 'default' | 'url' | 'number-pad';
  autoCapitalize?: 'none' | 'sentences';
}): React.ReactElement {
  return (
    <View style={styles.field}>
      <SectionLabel>{label}</SectionLabel>
      <View style={styles.inputRow}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          onEndEditing={onEndEditing}
          onBlur={onEndEditing}
          placeholder={placeholder}
          placeholderTextColor={colors.slate400}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={false}
          style={styles.input}
        />
        {icon ? <MaterialIcons name={icon} size={20} color={colors.onSurfaceVariant} /> : null}
      </View>
    </View>
  );
}

export function SecretField({
  label,
  value,
  onChangeText,
  onEndEditing,
  placeholder,
}: {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  onEndEditing?: () => void;
  placeholder?: string;
}): React.ReactElement {
  const [visible, setVisible] = useState(false);
  return (
    <View style={styles.field}>
      <SectionLabel>{label}</SectionLabel>
      <View style={styles.inputRow}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          onEndEditing={onEndEditing}
          onBlur={onEndEditing}
          placeholder={placeholder}
          placeholderTextColor={colors.slate400}
          secureTextEntry={!visible}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
        <Pressable onPress={() => setVisible((current) => !current)} hitSlop={8}>
          <MaterialIcons
            name={visible ? 'visibility-off' : 'visibility'}
            size={20}
            color={colors.onSurfaceVariant}
          />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  field: { gap: 10 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.outlineVariant,
    borderRadius: radius.control,
    paddingHorizontal: 14,
    backgroundColor: colors.surfaceContainerLow,
  },
  input: {
    flex: 1,
    fontFamily: 'IBMPlexMono_500Medium',
    fontSize: 14,
    color: colors.slate900,
  },
});
