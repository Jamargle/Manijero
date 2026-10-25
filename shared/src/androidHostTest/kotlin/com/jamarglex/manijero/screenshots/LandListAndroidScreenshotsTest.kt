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
                    onRetry = {},
                    onQueryChange = {},
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
                    onRetry = {},
                    onQueryChange = {},
                )
            }
        }

    /**
     * A query that matches neither saved land, light appearance at the wide 900 x 1000 dp viewport.
     * The class viewport is a phone, where the no-results panel falls below the fold; the per-method
     * qualifier matches the existing rail captures so the field, the Add action and the panel share
     * one frame.
     */
    @Test
    @Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")
    fun landListSearchNoResults() =
        capture("land_list_search_no_results") {
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
     * One match of two saved lands with the filtered summary copy, light appearance at the wide
     * 900 x 1000 dp viewport so the scope caption, the three cards and their `x de y` captions
     * share one frame. Uses the same per-method qualifier as the rail captures.
     */
    @Test
    @Config(qualifiers = "es-rES-w900dp-h1000dp-mdpi")
    fun landListSearchFiltered() =
        capture("land_list_search_filtered") {
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
}
