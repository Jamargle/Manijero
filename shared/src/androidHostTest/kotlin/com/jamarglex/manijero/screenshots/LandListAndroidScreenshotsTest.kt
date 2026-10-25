package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Pixel regression captures for the shared saved-lands screen, rendered by Android via Robolectric. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "es-rES-w360dp-h800dp-mdpi")
class LandListAndroidScreenshotsTest : AndroidScreenshotTestSupport() {

    /** The saved-lands surface with two distinguishable lands, light appearance. */
    @Test
    fun landListLight() =
        capture("land_list_light") {
            ManijeroTheme(darkTheme = false) {
                LandListScreen(
                    state = ScreenshotFixtures.twoLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onBack = {},
                    onRetry = {},
                )
            }
        }

    /** The saved-lands empty state, dark appearance. */
    @Test
    fun landListEmptyDark() =
        capture("land_list_empty_dark") {
            ManijeroTheme(darkTheme = true) {
                LandListScreen(
                    state = ScreenshotFixtures.noLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onBack = {},
                    onRetry = {},
                )
            }
        }
}
