package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/** Pixel regression captures for the shared saved-lands screen in light and dark appearance. */
class LandListScreenshotsTest : ScreenshotTestSupport() {

    /** The saved-lands surface with two distinguishable lands, light appearance. */
    @Test
    fun landListLight() =
        capture(name = "land_list_light", width = LAND_WIDTH, height = LAND_HEIGHT) {
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

    /** The two-land list at the single phone-width viewport, light appearance. */
    @Test
    fun landListLightPhone() =
        capture(name = "land_list_light_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
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
        capture(name = "land_list_empty_dark", width = LAND_WIDTH, height = EMPTY_LAND_HEIGHT) {
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

    /** The empty lands state at the single phone-width viewport, dark appearance. */
    @Test
    fun landListEmptyDarkPhone() =
        capture(name = "land_list_empty_dark_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
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
