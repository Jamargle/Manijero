package com.jamarglex.manijero.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import kotlin.math.round
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * Guards the shipped palette: the exact `DESIGN.md` token values, the role mapping, "no Material
 * default leaked", and the WCAG ratios documented in the feature spec.
 *
 * Pure computation: no composition, no I/O, no resources.
 */
class ManijeroColorsTest {

    private val scheme: ColorScheme = ManijeroLightColorScheme
    private val semantic = ManijeroLightSemanticColors

    // ---------------------------------------------------------------------------------------
    // Tokens
    // ---------------------------------------------------------------------------------------

    @Test
    fun `design tokens ship the exact documented values`() {
        assertToken("olive-800", Color(0xFF354B32), ManijeroOlive800)
        assertToken("olive-900", Color(0xFF263724), ManijeroOlive900)
        assertToken("canvas", Color(0xFFF7F6F0), ManijeroCanvas)
        assertToken("surface", Color(0xFFFFFFFF), ManijeroSurface)
        assertToken("text-primary", Color(0xFF1D221B), ManijeroTextPrimary)
        assertToken("text-secondary", Color(0xFF4B5149), ManijeroTextSecondary)
        assertToken("border", Color(0xFF777D73), ManijeroBorder)
        assertToken("caution", Color(0xFF704600), ManijeroCaution)
        assertToken("caution-surface", Color(0xFFFFF2D4), ManijeroCautionSurface)
        assertToken("danger", Color(0xFFA12622), ManijeroDanger)
    }

    @Test
    fun `derived values ship the documented hex values`() {
        assertToken("surfaceVariant", Color(0xFFE7E5DD), ManijeroSurfaceVariant)
        assertToken("surfaceContainerLowest", Color(0xFFFFFFFF), ManijeroSurfaceContainerLowest)
        assertToken("surfaceContainerLow", Color(0xFFFCFBF6), ManijeroSurfaceContainerLow)
        assertToken("surfaceContainer", Color(0xFFF2F0E9), ManijeroSurfaceContainer)
        assertToken("surfaceContainerHigh", Color(0xFFEDEBE3), ManijeroSurfaceContainerHigh)
        assertToken("surfaceContainerHighest", Color(0xFFE7E5DD), ManijeroSurfaceContainerHighest)
        assertToken("surfaceBright", Color(0xFFFFFFFC), ManijeroSurfaceBright)
        assertToken("surfaceDim", Color(0xFFDFDDD4), ManijeroSurfaceDim)
        assertToken("outlineVariant", Color(0xFF7E8479), ManijeroOutlineVariant)
        assertToken("primaryContainer", Color(0xFFD9E2D2), ManijeroPrimaryContainer)
        assertToken("secondaryContainer", Color(0xFFDFE4D8), ManijeroSecondaryContainer)
        assertToken("tertiary", Color(0xFF40573C), ManijeroTertiary)
        assertToken("tertiaryContainer", Color(0xFFE9EDE2), ManijeroTertiaryContainer)
        assertToken("inverseSurface", Color(0xFF2E332C), ManijeroInverseSurface)
        assertToken("inverseOnSurface", Color(0xFFF1F2EC), ManijeroInverseOnSurface)
        assertToken("inversePrimary", Color(0xFFB6C4AC), ManijeroInversePrimary)
        assertToken("errorContainer", Color(0xFFF9DEDA), ManijeroErrorContainer)
        assertToken("onErrorContainer", Color(0xFF6E1714), ManijeroOnErrorContainer)
    }

    // ---------------------------------------------------------------------------------------
    // Mapping
    // ---------------------------------------------------------------------------------------

