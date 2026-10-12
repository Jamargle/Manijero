package com.jamarglex.manijero.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import kotlin.math.pow

/**
 * The Manijero visual foundation: the olive-grove palette from `DESIGN.md` ("Visual foundation").
 *
 * This file is the only place in the repository allowed to declare a hex colour. Screens read
 * [androidx.compose.material3.MaterialTheme.colorScheme] roles or [LocalManijeroSemanticColors]
 * instead, so a palette change stays a one-file change.
 */

// ---------------------------------------------------------------------------------------------
// DESIGN.md tokens. These are the source of truth: they must not change without updating DESIGN.md.
// ---------------------------------------------------------------------------------------------

/** `olive-800`: primary actions, navigation, selected states. */
internal val ManijeroOlive800 = Color(0xFF354B32)

/** `olive-900`: pressed state and strong emphasis (`primaryStrong`). */
internal val ManijeroOlive900 = Color(0xFF263724)

/** `canvas`: warm page background. */
internal val ManijeroCanvas = Color(0xFFF7F6F0)

/** `surface`: cards and input surfaces. */
internal val ManijeroSurface = Color(0xFFFFFFFF)

/** `text-primary`: main text. */
internal val ManijeroTextPrimary = Color(0xFF1D221B)

/** `text-secondary`: secondary text and metadata. */
internal val ManijeroTextSecondary = Color(0xFF4B5149)

/** `border`: form boundaries and separators (`outline`). */
internal val ManijeroBorder = Color(0xFF777D73)

/** `caution`: warnings, always paired with text or an icon. */
internal val ManijeroCaution = Color(0xFF704600)

/** `caution-surface`: caution callout background, always beside caution text. */
internal val ManijeroCautionSurface = Color(0xFFFFF2D4)

/** `danger`: errors and destructive actions (`error`), always paired with text or an icon. */
internal val ManijeroDanger = Color(0xFFA12622)

/** `scrim`: intentionally the Material default; a black scrim carries no hue to leak. */
internal val ManijeroScrim = Color(0xFF000000)

// ---------------------------------------------------------------------------------------------
// Derived values. DESIGN.md names only the ten tokens above; these replace the remaining Material 3
// colour roles. They stay inside the same warm-neutral/olive families (no new hue), and each one is
// justified here. DESIGN.md documents the same table.
// ---------------------------------------------------------------------------------------------

/** Low-emphasis container: the person's own message bubble. Neutral so olive keeps meaning "primary". */
internal val ManijeroSurfaceVariant = Color(0xFFE7E5DD)

/** Warm lift family for future cards, menus, and sheets. */
internal val ManijeroSurfaceContainerLowest = Color(0xFFFFFFFF)
internal val ManijeroSurfaceContainerLow = Color(0xFFFCFBF6)
internal val ManijeroSurfaceContainer = Color(0xFFF2F0E9)
internal val ManijeroSurfaceContainerHigh = Color(0xFFEDEBE3)
internal val ManijeroSurfaceContainerHighest = Color(0xFFE7E5DD)

/** Surface extremes and the recessed surface. */
internal val ManijeroSurfaceBright = Color(0xFFFFFFFC)
internal val ManijeroSurfaceDim = Color(0xFFDFDDD4)

/** Softer separator/bubble border that still clears 3:1 against canvas, surface, and surfaceVariant. */
internal val ManijeroOutlineVariant = Color(0xFF7E8479)

/** Light olive fill for selected/tonal containers; text on it is [ManijeroOlive900]. */
internal val ManijeroPrimaryContainer = Color(0xFFD9E2D2)

/** Second tonal fill, same olive family as [ManijeroPrimaryContainer]. */
internal val ManijeroSecondaryContainer = Color(0xFFDFE4D8)

/**
 * Third emphasis step. Still olive: a brown tertiary would read as a caution state.
 * [ManijeroTertiaryContainer] is the lightest tonal fill.
 */
internal val ManijeroTertiary = Color(0xFF40573C)
internal val ManijeroTertiaryContainer = Color(0xFFE9EDE2)

/** Snackbar/reverse surfaces that avoid the Material purple family. */
internal val ManijeroInverseSurface = Color(0xFF2E332C)
internal val ManijeroInverseOnSurface = Color(0xFFF1F2EC)
internal val ManijeroInversePrimary = Color(0xFFB6C4AC)

/** Calm danger container derived from [ManijeroDanger] instead of a Material default. */
internal val ManijeroErrorContainer = Color(0xFFF9DEDA)
internal val ManijeroOnErrorContainer = Color(0xFF6E1714)

// ---------------------------------------------------------------------------------------------
// Roles
// ---------------------------------------------------------------------------------------------

