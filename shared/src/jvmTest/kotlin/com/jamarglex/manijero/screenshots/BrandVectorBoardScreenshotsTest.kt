package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.design.BrandVectorBoard
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/**
 * Pixel regression captures for the review-only brand-vector board: every vector in the set at the
 * sizes the contract publishes, once per appearance.
 *
 * The board is not a screen. These captures prove the eighteen vectors decode and take their colour
 * from the shared theme on the Compose Desktop renderer; they say nothing about device rendering,
 * accessibility, or legibility in a real screen.
 */
class BrandVectorBoardScreenshotsTest : ScreenshotTestSupport() {

    /** The mark, the illustration, and the sixteen icons, light appearance. */
    @Test
    fun brandVectorBoardLight() =
        capture(name = "brand_vector_board_light", width = BOARD_WIDTH, height = BOARD_HEIGHT) {
            ManijeroTheme(darkTheme = false) { BrandVectorBoard() }
        }

    /** The same board, dark appearance. */
    @Test
    fun brandVectorBoardDark() =
        capture(name = "brand_vector_board_dark", width = BOARD_WIDTH, height = BOARD_HEIGHT) {
            ManijeroTheme(darkTheme = true) { BrandVectorBoard() }
        }

    private companion object {
        /** Wide enough for the four-column icon grid; tall enough that no vector is clipped. */
        const val BOARD_WIDTH = 900
        const val BOARD_HEIGHT = 1200
    }
}