    @Test
    fun `color scheme maps every documented role`() {
        assertRole("primary", ManijeroOlive800, scheme.primary)
        assertRole("onPrimary", ManijeroSurface, scheme.onPrimary)
        assertRole("primaryContainer", ManijeroPrimaryContainer, scheme.primaryContainer)
        assertRole("onPrimaryContainer", ManijeroOlive900, scheme.onPrimaryContainer)
        assertRole("inversePrimary", ManijeroInversePrimary, scheme.inversePrimary)
        assertRole("secondary", ManijeroTextSecondary, scheme.secondary)
        assertRole("onSecondary", ManijeroSurface, scheme.onSecondary)
        assertRole("secondaryContainer", ManijeroSecondaryContainer, scheme.secondaryContainer)
        assertRole("onSecondaryContainer", ManijeroOlive900, scheme.onSecondaryContainer)
        assertRole("tertiary", ManijeroTertiary, scheme.tertiary)
        assertRole("onTertiary", ManijeroSurface, scheme.onTertiary)
        assertRole("tertiaryContainer", ManijeroTertiaryContainer, scheme.tertiaryContainer)
        assertRole("onTertiaryContainer", ManijeroOlive900, scheme.onTertiaryContainer)
        assertRole("background", ManijeroCanvas, scheme.background)
        assertRole("onBackground", ManijeroTextPrimary, scheme.onBackground)
        assertRole("surface", ManijeroSurface, scheme.surface)
        assertRole("onSurface", ManijeroTextPrimary, scheme.onSurface)
        assertRole("surfaceVariant", ManijeroSurfaceVariant, scheme.surfaceVariant)
        assertRole("onSurfaceVariant", ManijeroTextSecondary, scheme.onSurfaceVariant)
        assertRole("surfaceTint", ManijeroOlive800, scheme.surfaceTint)
        assertRole("inverseSurface", ManijeroInverseSurface, scheme.inverseSurface)
        assertRole("inverseOnSurface", ManijeroInverseOnSurface, scheme.inverseOnSurface)
        assertRole("error", ManijeroDanger, scheme.error)
        assertRole("onError", ManijeroSurface, scheme.onError)
        assertRole("errorContainer", ManijeroErrorContainer, scheme.errorContainer)
        assertRole("onErrorContainer", ManijeroOnErrorContainer, scheme.onErrorContainer)
        assertRole("outline", ManijeroBorder, scheme.outline)
        assertRole("outlineVariant", ManijeroOutlineVariant, scheme.outlineVariant)
        assertRole("scrim", ManijeroScrim, scheme.scrim)
        assertRole("surfaceBright", ManijeroSurfaceBright, scheme.surfaceBright)
        assertRole("surfaceDim", ManijeroSurfaceDim, scheme.surfaceDim)
        assertRole("surfaceContainerLowest", ManijeroSurfaceContainerLowest, scheme.surfaceContainerLowest)
        assertRole("surfaceContainerLow", ManijeroSurfaceContainerLow, scheme.surfaceContainerLow)
        assertRole("surfaceContainer", ManijeroSurfaceContainer, scheme.surfaceContainer)
        assertRole("surfaceContainerHigh", ManijeroSurfaceContainerHigh, scheme.surfaceContainerHigh)
        assertRole("surfaceContainerHighest", ManijeroSurfaceContainerHighest, scheme.surfaceContainerHighest)
    }

