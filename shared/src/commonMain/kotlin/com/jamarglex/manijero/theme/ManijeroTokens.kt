package com.jamarglex.manijero.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/** Common shape, spacing, icon, and layout scales translated from Stitch's tokens. */
object ManijeroShapes {
    val Small = RoundedCornerShape(4.dp)
    val Medium = RoundedCornerShape(12.dp)
    val Large = RoundedCornerShape(16.dp)
    val ExtraLarge = RoundedCornerShape(24.dp)
    val Material = Shapes(small = Small, medium = Medium, large = Large, extraLarge = ExtraLarge)
}

object ManijeroSpacing {
    val ExtraSmall = 6.dp
    val Small = 12.dp
    val Medium = 24.dp
    val Large = 32.dp
    val ExtraLarge = 48.dp

    /** Four-dp grid steps for the rhythm inside a component (the block scale stays above). */
    val Micro = 4.dp
    val Compact = 8.dp
    val Comfortable = 16.dp
}

/** Icon sizes on the 24 dp grid; interactive icons still need [ManijeroLayout.MinTouchTarget]. */
object ManijeroIconSize {
    /** Icon inline with text. */
    val Inline = 20.dp

    /** Default UI icon. */
    val Default = 24.dp

    /** Brand mark and other prominent marks. */
    val Large = 32.dp
}

object ManijeroLayout {
    /** Maximum width of the centred content column on wide windows. */
    val ContentMaxWidth = 720.dp

    val ScreenPaddingHorizontal = 24.dp
    val ScreenPaddingHorizontalWide = 40.dp
    val ScreenPaddingVertical = 32.dp

    /** Hairline borders and dividers. */
    val BorderWidth = 1.dp

    /** Minimum interactive target on every host, including Desktop pointer use. */
    val MinTouchTarget = 48.dp
}
