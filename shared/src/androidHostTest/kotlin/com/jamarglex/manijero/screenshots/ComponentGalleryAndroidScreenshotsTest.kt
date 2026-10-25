package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import com.jamarglex.manijero.design.ComponentGallery
import com.jamarglex.manijero.theme.ManijeroTheme
import kotlin.test.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Pixel regression captures for the review-only component gallery, rendered by Android through
 * Robolectric on the host JVM: every component and tone, once per appearance at the wide window and
 * once per appearance at the narrow phone window with 2x text.
 *
 * The viewport is pinned per capture because the wide and narrow images need different windows; the
 * harness still owns the locale, density, mode check, and comparison threshold. The 2x font scale is
 * a nested density override around the gallery only. This is not a device or emulator render and
 * makes no accessibility or real-device legibility claim.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ComponentGalleryAndroidScreenshotsTest : AndroidScreenshotTestSupport() {

    @Test
    @Config(sdk = [35], qualifiers = "es-rES-w1200dp-h3000dp-mdpi")
    fun componentGalleryLight() =
        capture("component_gallery_light") {
            ManijeroTheme(darkTheme = false) { ComponentGallery() }
        }

    @Test
    @Config(sdk = [35], qualifiers = "es-rES-w1200dp-h3000dp-mdpi")
    fun componentGalleryDark() =
        capture("component_gallery_dark") {
            ManijeroTheme(darkTheme = true) { ComponentGallery() }
        }

    @Test
    @Config(sdk = [35], qualifiers = "es-rES-w360dp-h5400dp-mdpi")
    fun componentGalleryNarrowLargeTextLight() =
        capture("component_gallery_narrow_large_text_light") {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                ManijeroTheme(darkTheme = false) { ComponentGallery() }
            }
        }

    @Test
    @Config(sdk = [35], qualifiers = "es-rES-w360dp-h5400dp-mdpi")
    fun componentGalleryNarrowLargeTextDark() =
        capture("component_gallery_narrow_large_text_dark") {
            CompositionLocalProvider(LocalDensity provides Density(density = 1f, fontScale = 2f)) {
                ManijeroTheme(darkTheme = true) { ComponentGallery() }
            }
        }
}
