package com.jamarglex.manijero.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import kotlin.math.pow

/**
 * The world-facing colour palette: the Stitch token set recorded in `DESIGN.md` ("Palette").
 *
 * The light and dark values are the Stitch token exports, with two changes only: `outlineVariant`
 * is darkened/lightened enough to clear the WCAG 3:1 non-text contrast floor on every surface, and
 * `scrim` keeps Material's black because neither export defines it.
 *
 * This file is the only place in the repository allowed to declare a hex colour. Screens read
 * [androidx.compose.material3.MaterialTheme.colorScheme] roles or [LocalManijeroSemanticColors]
 * instead, so a palette change stays a one-file change.
 */

// ---------------------------------------------------------------------------------------------
// DESIGN.md light tokens. These are the source of truth: they must not change without updating
// DESIGN.md ("Core tokens" and "Material role map").
// ---------------------------------------------------------------------------------------------

/** `olive-800`: primary actions, navigation, selected states. */
internal val ManijeroOlive800 = Color(0xFF214624)

/** `olive-900`: pressed state and strong emphasis (`primaryStrong`). */
internal val ManijeroOlive900 = Color(0xFF263724)

/** `canvas`: page background. */
internal val ManijeroCanvas = Color(0xFFF9FAF4)

/** The one white in the system: card/input surfaces and every on-colour Stitch documents as white. */
internal val ManijeroWhite = Color(0xFFFFFFFF)

/** `surface`: cards and input surfaces (Material `surfaceContainerLowest`). */
internal val ManijeroSurface = ManijeroWhite

/** `text-primary`: main text. */
internal val ManijeroTextPrimary = Color(0xFF1A1C19)

/** `text-secondary`: secondary text and metadata. */
internal val ManijeroTextSecondary = Color(0xFF424940)

/** `border`: form boundaries and separators (`outline`). */
internal val ManijeroBorder = Color(0xFF72796F)

/** `outlineVariant`: the lowered-emphasis boundary; the one light Stitch value that fails a gate. */
internal val ManijeroOutlineVariant = Color(0xFF757C71)

/** `caution`: warnings and limitations, always paired with text or an icon. */
internal val ManijeroCaution = Color(0xFF704600)

/** `caution-surface`: caution callout background, always beside caution text. */
internal val ManijeroCautionSurface = Color(0xFFFFF2D4)

/** `danger`: errors and destructive actions (`error`), always paired with text or an icon. */
internal val ManijeroDanger = Color(0xFFBA1A1A)

/** `scrim`: intentionally the Material default; a black scrim carries no hue to leak. */
internal val ManijeroScrim = Color(0xFF000000)

// ---------------------------------------------------------------------------------------------
// Remaining light roles. Stitch documents each value; none is derived locally.
// ---------------------------------------------------------------------------------------------

internal val ManijeroPrimaryContainer = Color(0xFF385E39)
internal val ManijeroOnPrimaryContainer = Color(0xFFABD6A7)

internal val ManijeroSecondary = Color(0xFF7E562E)
internal val ManijeroSecondaryContainer = Color(0xFFFDC796)
internal val ManijeroOnSecondaryContainer = Color(0xFF79512A)

internal val ManijeroTertiary = Color(0xFF602E40)
internal val ManijeroTertiaryContainer = Color(0xFF7B4557)
internal val ManijeroOnTertiaryContainer = Color(0xFFFEB7CC)

/** Neutral container behind user messages and excerpts. */
internal val ManijeroSurfaceVariant = Color(0xFFE2E3DD)

/** The tint Material uses for elevated surfaces; Stitch defines its own, not `primary`. */
internal val ManijeroSurfaceTint = Color(0xFF416741)

/** Snackbar/reverse surfaces. */
internal val ManijeroInverseSurface = Color(0xFF2F312D)
internal val ManijeroInverseOnSurface = Color(0xFFF1F1EB)
internal val ManijeroInversePrimary = Color(0xFFA7D2A3)

/** Error container from the Stitch error family rather than a Material default. */
internal val ManijeroErrorContainer = Color(0xFFFFDAD6)
internal val ManijeroOnErrorContainer = Color(0xFF93000A)

/** Surface extremes and the tonal container family. */
internal val ManijeroSurfaceBright = Color(0xFFF9FAF4)
internal val ManijeroSurfaceDim = Color(0xFFDADAD5)
internal val ManijeroSurfaceContainerLowest = Color(0xFFFFFFFF)
internal val ManijeroSurfaceContainerLow = Color(0xFFF3F4EE)
internal val ManijeroSurfaceContainer = Color(0xFFEEEEE9)
internal val ManijeroSurfaceContainerHigh = Color(0xFFE8E9E3)
internal val ManijeroSurfaceContainerHighest = Color(0xFFE2E3DD)

/**
 * The Ecológico land-attribute chip pair. Stitch exposes it as `primaryFixed`/`onPrimaryFixed`,
 * which this Material version does not map to roles, so it is kept as a semantic value.
 */
internal val ManijeroEcoChipContainer = Color(0xFFC2EEBE)
internal val ManijeroOnEcoChipContainer = Color(0xFF002106)

// ---------------------------------------------------------------------------------------------
// Roles
// ---------------------------------------------------------------------------------------------

/**
 * Every role the palette documents is set explicitly, so no component can fall back to a Material
 * default (purple/teal). Stitch's `*Fixed` roles are not exposed by this Material version and are
 * intentionally absent.
 *
 * Note that Stitch sets `background`, `surface`, and `surfaceBright` to the same light value. The
 * Material role `surface` is therefore the page canvas; raised cards and inputs use
 * `surfaceContainerLowest` (the `surface` design token), as documented in `DESIGN.md`.
 */
