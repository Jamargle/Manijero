package com.jamarglex.manijero.screenshots

import com.jamarglex.manijero.lands.LandListScreen
import com.jamarglex.manijero.lands.LandStoreRecovery
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
                    onRetry = {},
                    onQueryChange = {},
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
                    onRetry = {},
                    onQueryChange = {},
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
                    onRetry = {},
                    onQueryChange = {},
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
                    onRetry = {},
                    onQueryChange = {},
                )
            }
        }

    /**
     * A query that matches neither saved land, light appearance at the wide 900 x 1000 dp viewport.
     * The phone width would push the no-results panel below the fold, so the capture would prove
     * nothing; here the search field, the Add action and the panel share one frame.
     */
    @Test
    fun landListSearchNoResults() =
        capture(name = "land_list_search_no_results", width = LAND_WIDTH, height = LAND_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                LandListScreen(
                    state = ScreenshotFixtures.searchNoResults,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                )
            }
        }

    /**
     * One match of two saved lands, light appearance at the wide 900 x 1000 dp viewport, so the
     * filtered scope caption, the three cards and the `x de y` filtered captions share one frame.
     */
    @Test
    fun landListSearchFiltered() =
        capture(name = "land_list_search_filtered", width = LAND_WIDTH, height = LAND_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                LandListScreen(
                    state = ScreenshotFixtures.searchFiltered,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                )
            }
        }

    /**
     * The recovered state after a damaged primary store was rebuilt from the newest automatic copy:
     * the neutral callout, its `Entendido` action, and the unchanged two-row list, light appearance
     * at the 900 x 1200 dp viewport.
     */
    @Test
    fun landListRecoveryLight() =
        capture(name = "land_list_recovery_light", width = LAND_WIDTH, height = RECOVERY_LAND_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                LandListScreen(
                    state = ScreenshotFixtures.twoLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                    recovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                )
            }
        }

    /** The same recovered state, dark appearance at the 900 x 1200 dp viewport. */
    @Test
    fun landListRecoveryDark() =
        capture(name = "land_list_recovery_dark", width = LAND_WIDTH, height = RECOVERY_LAND_HEIGHT) {
            ManijeroTheme(darkTheme = true) {
                LandListScreen(
                    state = ScreenshotFixtures.twoLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                    recovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                )
            }
        }

    /** The recovered state at the phone-width viewport, light appearance. */
    @Test
    fun landListRecoveryLightPhone() =
        capture(name = "land_list_recovery_light_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
            ManijeroTheme(darkTheme = false) {
                LandListScreen(
                    state = ScreenshotFixtures.twoLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                    recovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                )
            }
        }

    /** The recovered state at the phone-width viewport, dark appearance. */
    @Test
    fun landListRecoveryDarkPhone() =
        capture(name = "land_list_recovery_dark_phone", width = PHONE_WIDTH, height = PHONE_HEIGHT) {
            ManijeroTheme(darkTheme = true) {
                LandListScreen(
                    state = ScreenshotFixtures.twoLands,
                    onAddLand = {},
                    onEditLand = {},
                    onRemoveLand = {},
                    onRetry = {},
                    onQueryChange = {},
                    recovery = LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
                )
            }
        }
}
