package com.jamarglex.manijero.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.sp
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

/**
 * Guards the typography rules the feature spec documents: one deliberate `bodySmall` line-height
 * override, a generous line height on the prose roles, and the platform system font family (no
 * bundled font asset). Pure computation: no composition, no resources.
 */
class ManijeroTypographyTest {

    @Test
    fun `body small keeps the documented eighteen sp line height and twelve sp size`() {
        assertEquals(18.sp, ManijeroTypography.bodySmall.lineHeight)
        assertEquals(12.sp, ManijeroTypography.bodySmall.fontSize, "the size must stay untouched")
    }

    @Test
    fun `prose and label roles keep a generous line height`() {
        val ruled = listOf(
            "bodyLarge" to ManijeroTypography.bodyLarge,
            "bodyMedium" to ManijeroTypography.bodyMedium,
            "bodySmall" to ManijeroTypography.bodySmall,
            "labelLarge" to ManijeroTypography.labelLarge,
        )

        ruled.forEach { (name, style) ->
            val ratio = style.lineHeight.value / style.fontSize.value
            assertTrue(
                ratio >= MINIMUM_LINE_HEIGHT_RATIO,
                "$name: line height ratio $ratio must be at least $MINIMUM_LINE_HEIGHT_RATIO",
            )
        }
    }

    @Test
    fun `only body small departs from the Material baseline`() {
        val baseline = Typography().roles()
        val themed = ManijeroTypography.roles()

        assertEquals(baseline.keys, themed.keys)
        baseline.forEach { (role, baselineStyle) ->
            if (role == "bodySmall") return@forEach
            assertEquals(
                baselineStyle,
                themed.getValue(role),
                "role $role must keep the Material 3 baseline",
            )
        }
        assertNotEquals(
            baseline.getValue("bodySmall"),
            themed.getValue("bodySmall"),
            "bodySmall is the one documented override",
        )
    }

    @Test
    fun `every role keeps a platform system font family`() {
        // Material's baseline uses the platform sans (SansSerif on Compose Multiplatform; Default is
        // the same system family). A bundled family would be a FontFamily(file...) and fails here.
        val platformFamilies = setOf<FontFamily?>(FontFamily.Default, FontFamily.SansSerif, null)

        ManijeroTypography.roles().forEach { (role, style) ->
            assertTrue(
                style.fontFamily in platformFamilies,
                "role $role must keep the platform system sans, not a bundled font family",
            )
        }
    }

    private fun Typography.roles(): Map<String, TextStyle> = mapOf(
        "displayLarge" to displayLarge,
        "displayMedium" to displayMedium,
        "displaySmall" to displaySmall,
        "headlineLarge" to headlineLarge,
        "headlineMedium" to headlineMedium,
        "headlineSmall" to headlineSmall,
        "titleLarge" to titleLarge,
        "titleMedium" to titleMedium,
        "titleSmall" to titleSmall,
        "bodyLarge" to bodyLarge,
        "bodyMedium" to bodyMedium,
        "bodySmall" to bodySmall,
        "labelLarge" to labelLarge,
        "labelMedium" to labelMedium,
        "labelSmall" to labelSmall,
    )

    private companion object {
        const val MINIMUM_LINE_HEIGHT_RATIO = 1.4
    }
}
