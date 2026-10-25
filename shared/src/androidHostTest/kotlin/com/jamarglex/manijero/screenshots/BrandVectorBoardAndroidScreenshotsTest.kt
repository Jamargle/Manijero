package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.design.BrandVectorBoard
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Pixel regression captures for the review-only brand-vector board, rendered by Android through
 * Robolectric on the host JVM.
 *
 * This class pins the same 900 x 1200 dp viewport as the Desktop board so the two reviewed images
 * show the same composition on the two pinned host renderers. It is not a device or emulator
 * render and makes no accessibility or real-screen legibility claim.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "es-rES-w900dp-h1200dp-mdpi")
class BrandVectorBoardAndroidScreenshotsTest : AndroidScreenshotTestSupport() {

    /** The mark, the illustration, and the sixteen icons, light appearance. */
    @Test
    fun brandVectorBoardLight() =
        capture("brand_vector_board_light") {
            ManijeroTheme(darkTheme = false) { BrandVectorBoard() }
        }

    /** The same board, dark appearance. */
    @Test
    fun brandVectorBoardDark() =
        capture("brand_vector_board_dark") {
            ManijeroTheme(darkTheme = true) { BrandVectorBoard() }
        }
}
