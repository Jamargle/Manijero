package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.v2.runDesktopComposeUiTest
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import com.github.takahirom.roborazzi.ExperimentalRoborazziApi
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.roborazziSystemPropertyTaskType
import io.github.takahirom.roborazzi.captureRoboImage
import java.util.Locale
import kotlin.test.AfterTest
import kotlin.test.BeforeTest

/**
 * Shared harness for the shared-UI screenshot regression suite, rendered on the existing Compose
 * Desktop (JVM) target. Each screen owns its captures in its own test class
 * ([ChatHomeScreenshotsTest], [LandListScreenshotsTest]); this file holds only the parts that must
 * stay identical across them.
 *
 * What the suite covers: the real `commonMain` composables in two appearances. It does not render
 * Android or iOS, does not prove accessibility, usability, or product behavior, and does not judge
 * whether the Spanish copy is good.
 *
 * Determinism contract (all values are pinned here or in the Gradle task):
 *  - surface size: a fixed size per capture (see [CHAT_WIDTH] and friends);
 *  - appearance: the explicit `darkTheme` argument of `ManijeroTheme`, never the host setting;
 *  - density and font scale: density 1, font scale 1, provided in [capture];
 *  - layout direction: left-to-right;
 *  - locale: `es-ES` pinned for the duration of each test. The app ships one default
 *    `values/strings.xml`, so no locale-specific resource can be selected anyway;
 *  - data: [ScreenshotFixtures], with no clock, network, disk, or backend dependency;
 *  - fonts: Compose Desktop resolves the host font, so the goldens are host-pinned. They were
 *    recorded on macOS; a different operating system must record its own reviewed goldens.
 *
 * Verification is read-only: it compares against `shared/src/jvmTest/screenshots` and writes only
 * `_actual`/`_compare` artifacts under `shared/build/reports/screenshot-regression`. Re-record
 * deliberately with `:shared:recordScreenshots` and review every changed PNG.
 */
@OptIn(ExperimentalTestApi::class)
abstract class ScreenshotTestSupport {

    private var previousLocale: Locale? = null

    @BeforeTest
    fun pinLocale() {
        previousLocale = Locale.getDefault()
        Locale.setDefault(Locale.forLanguageTag("es-ES"))
    }

    @AfterTest
    fun restoreLocale() {
        previousLocale?.let(Locale::setDefault)
        previousLocale = null
    }

    /**
     * Renders [content] at a fixed surface size and captures the semantics root with Roborazzi.
     * A missing capture mode fails loudly instead of silently producing no image.
     */
    protected fun capture(
        name: String,
        width: Int,
        height: Int,
        fontScale: Float = 1f,
        content: @Composable () -> Unit,
    ) {
        requireScreenshotMode()
        runDesktopComposeUiTest(width = width, height = height) {
            setContent {
                CompositionLocalProvider(
                    LocalDensity provides Density(density = 1f, fontScale = fontScale),
                    LocalLayoutDirection provides LayoutDirection.Ltr,
                ) {
                    content()
                }
            }
            onRoot().captureRoboImage(
                filePath = "$name.png",
                roborazziOptions = ScreenshotOptions,
            )
        }
    }

    @OptIn(ExperimentalRoborazziApi::class)
    private fun requireScreenshotMode() {
        val taskType = roborazziSystemPropertyTaskType()
        check(taskType.isVerifying() || taskType.isRecording()) {
            "Screenshot capture is not enabled. Run ./gradlew :shared:verifyScreenshots to verify " +
                "against the committed goldens, or ./gradlew :shared:recordScreenshots to " +
                "explicitly re-record them after review."
        }
    }

    protected companion object {
        /**
         * Dimensions are density-independent pixels at the pinned density of 1. The answered
         * chat state is taller than the viewport, so that golden records the top of the page
         * (title, transcript, answer, and source card) and deliberately excludes the composer and
         * privacy lines below the fold.
         */
        const val CHAT_WIDTH = 900
        const val CHAT_HEIGHT = 1200
        const val LAND_WIDTH = 900
        const val LAND_HEIGHT = 1000
        const val EMPTY_LAND_HEIGHT = 800

        /**
         * One phone-width viewport, still rendered by Compose Desktop on the JVM. It approximates
         * a 360 dp wide phone at density 1 and is not an Android or iOS render; fonts and text
         * metrics still come from the host. The same four states are captured at this size so a
         * narrow-screen reflow that the 900 dp captures cannot show becomes visible.
         */
        const val PHONE_WIDTH = 360
        const val PHONE_HEIGHT = 800

        /**
         * A meaningful regression (a moved control, a changed colour, a wrapped line) covers far
         * more than 0.1% of the frame, while the same-host render is deterministic. The per-pixel
         * comparator (Roborazzi's default `SimpleImageComparator(maxDistance = 0.007)`) already
         * absorbs sub-visible antialiasing noise. The threshold is deliberately not widened.
         */
        val ScreenshotOptions = RoborazziOptions(
            compareOptions = RoborazziOptions.CompareOptions(changeThreshold = 0.001F),
        )
    }
}
