package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import com.jamarglex.manijero.design.ComponentGallery
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test

/**
 * Pixel regression captures for the review-only component gallery: every component and tone in the
 * shared design layer, once per appearance at the wide window and once per appearance at the narrow
 * phone window with 2x text.
 *
 * The gallery is not a screen. These captures prove the layer compiles into the Compose Desktop
 * renderer, reads only theme roles, and keeps its layout intact in both appearances and at enlarged
 * text; they say nothing about a device, accessibility, or product behavior.
 */
class ComponentGalleryScreenshotsTest : ScreenshotTestSupport() {

    @Test
    fun componentGalleryLight() =
        capture(name = "component_gallery_light", width = WIDE_WIDTH, height = WIDE_HEIGHT) {
            ManijeroTheme(darkTheme = false) { ComponentGallery() }
        }

    @Test
    fun componentGalleryDark() =
        capture(name = "component_gallery_dark", width = WIDE_WIDTH, height = WIDE_HEIGHT) {
            ManijeroTheme(darkTheme = true) { ComponentGallery() }
        }

    /**
     * The same gallery at the narrow phone width with text scaled to 2x. The density override is
     * nested inside the harness provider, so only the gallery's font scale changes and the capture
     * viewport, locale, and threshold stay the suite defaults.
     */
    @Test
    fun componentGalleryNarrowLargeTextLight() =
        capture(
            name = "component_gallery_narrow_large_text_light",
            width = NARROW_WIDTH,
            height = NARROW_HEIGHT,
        ) {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                ManijeroTheme(darkTheme = false) { ComponentGallery() }
            }
        }

    @Test
    fun componentGalleryNarrowLargeTextDark() =
        capture(
            name = "component_gallery_narrow_large_text_dark",
            width = NARROW_WIDTH,
            height = NARROW_HEIGHT,
        ) {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                ManijeroTheme(darkTheme = true) { ComponentGallery() }
            }
        }

    private companion object {
        /** Wide enough for the 1200 dp gallery; tall enough that no section is clipped. */
        const val WIDE_WIDTH = 1200
        const val WIDE_HEIGHT = 3000

        /** The 360 dp phone width the app scenes already use, taller for the 2x text. */
        const val NARROW_WIDTH = 360
        const val NARROW_HEIGHT = 5400
    }
}
