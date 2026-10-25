package com.jamarglex.manijero.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import kotlin.math.round
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * Guards the shipped palette: the exact `DESIGN.md` token values, the semantic colours, "no Material
 * default leaked", and every WCAG ratio documented in `DESIGN.md`'s contrast contract, in both
 * appearances.
 *
 * Pure computation: no composition, no I/O, no resources.
 */
class ManijeroColorsTest {

    private val light: ColorScheme = ManijeroLightColorScheme
    private val dark: ColorScheme = ManijeroDarkColorScheme
    private val lightSemantic = ManijeroLightSemanticColors
    private val darkSemantic = ManijeroDarkSemanticColors

    // ---------------------------------------------------------------------------------------
    // Tokens
    // ---------------------------------------------------------------------------------------

    @Test
    fun `light tokens ship the exact documented values`() {
        assertToken("primary / olive-800", Color(0xFF214624), ManijeroOlive800)
        assertToken("primaryStrong / olive-900", Color(0xFF263724), ManijeroOlive900)
        assertToken("canvas", Color(0xFFF9FAF4), ManijeroCanvas)
        assertToken("surface", Color(0xFFFFFFFF), ManijeroSurface)
        assertToken("text-primary", Color(0xFF1A1C19), ManijeroTextPrimary)
        assertToken("text-secondary", Color(0xFF424940), ManijeroTextSecondary)
        assertToken("border", Color(0xFF72796F), ManijeroBorder)
        assertToken("outlineVariant (corrected)", Color(0xFF757C71), ManijeroOutlineVariant)
        assertToken("caution", Color(0xFF704600), ManijeroCaution)
        assertToken("caution-surface", Color(0xFFFFF2D4), ManijeroCautionSurface)
        assertToken("danger", Color(0xFFBA1A1A), ManijeroDanger)
        assertToken("scrim", Color(0xFF000000), ManijeroScrim)
    }

    /**
     * Stitch sets `background`, `surface`, and `surfaceBright` to the same light value, so the
     * Material `surface` role must be the canvas and raised cards must read `surfaceContainerLowest`.
     */
    @Test
    fun `light surface role is the canvas and cards use the white container`() {
        assertRole("background", ManijeroCanvas, light.background)
        assertRole("surface", ManijeroCanvas, light.surface)
        assertRole("surfaceBright", ManijeroCanvas, light.surfaceBright)
        assertRole("surfaceContainerLowest", ManijeroSurface, light.surfaceContainerLowest)
        assertRole("onPrimary", ManijeroWhite, light.onPrimary)
        assertRole("onError", ManijeroWhite, light.onError)
    }

    @Test
    fun `dark scheme ships the documented values`() {
        assertRole("primary", Color(0xFF85A886), dark.primary)
        assertRole("secondary", Color(0xFFD4C5A9), dark.secondary)
        assertRole("tertiary", Color(0xFFB8C5D6), dark.tertiary)
        assertRole("background", Color(0xFF121612), dark.background)
        assertRole("surface", Color(0xFF121612), dark.surface)
        assertRole("surfaceContainerLowest", Color(0xFF0D100D), dark.surfaceContainerLowest)
        assertRole("error", Color(0xFFFFB4AB), dark.error)
        assertRole("outline", Color(0xFF8C948C), dark.outline)
        assertRole("outlineVariant (corrected)", Color(0xFF868E86), dark.outlineVariant)
        assertRole("scrim", ManijeroScrim, dark.scrim)
    }

    // ---------------------------------------------------------------------------------------
    // Mapping
    // ---------------------------------------------------------------------------------------

    /**
     * Compared against the Material default scheme computed at runtime, so a future Material release
     * that changes its defaults cannot make an unset role silently look "correct".
     *
     * Excluded: the four white light on-colours and light `surfaceContainerLowest` (documented white,
     * Material's default is white too) and `scrim` (documented as the unchanged Material black).
     */
    @Test
    fun `no brand-bearing role falls back to the Material light default`() {
        assertNoMaterialDefault(
            scheme = light,
            defaults = lightColorScheme(),
            intentionallyDefault = setOf(
                "onPrimary",
                "onSecondary",
                "onTertiary",
                "onError",
                "surfaceContainerLowest",
                "scrim",
            ),
        )
    }

