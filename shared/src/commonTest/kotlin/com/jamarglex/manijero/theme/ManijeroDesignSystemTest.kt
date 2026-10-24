package com.jamarglex.manijero.theme

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import androidx.compose.ui.graphics.Color

class ManijeroDesignSystemTest {
    @Test
    fun explicitAppearanceSelectsTheCorrespondingScheme() {
        assertEquals(ManijeroLightColorScheme, selectManijeroColorScheme(darkTheme = false))
        assertEquals(ManijeroDarkColorScheme, selectManijeroColorScheme(darkTheme = true))
    }

    @Test
    fun everyDocumentedMaterialRoleIsExplicitAndContrastPairsPass() {
        val light = ManijeroLightColorScheme
        assertEquals(listOf(
            Color(0xFF354B32), Color.White, Color(0xFFD9E2D2), Color(0xFF263724), Color(0xFFB6C4AC),
            Color(0xFF4B5149), Color.White, Color(0xFFDFE4D8), Color(0xFF263724), Color(0xFF40573C),
            Color.White, Color(0xFFE9EDE2), Color(0xFF263724), Color(0xFFF7F6F0), Color(0xFF1D221B),
            Color.White, Color(0xFF1D221B), Color(0xFFE7E5DD), Color(0xFF4B5149), Color(0xFF354B32),
            Color(0xFF2E332C), Color(0xFFF1F2EC), Color(0xFFA12622), Color.White, Color(0xFFF9DEDA),
            Color(0xFF6E1714), Color(0xFF777D73), Color(0xFF7E8479), Color.Black, Color(0xFFFFFFFC),
            Color(0xFFDFDDD4), Color.White, Color(0xFFFCFBF6), Color(0xFFF2F0E9), Color(0xFFEDEBE3), Color(0xFFE7E5DD)
        ), roles(light))
        assertEquals(listOf(
            Color(0xFF85A886), Color(0xFF0D1B0E), Color(0xFF283C29), Color(0xFFCFE8CF), Color(0xFF456648),
            Color(0xFFD4C5A9), Color(0xFF382E1C), Color(0xFF4F422E), Color(0xFFF1E5CC), Color(0xFFB8C5D6),
            Color(0xFF222D3B), Color(0xFF93A0B0), Color(0xFF2B3745), Color(0xFF121612), Color(0xFFE1E3DF),
            Color(0xFF121612), Color(0xFFE1E3DF), Color(0xFF333532), Color(0xFFC2C8BF), Color(0xFFABD0AC),
            Color(0xFFE3E3DE), Color(0xFF2F312E), Color(0xFFFFB4AB), Color(0xFF690005), Color(0xFF93000A),
            Color(0xFFFFDAD6), Color(0xFF8C948C), Color(0xFF646B64), Color.Black, Color(0xFF242C24),
            Color(0xFF1A201B), Color(0xFF0D100D), Color(0xFF181E18), Color(0xFF202820), Color(0xFF2C362C), Color(0xFF384438)
        ), roles(ManijeroDarkColorScheme))
        listOf(ManijeroLightColorScheme, ManijeroDarkColorScheme).forEach { s ->
            val pairs = listOf(
                s.onPrimary to s.primary, s.onSecondary to s.secondary, s.onTertiary to s.tertiary,
                s.onBackground to s.background, s.onSurface to s.surface, s.onSurfaceVariant to s.surfaceVariant,
                s.onPrimaryContainer to s.primaryContainer, s.onSecondaryContainer to s.secondaryContainer,
                s.onTertiaryContainer to s.tertiaryContainer, s.inverseOnSurface to s.inverseSurface,
                s.onError to s.error, s.onErrorContainer to s.errorContainer,
                s.error to s.background, s.outline to s.surface, s.outline to s.background,
                s.outlineVariant to s.surface, s.outlineVariant to s.surfaceContainerLow,
                s.outline to s.surfaceVariant, s.primary to s.surface
            )
            pairs.forEachIndexed { index, (fg, bg) ->
                val threshold = if (index < 12) 4.5 else 3.0
                assertTrue(contrastRatio(fg, bg) >= threshold, "pair $index ratio ${contrastRatio(fg, bg)}")
            }
        }
        assertTrue(contrastRatio(ManijeroLightSemanticColors.caution, ManijeroLightColorScheme.background) >= 4.5)
        assertTrue(contrastRatio(ManijeroLightSemanticColors.caution, ManijeroLightColorScheme.surface) >= 4.5)
        assertTrue(contrastRatio(ManijeroLightSemanticColors.caution, ManijeroLightSemanticColors.cautionSurface) >= 4.5)
        assertEquals(Color(0xFF704600), ManijeroLightSemanticColors.caution)
        assertEquals(Color(0xFFFFD18A), ManijeroDarkSemanticColors.caution)
        assertEquals(Color.White, ManijeroLightSemanticColors.onCaution)
        assertEquals(Color(0xFF3A2600), ManijeroDarkSemanticColors.onCaution)
        assertEquals(Color(0xFFFFF2D4), ManijeroLightSemanticColors.cautionSurface)
        assertEquals(Color(0xFF4B350D), ManijeroDarkSemanticColors.cautionSurface)
        assertEquals(Color(0xFF263724), ManijeroLightSemanticColors.primaryStrong)
        assertEquals(Color(0xFFCFE8CF), ManijeroDarkSemanticColors.primaryStrong)
        assertTrue(contrastRatio(ManijeroDarkSemanticColors.caution, ManijeroDarkSemanticColors.cautionSurface) >= 4.5)
        assertTrue(contrastRatio(ManijeroLightSemanticColors.onCaution, ManijeroLightSemanticColors.caution) >= 4.5)
        assertTrue(contrastRatio(ManijeroDarkSemanticColors.onCaution, ManijeroDarkSemanticColors.caution) >= 4.5)
        assertTrue(contrastRatio(ManijeroLightSemanticColors.primaryStrong, ManijeroLightColorScheme.background) >= 4.5)
        assertTrue(contrastRatio(ManijeroDarkSemanticColors.primaryStrong, ManijeroDarkColorScheme.background) >= 4.5)
    }

    @Test
    fun semanticColorsAndSharedGeometryAreAvailable() {
        assertTrue(contrastRatio(ManijeroLightSemanticColors.caution, ManijeroLightSemanticColors.cautionSurface) >= 4.5)
        assertTrue(contrastRatio(ManijeroDarkSemanticColors.caution, ManijeroDarkSemanticColors.cautionSurface) >= 4.5)
        assertEquals(24, ManijeroSpacing.Medium.value.toInt())
        assertTrue(ManijeroShapes.Small != ManijeroShapes.Large)
    }

    private fun roles(s: androidx.compose.material3.ColorScheme) = listOf(
        s.primary,s.onPrimary,s.primaryContainer,s.onPrimaryContainer,s.inversePrimary,s.secondary,s.onSecondary,
        s.secondaryContainer,s.onSecondaryContainer,s.tertiary,s.onTertiary,s.tertiaryContainer,s.onTertiaryContainer,
        s.background,s.onBackground,s.surface,s.onSurface,s.surfaceVariant,s.onSurfaceVariant,s.surfaceTint,
        s.inverseSurface,s.inverseOnSurface,s.error,s.onError,s.errorContainer,s.onErrorContainer,s.outline,
        s.outlineVariant,s.scrim,s.surfaceBright,s.surfaceDim,s.surfaceContainerLowest,s.surfaceContainerLow,
        s.surfaceContainer,s.surfaceContainerHigh,s.surfaceContainerHighest
    )
}