    /**
     * Compared against `lightColorScheme()` computed at runtime, so a future Material release that
     * changes its defaults cannot make an unset role silently look "correct".
     *
     * Intentionally excluded: `onPrimary` / `onSecondary` / `onTertiary` / `onError` are documented
     * white and Material's defaults are white too, `surfaceContainerLowest` is documented white, and
     * `scrim` is documented as the unchanged Material default. Those roles have no hue to leak.
     */
    @Test
    fun `no brand-bearing role falls back to the Material light default`() {
        val defaults = lightColorScheme()
        val compared = listOf(
            RoleComparison("primary", scheme.primary, defaults.primary),
            RoleComparison("primaryContainer", scheme.primaryContainer, defaults.primaryContainer),
            RoleComparison("onPrimaryContainer", scheme.onPrimaryContainer, defaults.onPrimaryContainer),
            RoleComparison("inversePrimary", scheme.inversePrimary, defaults.inversePrimary),
            RoleComparison("secondary", scheme.secondary, defaults.secondary),
            RoleComparison("secondaryContainer", scheme.secondaryContainer, defaults.secondaryContainer),
            RoleComparison("onSecondaryContainer", scheme.onSecondaryContainer, defaults.onSecondaryContainer),
            RoleComparison("tertiary", scheme.tertiary, defaults.tertiary),
            RoleComparison("tertiaryContainer", scheme.tertiaryContainer, defaults.tertiaryContainer),
            RoleComparison("onTertiaryContainer", scheme.onTertiaryContainer, defaults.onTertiaryContainer),
            RoleComparison("background", scheme.background, defaults.background),
            RoleComparison("onBackground", scheme.onBackground, defaults.onBackground),
            RoleComparison("surface", scheme.surface, defaults.surface),
            RoleComparison("onSurface", scheme.onSurface, defaults.onSurface),
            RoleComparison("surfaceVariant", scheme.surfaceVariant, defaults.surfaceVariant),
            RoleComparison("onSurfaceVariant", scheme.onSurfaceVariant, defaults.onSurfaceVariant),
            RoleComparison("surfaceTint", scheme.surfaceTint, defaults.surfaceTint),
            RoleComparison("inverseSurface", scheme.inverseSurface, defaults.inverseSurface),
            RoleComparison("inverseOnSurface", scheme.inverseOnSurface, defaults.inverseOnSurface),
            RoleComparison("error", scheme.error, defaults.error),
            RoleComparison("errorContainer", scheme.errorContainer, defaults.errorContainer),
            RoleComparison("onErrorContainer", scheme.onErrorContainer, defaults.onErrorContainer),
            RoleComparison("outline", scheme.outline, defaults.outline),
            RoleComparison("outlineVariant", scheme.outlineVariant, defaults.outlineVariant),
            RoleComparison("surfaceBright", scheme.surfaceBright, defaults.surfaceBright),
            RoleComparison("surfaceDim", scheme.surfaceDim, defaults.surfaceDim),
            RoleComparison("surfaceContainerLow", scheme.surfaceContainerLow, defaults.surfaceContainerLow),
            RoleComparison("surfaceContainer", scheme.surfaceContainer, defaults.surfaceContainer),
            RoleComparison("surfaceContainerHigh", scheme.surfaceContainerHigh, defaults.surfaceContainerHigh),
            RoleComparison("surfaceContainerHighest", scheme.surfaceContainerHighest, defaults.surfaceContainerHighest),
        )

        compared.forEach { role ->
            assertNotEquals(
                role.materialDefault,
                role.actual,
                "role ${role.name} must not fall back to Material's default palette",
            )
        }
    }

    // ---------------------------------------------------------------------------------------
    // Contrast (WCAG AA)
    // ---------------------------------------------------------------------------------------

    @Test
    fun `documented text pairs meet 4 point 5 to 1 and match the spec`() {
        assertDocumentedContrast(textContrastPairs(), MINIMUM_TEXT_CONTRAST)
    }

    @Test
    fun `documented non-text pairs meet 3 to 1 and match the spec`() {
        assertDocumentedContrast(nonTextContrastPairs(), MINIMUM_NON_TEXT_CONTRAST)
    }

