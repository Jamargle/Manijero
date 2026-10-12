package com.jamarglex.manijero.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.unit.sp

/**
 * Manijero typography: the Material 3 baseline, which already resolves to the platform system
 * sans-serif through `FontFamily.Default`. No font asset, family, size, weight, or letter spacing is
 * introduced.
 *
 * The single override is `bodySmall`: its 12sp size is the smallest text in the app (text-field
 * labels, supporting text, and validation errors), and Material's 16sp line height is cramped for
 * accented Spanish at that size. `DESIGN.md` asks for a generous line height and support for platform
 * text scaling, so the line height grows to 18sp (1.5x) while the size stays untouched.
 */
internal val ManijeroTypography: Typography = Typography().let { baseline ->
    baseline.copy(bodySmall = baseline.bodySmall.copy(lineHeight = 18.sp))
}
