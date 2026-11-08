package com.jamarglex.manijero.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

/**
 * Common shape, spacing, icon, and layout scales translated from Stitch's tokens.
 *
 * The shape scale follows the Stitch V2 screens: soft 24 dp cards, 32 dp hero containers, 16 dp
 * nested tiles and fields, and pill-shaped chips, search and composer fields. Material components
 * that read the theme (text fields, menus, dialogs) inherit the same scale through [Material].
 */
object ManijeroShapes {
    val Small = RoundedCornerShape(8.dp)
    val Medium = RoundedCornerShape(16.dp)
    val Large = RoundedCornerShape(24.dp)
    val ExtraLarge = RoundedCornerShape(32.dp)

    /** Text fields and menus: rounded enough to match the cards without crowding the label notch. */
    val Field = RoundedCornerShape(16.dp)

    /** Chips, single-line search fields and the chat composer. */
    val Pill = RoundedCornerShape(percent = 50)

    /** Corner kept tight where a chat bubble meets its speaker's side of the column. */
    private val BubbleTail = 6.dp

    /** The person's own entry: rounded everywhere except the top corner on their (end) side. */
    val BubbleOwn = RoundedCornerShape(
        topStart = 24.dp,
        topEnd = BubbleTail,
        bottomEnd = 24.dp,
        bottomStart = 24.dp,
    )

    /** An assistant entry: rounded everywhere except the top corner on the assistant (start) side. */
    val BubbleAssistant = RoundedCornerShape(
        topStart = BubbleTail,
        topEnd = 24.dp,
        bottomEnd = 24.dp,
        bottomStart = 24.dp,
    )

    val Material = Shapes(
        extraSmall = Field,
        small = Small,
        medium = Medium,
        large = Large,
        extraLarge = ExtraLarge,
    )
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
