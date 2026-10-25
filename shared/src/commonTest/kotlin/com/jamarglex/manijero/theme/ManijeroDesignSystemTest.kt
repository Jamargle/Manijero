package com.jamarglex.manijero.theme

import androidx.compose.ui.graphics.Color
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class ManijeroDesignSystemTest {
    @Test
    fun explicitAppearanceSelectsTheCorrespondingScheme() {
        assertEquals(ManijeroLightColorScheme, selectManijeroColorScheme(darkTheme = false))
        assertEquals(ManijeroDarkColorScheme, selectManijeroColorScheme(darkTheme = true))
    }

    @Test
    fun everyDocumentedLightRoleIsExplicit() {
        assertEquals(
            listOf(
                Color(0xFF214624), Color.White, Color(0xFF385E39), Color(0xFFABD6A7), Color(0xFFA7D2A3),
                Color(0xFF7E562E), Color.White, Color(0xFFFDC796), Color(0xFF79512A), Color(0xFF602E40),
                Color.White, Color(0xFF7B4557), Color(0xFFFEB7CC), Color(0xFFF9FAF4), Color(0xFF1A1C19),
                Color(0xFFF9FAF4), Color(0xFF1A1C19), Color(0xFFE2E3DD), Color(0xFF424940), Color(0xFF416741),
                Color(0xFF2F312D), Color(0xFFF1F1EB), Color(0xFFBA1A1A), Color.White, Color(0xFFFFDAD6),
                Color(0xFF93000A), Color(0xFF72796F), Color(0xFF757C71), Color.Black, Color(0xFFF9FAF4),
                Color(0xFFDADAD5), Color.White, Color(0xFFF3F4EE), Color(0xFFEEEEE9), Color(0xFFE8E9E3),
                Color(0xFFE2E3DD),
            ),
            roles(ManijeroLightColorScheme),
        )
    }

    @Test
    fun everyDocumentedDarkRoleIsExplicit() {
        assertEquals(
            listOf(
                Color(0xFF85A886), Color(0xFF0D1B0E), Color(0xFF283C29), Color(0xFFCFE8CF), Color(0xFF456648),
                Color(0xFFD4C5A9), Color(0xFF382E1C), Color(0xFF4F422E), Color(0xFFF1E5CC), Color(0xFFB8C5D6),
                Color(0xFF222D3B), Color(0xFF93A0B0), Color(0xFF2B3745), Color(0xFF121612), Color(0xFFE1E3DF),
                Color(0xFF121612), Color(0xFFE1E3DF), Color(0xFF333532), Color(0xFFC2C8BF), Color(0xFFABD0AC),
                Color(0xFFE3E3DE), Color(0xFF2F312E), Color(0xFFFFB4AB), Color(0xFF690005), Color(0xFF93000A),
                Color(0xFFFFDAD6), Color(0xFF8C948C), Color(0xFF868E86), Color.Black, Color(0xFF242C24),
                Color(0xFF1A201B), Color(0xFF0D100D), Color(0xFF181E18), Color(0xFF202820), Color(0xFF2C362C),
                Color(0xFF384438),
            ),
            roles(ManijeroDarkColorScheme),
        )
    }

    @Test
    fun sharedGeometryTokensMatchTheDocumentedScale() {
        assertEquals(6f, ManijeroSpacing.ExtraSmall.value)
        assertEquals(12f, ManijeroSpacing.Small.value)
        assertEquals(24f, ManijeroSpacing.Medium.value)
        assertEquals(32f, ManijeroSpacing.Large.value)
        assertEquals(48f, ManijeroSpacing.ExtraLarge.value)
        assertEquals(4f, ManijeroSpacing.Micro.value)
        assertEquals(8f, ManijeroSpacing.Compact.value)
        assertEquals(16f, ManijeroSpacing.Comfortable.value)

        assertEquals(20f, ManijeroIconSize.Inline.value)
        assertEquals(24f, ManijeroIconSize.Default.value)
        assertEquals(32f, ManijeroIconSize.Large.value)

        assertEquals(720f, ManijeroLayout.ContentMaxWidth.value)
        assertEquals(24f, ManijeroLayout.ScreenPaddingHorizontal.value)
        assertEquals(40f, ManijeroLayout.ScreenPaddingHorizontalWide.value)
        assertEquals(32f, ManijeroLayout.ScreenPaddingVertical.value)
        assertEquals(1f, ManijeroLayout.BorderWidth.value)
        assertEquals(48f, ManijeroLayout.MinTouchTarget.value)

        assertEquals(ManijeroShapes.Small, ManijeroShapes.Material.small)
        assertEquals(ManijeroShapes.Medium, ManijeroShapes.Material.medium)
        assertEquals(ManijeroShapes.Large, ManijeroShapes.Material.large)
        assertEquals(ManijeroShapes.ExtraLarge, ManijeroShapes.Material.extraLarge)
        assertNotEquals(ManijeroShapes.Small, ManijeroShapes.Large)
    }

    private fun roles(s: androidx.compose.material3.ColorScheme) = listOf(
        s.primary, s.onPrimary, s.primaryContainer, s.onPrimaryContainer, s.inversePrimary, s.secondary,
        s.onSecondary, s.secondaryContainer, s.onSecondaryContainer, s.tertiary, s.onTertiary,
        s.tertiaryContainer, s.onTertiaryContainer, s.background, s.onBackground, s.surface, s.onSurface,
        s.surfaceVariant, s.onSurfaceVariant, s.surfaceTint, s.inverseSurface, s.inverseOnSurface, s.error,
        s.onError, s.errorContainer, s.onErrorContainer, s.outline, s.outlineVariant, s.scrim,
        s.surfaceBright, s.surfaceDim, s.surfaceContainerLowest, s.surfaceContainerLow,
        s.surfaceContainer, s.surfaceContainerHigh, s.surfaceContainerHighest,
    )
}