    @Test
    fun `no brand-bearing role falls back to the Material dark default`() {
        assertNoMaterialDefault(
            scheme = dark,
            defaults = darkColorScheme(),
            intentionallyDefault = setOf("scrim"),
        )
    }

    // ---------------------------------------------------------------------------------------
    // Contrast (WCAG AA)
    // ---------------------------------------------------------------------------------------

    @Test
    fun `light text pairs meet 4 point 5 to 1 and match the document`() {
        assertDocumentedContrast(lightTextPairs(), MINIMUM_TEXT_CONTRAST)
    }

    @Test
    fun `dark text pairs meet 4 point 5 to 1 and match the document`() {
        assertDocumentedContrast(darkTextPairs(), MINIMUM_TEXT_CONTRAST)
    }

    @Test
    fun `light non-text pairs meet 3 to 1 and match the document`() {
        assertDocumentedContrast(lightNonTextPairs(), MINIMUM_NON_TEXT_CONTRAST)
    }

    @Test
    fun `dark non-text pairs meet 3 to 1 and match the document`() {
        assertDocumentedContrast(darkNonTextPairs(), MINIMUM_NON_TEXT_CONTRAST)
    }

    /** Chips reuse Stitch role pairs; the Ecológico pair is the only semantic chip value. */
    @Test
    fun `land attribute chips clear text contrast in both appearances`() {
        val pairs = listOf(
            chip("light Secano", light.secondaryContainer, light.onSecondaryContainer, 4.56),
            chip("light Regadío", light.primaryContainer, light.onPrimaryContainer, 4.56),
            chip("light Ecológico", lightSemantic.ecoContainer, lightSemantic.onEcoContainer, 13.33),
            chip("light Neutral", light.surfaceContainerHighest, light.onSurface, 13.29),
            chip("dark Secano", dark.secondaryContainer, dark.onSecondaryContainer, 7.82),
            chip("dark Regadío", dark.primaryContainer, dark.onPrimaryContainer, 9.10),
            chip("dark Ecológico", darkSemantic.ecoContainer, darkSemantic.onEcoContainer, 13.26),
            chip("dark Neutral", dark.surfaceContainerHighest, dark.onSurface, 7.92),
        )

        assertDocumentedContrast(pairs, MINIMUM_TEXT_CONTRAST)

        assertEquals(Color(0xFFFDC796), light.secondaryContainer)
        assertEquals(Color(0xFF79512A), light.onSecondaryContainer)
        assertEquals(Color(0xFF385E39), light.primaryContainer)
        assertEquals(Color(0xFFABD6A7), light.onPrimaryContainer)
        assertEquals(Color(0xFFC2EEBE), lightSemantic.ecoContainer)
        assertEquals(Color(0xFF002106), lightSemantic.onEcoContainer)
        assertEquals(Color(0xFF4F422E), dark.secondaryContainer)
        assertEquals(Color(0xFFF1E5CC), dark.onSecondaryContainer)
        assertEquals(Color(0xFF283C29), dark.primaryContainer)
        assertEquals(Color(0xFFCFE8CF), dark.onPrimaryContainer)
        assertEquals(Color(0xFFC7ECC6), darkSemantic.ecoContainer)
        assertEquals(Color(0xFF02210A), darkSemantic.onEcoContainer)
    }

    // ---------------------------------------------------------------------------------------
    // Semantic colours
    // ---------------------------------------------------------------------------------------

    @Test
    fun `semantic colours expose caution, on-caution, caution surface and the strong olive`() {
        assertEquals(ManijeroCaution, lightSemantic.caution)
        assertEquals(ManijeroWhite, lightSemantic.onCaution)
        assertEquals(ManijeroCautionSurface, lightSemantic.cautionSurface)
        assertEquals(ManijeroOlive900, lightSemantic.primaryStrong)

        assertEquals(Color(0xFFFFD18A), darkSemantic.caution)
        assertEquals(Color(0xFF3A2600), darkSemantic.onCaution)
        assertEquals(Color(0xFF4B350D), darkSemantic.cautionSurface)
        assertEquals(Color(0xFFCFE8CF), darkSemantic.primaryStrong)
    }