internal val ManijeroLightColorScheme: ColorScheme = lightColorScheme(
    primary = ManijeroOlive800,
    onPrimary = ManijeroWhite,
    primaryContainer = ManijeroPrimaryContainer,
    onPrimaryContainer = ManijeroOnPrimaryContainer,
    inversePrimary = ManijeroInversePrimary,
    secondary = ManijeroSecondary,
    onSecondary = ManijeroWhite,
    secondaryContainer = ManijeroSecondaryContainer,
    onSecondaryContainer = ManijeroOnSecondaryContainer,
    tertiary = ManijeroTertiary,
    onTertiary = ManijeroWhite,
    tertiaryContainer = ManijeroTertiaryContainer,
    onTertiaryContainer = ManijeroOnTertiaryContainer,
    background = ManijeroCanvas,
    onBackground = ManijeroTextPrimary,
    surface = ManijeroCanvas,
    onSurface = ManijeroTextPrimary,
    surfaceVariant = ManijeroSurfaceVariant,
    onSurfaceVariant = ManijeroTextSecondary,
    surfaceTint = ManijeroSurfaceTint,
    inverseSurface = ManijeroInverseSurface,
    inverseOnSurface = ManijeroInverseOnSurface,
    error = ManijeroDanger,
    onError = ManijeroWhite,
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

/** Dark roles are the Stitch dark token export, with the same single `outlineVariant` correction. */
internal val ManijeroDarkColorScheme: ColorScheme = darkColorScheme(
    primary = Color(0xFF85A886), onPrimary = Color(0xFF0D1B0E),
    primaryContainer = Color(0xFF283C29), onPrimaryContainer = Color(0xFFCFE8CF),
    inversePrimary = Color(0xFF456648), secondary = Color(0xFFD4C5A9), onSecondary = Color(0xFF382E1C),
    secondaryContainer = Color(0xFF4F422E), onSecondaryContainer = Color(0xFFF1E5CC),
    tertiary = Color(0xFFB8C5D6), onTertiary = Color(0xFF222D3B),
    tertiaryContainer = Color(0xFF93A0B0), onTertiaryContainer = Color(0xFF2B3745),
    background = Color(0xFF121612), onBackground = Color(0xFFE1E3DF),
    surface = Color(0xFF121612), onSurface = Color(0xFFE1E3DF),
    surfaceVariant = Color(0xFF333532), onSurfaceVariant = Color(0xFFC2C8BF),
    surfaceTint = Color(0xFFABD0AC), inverseSurface = Color(0xFFE3E3DE),
    inverseOnSurface = Color(0xFF2F312E), error = Color(0xFFFFB4AB), onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A), onErrorContainer = Color(0xFFFFDAD6),
    outline = Color(0xFF8C948C), outlineVariant = Color(0xFF868E86), scrim = ManijeroScrim,
    surfaceBright = Color(0xFF242C24), surfaceDim = Color(0xFF1A201B),
    surfaceContainerLowest = Color(0xFF0D100D), surfaceContainerLow = Color(0xFF181E18),
    surfaceContainer = Color(0xFF202820), surfaceContainerHigh = Color(0xFF2C362C),
    surfaceContainerHighest = Color(0xFF384438),
)

// ---------------------------------------------------------------------------------------------
// Semantic colours Material 3 has no role for
// ---------------------------------------------------------------------------------------------

/**
 * The tokens Material 3 cannot express. Danger is deliberately absent: it is
 * [ColorScheme.error], and the border is [ColorScheme.outline], so one value keeps one source.
 *
 * @property caution caution text/icon on `canvas`, `surface`, or [cautionSurface]; light 7.37:1 on
 * [cautionSurface] and 8.19:1 on the white card, dark 8.12:1 and 13.44:1.
 * @property onCaution content on a solid caution-filled surface (8.19:1 light, 10.12:1 dark).
 * @property cautionSurface caution callout background, always beside explicit caution text.
 * @property primaryStrong `olive-900` emphasis for strong labels or surfaces (12.09:1 light,
 * 14.01:1 dark as text on the page background). Material's pressed feedback is a state layer over
 * `primary`, not a container swap.
 * @property ecoContainer Ecológico chip container; 13.33:1 light and 13.26:1 dark under
 * [onEcoContainer].
 * @property onEcoContainer Ecológico chip text/icon.
 */
@Immutable
data class ManijeroSemanticColors(
    val caution: Color,
    val onCaution: Color,
    val cautionSurface: Color,
    val primaryStrong: Color,
    val ecoContainer: Color,
    val onEcoContainer: Color,
)

/** The light semantic colours; also the local's default, so a missing provider cannot crash. */
internal val ManijeroLightSemanticColors = ManijeroSemanticColors(
    caution = ManijeroCaution,
    onCaution = ManijeroWhite,
    cautionSurface = ManijeroCautionSurface,
    primaryStrong = ManijeroOlive900,
    ecoContainer = ManijeroEcoChipContainer,
    onEcoContainer = ManijeroOnEcoChipContainer,
)

internal val ManijeroDarkSemanticColors = ManijeroSemanticColors(
    caution = Color(0xFFFFD18A), onCaution = Color(0xFF3A2600),
    cautionSurface = Color(0xFF4B350D), primaryStrong = Color(0xFFCFE8CF),
    ecoContainer = Color(0xFFC7ECC6), onEcoContainer = Color(0xFF02210A),
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