    private fun textContrastPairs(): List<ContrastPair> = listOf(
        ContrastPair("onBackground on canvas", scheme.onBackground, scheme.background, 14.96),
        ContrastPair("onSurface on surface", scheme.onSurface, scheme.surface, 16.19),
        ContrastPair("onSurfaceVariant on canvas", scheme.onSurfaceVariant, scheme.background, 7.54),
        ContrastPair("onSurfaceVariant on surface", scheme.onSurfaceVariant, scheme.surface, 8.16),
        ContrastPair("onPrimary on primary", scheme.onPrimary, scheme.primary, 9.53),
        ContrastPair("primaryStrong on canvas", semantic.primaryStrong, scheme.background, 11.72),
        ContrastPair("primary label on canvas", scheme.primary, scheme.background, 8.80),
        ContrastPair("primary label on surface", scheme.primary, scheme.surface, 9.53),
        ContrastPair("onSurface on surfaceVariant", scheme.onSurface, scheme.surfaceVariant, 12.84),
        ContrastPair("primary label on surfaceVariant", scheme.primary, scheme.surfaceVariant, 7.55),
        ContrastPair("caution on cautionSurface", semantic.caution, semantic.cautionSurface, 7.37),
        ContrastPair("caution on canvas", semantic.caution, scheme.background, 7.56),
        ContrastPair("caution on surface", semantic.caution, scheme.surface, 8.19),
        ContrastPair("onCaution on caution", semantic.onCaution, semantic.caution, 8.19),
        ContrastPair("error on surface", scheme.error, scheme.surface, 7.46),
        ContrastPair("error on canvas", scheme.error, scheme.background, 6.89),
        ContrastPair("onError on error", scheme.onError, scheme.error, 7.46),
        ContrastPair("error on errorContainer", scheme.error, scheme.errorContainer, 5.86),
        ContrastPair(
            "onErrorContainer on errorContainer",
            scheme.onErrorContainer,
            scheme.errorContainer,
            9.18,
        ),
        ContrastPair(
            "onPrimaryContainer on primaryContainer",
            scheme.onPrimaryContainer,
            scheme.primaryContainer,
            9.53,
        ),
        ContrastPair(
            "onSecondaryContainer on secondaryContainer",
            scheme.onSecondaryContainer,
            scheme.secondaryContainer,
            9.81,
        ),
        ContrastPair("onSecondary on secondary", scheme.onSecondary, scheme.secondary, 8.16),
        ContrastPair("onTertiary on tertiary", scheme.onTertiary, scheme.tertiary, 7.93),
        ContrastPair(
            "onTertiaryContainer on tertiaryContainer",
            scheme.onTertiaryContainer,
            scheme.tertiaryContainer,
            10.68,
        ),
        ContrastPair("inverseOnSurface on inverseSurface", scheme.inverseOnSurface, scheme.inverseSurface, 11.47),
        ContrastPair("inversePrimary on inverseSurface", scheme.inversePrimary, scheme.inverseSurface, 7.06),
        ContrastPair(
            "onSurface on surfaceContainerLowest",
            scheme.onSurface,
            scheme.surfaceContainerLowest,
            16.19,
        ),
        ContrastPair("onSurface on surfaceContainerLow", scheme.onSurface, scheme.surfaceContainerLow, 15.63),
        ContrastPair("onSurface on surfaceContainer", scheme.onSurface, scheme.surfaceContainer, 14.20),
        ContrastPair("onSurface on surfaceContainerHigh", scheme.onSurface, scheme.surfaceContainerHigh, 13.57),
        ContrastPair(
            "onSurface on surfaceContainerHighest",
            scheme.onSurface,
            scheme.surfaceContainerHighest,
            12.84,
        ),
        ContrastPair("onSurface on surfaceDim", scheme.onSurface, scheme.surfaceDim, 11.90),
        ContrastPair("onSurface on surfaceBright", scheme.onSurface, scheme.surfaceBright, 16.16),
        ContrastPair(
            "onSurfaceVariant on surfaceContainerHighest",
            scheme.onSurfaceVariant,
            scheme.surfaceContainerHighest,
            6.47,
        ),
    )

