package com.jamarglex.manijero.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/** Common shape and spacing scales translated from Stitch's rounded and spacing tokens. */
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
}
