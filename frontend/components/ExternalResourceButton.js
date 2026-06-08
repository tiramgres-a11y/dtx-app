// @flow
/**
 * ExternalResourceButton.js — Content Curation deep-link component
 *
 * Renders a tappable CTA button when the Orchestrator attaches an
 * `action_url` + `action_label` to an evaluation response.
 * Tapping opens the URL in an in-app browser overlay via
 * expo-web-browser so the user never leaves the app.
 *
 * NULL SAFETY:
 *   If either `url` or `label` is falsy the component renders nothing.
 *   This matches the Orchestrator contract: both fields must be non-null.
 *
 * RTL CONSTRAINTS (per ROADMAP.md):
 *   ✓ Icon sits at marginEnd (right-side reading start in RTL)
 *   ✓ Label text is right-aligned via RTL.text
 *   ✓ No marginLeft / marginRight — only marginStart / marginEnd
 *   ✓ No inline Hebrew string literals — all labels come from the API
 *
 * PROPS:
 *   url         {string|null}   — External URL (YouTube, recipe, etc.)
 *   label       {string|null}   — Hebrew CTA label from Orchestrator
 *   accentColor {string}        — Optional accent (defaults to brand blue)
 *   style       {object}        — Optional additional container style
 *
 * ARCHITECTURE:
 *   Owned by Worker 2 (Frontend Manager). Zero clinical logic.
 *   All text comes from the Orchestrator response — not from locales directly.
 */

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';

import { COLORS, FONT, SPACING, RADIUS, RTL } from './tokens';
import { t } from '../utils/i18n';

// expo-web-browser: safe import — graceful degradation on unsupported platforms
let WebBrowser = null;
try {
  WebBrowser = require('expo-web-browser');
} catch (_) { /* no-op */ }

// ── Component ─────────────────────────────────────────────────────────────

export default function ExternalResourceButton({
  url,
  label,
  accentColor = COLORS.primary,
  style       = null,
}) {
  // Null-safety guard: render nothing when either field is missing
  if (!url || !label) return null;

  const [isLoading, setIsLoading] = useState(false);

  const handlePress = useCallback(async () => {
    if (isLoading) return;
    setIsLoading(true);
    try {
      if (WebBrowser && typeof WebBrowser.openBrowserAsync === 'function') {
        // In-app browser overlay (iOS SFSafariViewController / Android Custom Tab)
        await WebBrowser.openBrowserAsync(url, {
          toolbarColor:          accentColor,
          controlsColor:         '#FFFFFF',
          showTitle:             true,
          enableBarCollapsing:   true,
        });
      } else {
        // Web fallback: open in new tab (Expo Web or unsupported native)
        if (typeof window !== 'undefined') {
          window.open(url, '_blank', 'noopener,noreferrer');
        }
      }
    } catch (_err) {
      // Silent fail — never crash the app over a resource link
    } finally {
      setIsLoading(false);
    }
  }, [url, accentColor, isLoading]);

  return (
    <TouchableOpacity
      style={[styles.btn, { borderColor: accentColor, borderStartColor: accentColor }, style]}
      onPress={handlePress}
      disabled={isLoading}
      accessibilityRole="link"
      accessibilityLabel={label}
      accessibilityHint={t('ACTION_OPEN_ACCESSIBILITY_HINT')}
    >
      <View style={[styles.inner, RTL.row]}>
        {/* Icon — positioned at marginEnd (start of RTL reading direction) */}
        <View style={[styles.iconWrap, { backgroundColor: accentColor + '20' }]}>
          {isLoading
            ? <ActivityIndicator size="small" color={accentColor} />
            : <Text style={[styles.icon, { color: accentColor }]}>🔗</Text>
          }
        </View>

        {/* Label — right-aligned Hebrew text */}
        <Text
          style={[styles.label, { color: accentColor }, RTL.text]}
          numberOfLines={2}
        >
          {label}
        </Text>

        {/* Chevron — LTR visual indicator (→) flips automatically in RTL */}
        <Text style={[styles.chevron, { color: accentColor }]}>‹</Text>
      </View>
    </TouchableOpacity>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  btn: {
    backgroundColor:  COLORS.surface,
    borderRadius:     RADIUS.md,
    borderWidth:      1.5,
    // borderColor set inline; borderStartColor provides RTL accent stripe
    borderStartWidth: 4,
    marginTop:        SPACING.sm,
    overflow:         'hidden',
    // Shadow
    shadowColor:      '#000',
    shadowOffset:     { width: 0, height: 1 },
    shadowOpacity:    0.06,
    shadowRadius:     3,
    elevation:        2,
  },

  inner: {
    paddingHorizontal: SPACING.sm,
    paddingVertical:   SPACING.xs,
    alignItems:        'center',
    // RTL.row provides flexDirection: 'row', writingDirection: 'rtl'
  },

  iconWrap: {
    width:        36,
    height:       36,
    borderRadius: RADIUS.md,
    alignItems:   'center',
    justifyContent: 'center',
    marginEnd:    SPACING.sm,   // RTL: gap between icon and label
    flexShrink:   0,
  },

  icon: {
    fontSize: 18,
  },

  label: {
    flex:       1,
    fontSize:   FONT.sm,
    fontWeight: '600',
    lineHeight: FONT.sm * 1.4,
  },

  chevron: {
    fontSize:    FONT.lg,
    fontWeight:  '300',
    marginStart: SPACING.xs,    // RTL: gap between label and chevron
    opacity:     0.6,
  },
});