    private fun nonTextContrastPairs(): List<ContrastPair> = listOf(
        ContrastPair("outline on canvas", scheme.outline, scheme.background, 3.91),
        ContrastPair("outline on surface", scheme.outline, scheme.surface, 4.23),
        ContrastPair("outlineVariant on canvas", scheme.outlineVariant, scheme.background, 3.55),
        ContrastPair("outlineVariant on surface", scheme.outlineVariant, scheme.surface, 3.84),
        ContrastPair("outlineVariant on surfaceVariant", scheme.outlineVariant, scheme.surfaceVariant, 3.05),
        ContrastPair(
            "outlineVariant on surfaceContainer",
            scheme.outlineVariant,
            scheme.surfaceContainer,
            3.37,
        ),
        ContrastPair("primary vs canvas", scheme.primary, scheme.background, 8.80),
        ContrastPair("error vs canvas", scheme.error, scheme.background, 6.89),
        ContrastPair("caution vs cautionSurface", semantic.caution, semantic.cautionSurface, 7.37),
    )

    // ---------------------------------------------------------------------------------------
    // Semantic colours
    // ---------------------------------------------------------------------------------------

    @Test
    fun `semantic colours expose caution, on-caution, caution surface and the strong olive`() {
        assertEquals(ManijeroCaution, semantic.caution)
        assertEquals(ManijeroSurface, semantic.onCaution)
        assertEquals(ManijeroCautionSurface, semantic.cautionSurface)
        assertEquals(ManijeroOlive900, semantic.primaryStrong)
    }

    @Test
    fun `danger is the scheme error role and caution stays a separate value`() {
        assertNotEquals(
            semantic.caution,
            scheme.error,
            "danger must come from colorScheme.error, never from the caution token",
        )
    }

    // ---------------------------------------------------------------------------------------
    // WCAG helper
    // ---------------------------------------------------------------------------------------

    @Test
    fun `relative luminance anchors at black and white`() {
        assertEquals(0.0, relativeLuminance(Color(0xFF000000)), "black luminance")
        assertEquals(1.0, relativeLuminance(Color(0xFFFFFFFF)), "white luminance")
    }

    @Test
    fun `contrast ratio anchors at 21 to 1 and 1 to 1 and is symmetric`() {
        val black = Color(0xFF000000)
        val white = Color(0xFFFFFFFF)

        assertEquals(21.0, contrastRatio(black, white), ABSOLUTE_TOLERANCE, "black on white")
        assertEquals(1.0, contrastRatio(white, white), ABSOLUTE_TOLERANCE, "same colour")
        assertEquals(
            contrastRatio(ManijeroDanger, ManijeroCanvas),
            contrastRatio(ManijeroCanvas, ManijeroDanger),
            ABSOLUTE_TOLERANCE,
            "argument order must not change the ratio",
        )
    }

    // ---------------------------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------------------------

    private data class RoleComparison(
        val name: String,
        val actual: Color,
        val materialDefault: Color,
    )

    private data class ContrastPair(
        val name: String,
        val foreground: Color,
        val background: Color,
        val documentedRatio: Double,
    )

    private fun assertDocumentedContrast(pairs: List<ContrastPair>, minimum: Double) {
        pairs.forEach { pair ->
            val measured = contrastRatio(pair.foreground, pair.background)
            assertTrue(
                measured >= minimum,
                "${pair.name}: measured ${roundToTwoDecimals(measured)}:1, required $minimum:1",
            )
            assertEquals(
                pair.documentedRatio,
                roundToTwoDecimals(measured),
                "${pair.name}: measured ratio must match the documented value",
            )
        }
    }

    private fun assertToken(name: String, expected: Color, actual: Color) {
        assertEquals(expected, actual, "token $name must ship the documented value")
    }

    private fun assertRole(role: String, expected: Color, actual: Color) {
        assertEquals(expected, actual, "color scheme role $role must be the documented value")
    }

    private companion object {
        const val MINIMUM_TEXT_CONTRAST = 4.5
        const val MINIMUM_NON_TEXT_CONTRAST = 3.0
        const val ABSOLUTE_TOLERANCE = 0.0001

        fun roundToTwoDecimals(value: Double): Double = round(value * 100) / 100
    }
}
