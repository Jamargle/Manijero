package com.jamarglex.manijero.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.unit.sp

/**
 * Typography preserves the platform default family: font bundling is explicitly deferred pending
 * provenance and redistribution approval. Scalable Material roles remain the shared hierarchy.
 *
 * The single override is `bodySmall`: its 12sp size is the smallest text in the app (text-field
 * labels, supporting text, and validation errors), and Material's 16sp line height is cramped for
 * accented Spanish at that size. `DESIGN.md` asks for a generous line height and support for platform
 * text scaling, so the line height grows to 18sp (1.5x) while the size stays untouched.
 */
internal val ManijeroTypography: Typography = Typography().let { baseline ->
    baseline.copy(bodySmall = baseline.bodySmall.copy(lineHeight = 18.sp))
}