    @Test
    fun `danger is the scheme error role and caution stays a separate value`() {
        assertNotEquals(
            lightSemantic.caution,
            light.error,
            "danger must come from colorScheme.error, never from the caution token",
        )
        assertNotEquals(darkSemantic.caution, dark.error)
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
    // Documented pairs (mirror of DESIGN.md "Contrast contract"; a value change must recompute them)
    // ---------------------------------------------------------------------------------------

    private fun lightTextPairs(): List<ContrastPair> = listOf(
        pair("onSurface on background", light.onSurface, light.background, 16.35),
        pair("onSurface on surfaceContainerLowest", light.onSurface, light.surfaceContainerLowest, 17.16),
        pair("onSurface on surfaceContainerLow", light.onSurface, light.surfaceContainerLow, 15.51),
        pair("onSurface on surfaceContainer", light.onSurface, light.surfaceContainer, 14.74),
        pair("onSurface on surfaceContainerHigh", light.onSurface, light.surfaceContainerHigh, 14.05),
        pair("onSurface on surfaceContainerHighest", light.onSurface, light.surfaceContainerHighest, 13.29),
        pair("onSurface on surfaceDim", light.onSurface, light.surfaceDim, 12.23),
        pair("onSurfaceVariant on background", light.onSurfaceVariant, light.background, 8.86),
        pair("onSurfaceVariant on surfaceContainerLowest", light.onSurfaceVariant, light.surfaceContainerLowest, 9.30),
        pair("onSurfaceVariant on surfaceContainerLow", light.onSurfaceVariant, light.surfaceContainerLow, 8.41),
        pair("onSurfaceVariant on surfaceContainer", light.onSurfaceVariant, light.surfaceContainer, 7.99),
        pair("onSurfaceVariant on surfaceContainerHigh", light.onSurfaceVariant, light.surfaceContainerHigh, 7.61),
        pair("onSurfaceVariant on surfaceContainerHighest", light.onSurfaceVariant, light.surfaceContainerHighest, 7.20),
        pair("onSurfaceVariant on surfaceDim", light.onSurfaceVariant, light.surfaceDim, 6.63),
        pair("onPrimary on primary", light.onPrimary, light.primary, 10.68),
        pair("onPrimaryContainer on primaryContainer", light.onPrimaryContainer, light.primaryContainer, 4.56),
        pair("secondary on background", light.secondary, light.background, 6.14),
        pair("onSecondary on secondary", light.onSecondary, light.secondary, 6.45),
        pair("onSecondaryContainer on secondaryContainer", light.onSecondaryContainer, light.secondaryContainer, 4.56),
        pair("tertiary on background", light.tertiary, light.background, 10.20),
        pair("onTertiary on tertiary", light.onTertiary, light.tertiary, 10.70),
        pair("onTertiaryContainer on tertiaryContainer", light.onTertiaryContainer, light.tertiaryContainer, 4.54),
        pair("primaryStrong on background", lightSemantic.primaryStrong, light.background, 12.09),
        pair("caution on cautionSurface", lightSemantic.caution, lightSemantic.cautionSurface, 7.37),
        pair("caution on background", lightSemantic.caution, light.background, 7.80),
        pair("caution on surfaceContainerLowest", lightSemantic.caution, light.surfaceContainerLowest, 8.19),
        pair("onCaution on caution", lightSemantic.onCaution, lightSemantic.caution, 8.19),
        pair("error on background", light.error, light.background, 6.16),
        pair("error on surfaceContainerLowest", light.error, light.surfaceContainerLowest, 6.46),
        pair("error on surfaceVariant", light.error, light.surfaceVariant, 5.00),
        pair("onError on error", light.onError, light.error, 6.46),
        pair("error on errorContainer", light.error, light.errorContainer, 5.00),
        pair("onErrorContainer on errorContainer", light.onErrorContainer, light.errorContainer, 7.24),
        pair("inverseOnSurface on inverseSurface", light.inverseOnSurface, light.inverseSurface, 11.59),
        pair("inversePrimary on inverseSurface", light.inversePrimary, light.inverseSurface, 7.75),
    )

    private fun lightNonTextPairs(): List<ContrastPair> = listOf(
        pair("outline on background", light.outline, light.background, 4.28),
        pair("outline on surfaceContainerLowest", light.outline, light.surfaceContainerLowest, 4.49),
        pair("outline on surfaceVariant", light.outline, light.surfaceVariant, 3.48),
        pair("outlineVariant on background", light.outlineVariant, light.background, 4.10),
        pair("outlineVariant on surfaceContainerLowest", light.outlineVariant, light.surfaceContainerLowest, 4.31),
        pair("outlineVariant on surfaceContainerLow", light.outlineVariant, light.surfaceContainerLow, 3.89),
        pair("outlineVariant on surfaceContainer", light.outlineVariant, light.surfaceContainer, 3.70),
        pair("outlineVariant on surfaceContainerHigh", light.outlineVariant, light.surfaceContainerHigh, 3.53),
        pair("outlineVariant on surfaceContainerHighest", light.outlineVariant, light.surfaceContainerHighest, 3.33),
        pair("outlineVariant on surfaceDim", light.outlineVariant, light.surfaceDim, 3.07),
        pair("primary on background", light.primary, light.background, 10.18),
        pair("error on background", light.error, light.background, 6.16),
    )

    private fun darkTextPairs(): List<ContrastPair> = listOf(
        pair("onSurface on background", dark.onSurface, dark.background, 14.14),
        pair("onSurface on surfaceContainerLowest", dark.onSurface, dark.surfaceContainerLowest, 14.82),
        pair("onSurface on surfaceContainerLow", dark.onSurface, dark.surfaceContainerLow, 13.13),
        pair("onSurface on surfaceContainer", dark.onSurface, dark.surfaceContainer, 11.73),
        pair("onSurface on surfaceContainerHigh", dark.onSurface, dark.surfaceContainerHigh, 9.73),
        pair("onSurface on surfaceContainerHighest", dark.onSurface, dark.surfaceContainerHighest, 7.92),
        pair("onSurface on surfaceDim", dark.onSurface, dark.surfaceDim, 12.84),
        pair("onSurfaceVariant on background", dark.onSurfaceVariant, dark.background, 10.71),
        pair("onSurfaceVariant on surfaceVariant", dark.onSurfaceVariant, dark.surfaceVariant, 7.26),
        pair("onSurfaceVariant on surfaceContainerHighest", dark.onSurfaceVariant, dark.surfaceContainerHighest, 6.00),
        pair("onPrimary on primary", dark.onPrimary, dark.primary, 6.73),
        pair("primary on background", dark.primary, dark.background, 6.91),
        pair("onPrimaryContainer on primaryContainer", dark.onPrimaryContainer, dark.primaryContainer, 9.10),
        pair("secondary on background", dark.secondary, dark.background, 10.75),
        pair("onSecondary on secondary", dark.onSecondary, dark.secondary, 7.84),
        pair("onSecondaryContainer on secondaryContainer", dark.onSecondaryContainer, dark.secondaryContainer, 7.82),
        pair("tertiary on background", dark.tertiary, dark.background, 10.44),
        pair("onTertiary on tertiary", dark.onTertiary, dark.tertiary, 7.96),
        pair("onTertiaryContainer on tertiaryContainer", dark.onTertiaryContainer, dark.tertiaryContainer, 4.55),
        pair("primaryStrong on background", darkSemantic.primaryStrong, dark.background, 14.01),
        pair("error on background", dark.error, dark.background, 10.76),
        pair("onError on error", dark.onError, dark.error, 7.72),
        pair("error on errorContainer", dark.error, dark.errorContainer, 5.51),
        pair("onErrorContainer on errorContainer", dark.onErrorContainer, dark.errorContainer, 7.24),
        pair("caution on cautionSurface", darkSemantic.caution, darkSemantic.cautionSurface, 8.12),
        pair("caution on surfaceContainerLowest", darkSemantic.caution, dark.surfaceContainerLowest, 13.44),
        pair("onCaution on caution", darkSemantic.onCaution, darkSemantic.caution, 10.12),
        pair("inverseOnSurface on inverseSurface", dark.inverseOnSurface, dark.inverseSurface, 10.20),
        pair("inversePrimary on inverseSurface", dark.inversePrimary, dark.inverseSurface, 5.02),
    )

    private fun darkNonTextPairs(): List<ContrastPair> = listOf(
        pair("outline on background", dark.outline, dark.background, 5.86),
        pair("outline on surfaceVariant", dark.outline, dark.surfaceVariant, 3.97),
        pair("outlineVariant on background", dark.outlineVariant, dark.background, 5.42),
        pair("outlineVariant on surfaceContainerLowest", dark.outlineVariant, dark.surfaceContainerLowest, 5.68),
        pair("outlineVariant on surfaceContainerLow", dark.outlineVariant, dark.surfaceContainerLow, 5.03),
        pair("outlineVariant on surfaceContainer", dark.outlineVariant, dark.surfaceContainer, 4.49),
        pair("outlineVariant on surfaceContainerHigh", dark.outlineVariant, dark.surfaceContainerHigh, 3.73),
        pair("outlineVariant on surfaceContainerHighest", dark.outlineVariant, dark.surfaceContainerHighest, 3.03),
        pair("outlineVariant on surfaceDim", dark.outlineVariant, dark.surfaceDim, 4.92),
    )

    private fun pair(name: String, foreground: Color, background: Color, documentedRatio: Double) =
        ContrastPair(name, foreground, background, documentedRatio)

    private fun chip(name: String, container: Color, ink: Color, documentedRatio: Double) =
        ContrastPair(name, ink, container, documentedRatio)

    // ---------------------------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------------------------

    private data class ContrastPair(
        val name: String,
        val foreground: Color,
        val background: Color,
        val documentedRatio: Double,
    )

    private fun assertNoMaterialDefault(
        scheme: ColorScheme,
        defaults: ColorScheme,
        intentionallyDefault: Set<String>,
    ) {
        val actualRoles = roles(scheme)
        val defaultRoles = roles(defaults)

        actualRoles.keys.forEach { role ->
            if (role in intentionallyDefault) return@forEach
            assertNotEquals(
                defaultRoles.getValue(role),
                actualRoles.getValue(role),
                "role $role must not fall back to Material's default palette",
            )
        }
    }

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

    private fun roles(scheme: ColorScheme): Map<String, Color> = linkedMapOf(
        "primary" to scheme.primary,
        "onPrimary" to scheme.onPrimary,
        "primaryContainer" to scheme.primaryContainer,
        "onPrimaryContainer" to scheme.onPrimaryContainer,
        "inversePrimary" to scheme.inversePrimary,
        "secondary" to scheme.secondary,
        "onSecondary" to scheme.onSecondary,
        "secondaryContainer" to scheme.secondaryContainer,
        "onSecondaryContainer" to scheme.onSecondaryContainer,
        "tertiary" to scheme.tertiary,
        "onTertiary" to scheme.onTertiary,
        "tertiaryContainer" to scheme.tertiaryContainer,
        "onTertiaryContainer" to scheme.onTertiaryContainer,
        "background" to scheme.background,
        "onBackground" to scheme.onBackground,
        "surface" to scheme.surface,
        "onSurface" to scheme.onSurface,
        "surfaceVariant" to scheme.surfaceVariant,
        "onSurfaceVariant" to scheme.onSurfaceVariant,
        "surfaceTint" to scheme.surfaceTint,
        "inverseSurface" to scheme.inverseSurface,
        "inverseOnSurface" to scheme.inverseOnSurface,
        "error" to scheme.error,
        "onError" to scheme.onError,
        "errorContainer" to scheme.errorContainer,
        "onErrorContainer" to scheme.onErrorContainer,
        "outline" to scheme.outline,
        "outlineVariant" to scheme.outlineVariant,
        "scrim" to scheme.scrim,
        "surfaceBright" to scheme.surfaceBright,
        "surfaceDim" to scheme.surfaceDim,
        "surfaceContainerLowest" to scheme.surfaceContainerLowest,
        "surfaceContainerLow" to scheme.surfaceContainerLow,
        "surfaceContainer" to scheme.surfaceContainer,
        "surfaceContainerHigh" to scheme.surfaceContainerHigh,
        "surfaceContainerHighest" to scheme.surfaceContainerHighest,
    )

    private companion object {
        const val MINIMUM_TEXT_CONTRAST = 4.5
        const val MINIMUM_NON_TEXT_CONTRAST = 3.0
        const val ABSOLUTE_TOLERANCE = 0.0001

        fun roundToTwoDecimals(value: Double): Double = round(value * 100) / 100
    }
}
