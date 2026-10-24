package com.jamarglex.manijero.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.sp
import kotlin.test.Test
import kotlin.test.assertEquals

class ManijeroTypographyTest {
    @Test
    fun everyMaterialRolePreservesDefaultSizeWeightAndFamilyAndOnlyBodySmallLineHeightChanges() {
        val baseline = Typography()
        val themed = ManijeroTypography
        val baselineRoles = baseline.roles()
        val themedRoles = themed.roles()
        assertEquals(baselineRoles.keys, themedRoles.keys)

        baselineRoles.forEach { (role, default) ->
            val actual = themedRoles.getValue(role)
            assertEquals(default.fontSize, actual.fontSize, "$role size")
            assertEquals(default.fontWeight, actual.fontWeight, "$role weight")
            assertEquals(default.fontFamily, actual.fontFamily, "$role family (font gate deferred)")
            val expectedLineHeight = if (role == "bodySmall") 18.sp else default.lineHeight
            assertEquals(expectedLineHeight, actual.lineHeight, "$role line height")
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
}