/**
 * Every role the palette documents is set explicitly, so no component can fall back to a Material
 * default (purple/teal). The Material 3 expressive `*Fixed` roles are intentionally absent: they are
 * not part of the DESIGN.md token set and no screen uses them.
 */
internal val ManijeroLightColorScheme: ColorScheme = lightColorScheme(
    primary = ManijeroOlive800,
    onPrimary = ManijeroSurface,
    primaryContainer = ManijeroPrimaryContainer,
    onPrimaryContainer = ManijeroOlive900,
    inversePrimary = ManijeroInversePrimary,
    secondary = ManijeroTextSecondary,
    onSecondary = ManijeroSurface,
    secondaryContainer = ManijeroSecondaryContainer,
    onSecondaryContainer = ManijeroOlive900,
    tertiary = ManijeroTertiary,
    onTertiary = ManijeroSurface,
    tertiaryContainer = ManijeroTertiaryContainer,
    onTertiaryContainer = ManijeroOlive900,
    background = ManijeroCanvas,
    onBackground = ManijeroTextPrimary,
    surface = ManijeroSurface,
    onSurface = ManijeroTextPrimary,
    surfaceVariant = ManijeroSurfaceVariant,
    onSurfaceVariant = ManijeroTextSecondary,
    surfaceTint = ManijeroOlive800,
    inverseSurface = ManijeroInverseSurface,
    inverseOnSurface = ManijeroInverseOnSurface,
    error = ManijeroDanger,
    onError = ManijeroSurface,
    errorContainer = ManijeroErrorContainer,
    onErrorContainer = ManijeroOnErrorContainer,
    outline = ManijeroBorder,
    outlineVariant = ManijeroOutlineVariant,
    scrim = ManijeroScrim,
    surfaceBright = ManijeroSurfaceBright,
    surfaceDim = ManijeroSurfaceDim,
    surfaceContainerLowest = ManijeroSurfaceContainerLowest,
    surfaceContainerLow = ManijeroSurfaceContainerLow,
    surfaceContainer = ManijeroSurfaceContainer,
    surfaceContainerHigh = ManijeroSurfaceContainerHigh,
    surfaceContainerHighest = ManijeroSurfaceContainerHighest,
)

// ---------------------------------------------------------------------------------------------
// Semantic colours Material 3 has no role for
// ---------------------------------------------------------------------------------------------

/**
 * The tokens Material 3 cannot express. Danger is deliberately absent: it is
 * [ColorScheme.error], and the border is [ColorScheme.outline], so one value keeps one source.
 *
 * @property caution caution text/icon on `canvas`, `surface`, or [cautionSurface]; all pairs clear
 * 4.5:1.
 * @property onCaution content on a solid caution-filled surface (8.19:1 against [caution]).
 * @property cautionSurface caution callout background, always beside explicit caution text.
 * @property primaryStrong `olive-900` emphasis for strong labels or surfaces (11.72:1 as text on
 * `canvas`). Material's pressed feedback is a state layer over `primary`, not a container swap.
 */
@Immutable
data class ManijeroSemanticColors(
    val caution: Color,
    val onCaution: Color,
    val cautionSurface: Color,
    val primaryStrong: Color,
)

/** The light semantic colours; also the local's default, so a missing provider cannot crash. */
internal val ManijeroLightSemanticColors = ManijeroSemanticColors(
    caution = ManijeroCaution,
    onCaution = ManijeroSurface,
    cautionSurface = ManijeroCautionSurface,
    primaryStrong = ManijeroOlive900,
)

/**
 * Provides the Manijero-only tokens. The default is the light set, so previews and screens rendered
 * outside [ManijeroTheme] still read real Manijero values instead of crashing.
 */
val LocalManijeroSemanticColors = staticCompositionLocalOf { ManijeroLightSemanticColors }

// ---------------------------------------------------------------------------------------------
// WCAG contrast helpers (dependency-free, no I/O; used by the contrast tests)
// ---------------------------------------------------------------------------------------------

/** WCAG 2.x relative luminance of an sRGB colour (0.0 for black, 1.0 for white). */
internal fun relativeLuminance(color: Color): Double {
    fun linearize(component: Float): Double {
        val value = component.toDouble()
        return if (value <= 0.04045) value / 12.92 else ((value + 0.055) / 1.055).pow(2.4)
    }

    return 0.2126 * linearize(color.red) +
        0.7152 * linearize(color.green) +
        0.0722 * linearize(color.blue)
}

/** WCAG 2.x contrast ratio between two colours, from 1.0 (identical) to 21.0 (black on white). */
internal fun contrastRatio(first: Color, second: Color): Double {
    val firstLuminance = relativeLuminance(first)
    val secondLuminance = relativeLuminance(second)
    val lighter = maxOf(firstLuminance, secondLuminance)
    val darker = minOf(firstLuminance, secondLuminance)
    return (lighter + 0.05) / (darker + 0.05)
}
