package com.jamarglex.manijero.screenshots

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.Density
import com.github.takahirom.roborazzi.ExperimentalRoborazziApi
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.roborazziSystemPropertyTaskType
import java.util.Locale
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import org.junit.Rule

/**
 * Shared harness for the Android screenshot suite. Robolectric renders the real Android target on
 * the host JVM, so no emulator or device is required; the RenderNode still follows Android's
 * layout, fonts, and rasterisation rather than Compose Desktop's.
 *
 * The goldens live in `shared/src/androidHostTest/screenshots` and are separate from the Desktop
 * set: the two platforms rasterise text and controls differently. The viewport is pinned by the
 * concrete test classes' `@Config(qualifiers = ...)`; density and font scale are pinned here.
 *
 * Verification is read-only and re-recording is explicit, exactly like the Desktop suite.
 */
abstract class AndroidScreenshotTestSupport {

    @get:Rule
    val composeRule = createComposeRule()

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
     * Sets [content] on the Robolectric activity and captures the semantics root with Roborazzi.
     * A missing capture mode fails loudly instead of silently producing no image.
     */
    protected fun capture(name: String, content: @Composable () -> Unit) {
        requireScreenshotMode()
        composeRule.setContent {
            CompositionLocalProvider(
                LocalDensity provides Density(density = 1f, fontScale = 1f),
            ) {
                content()
            }
        }
        composeRule.waitForIdle()
        composeRule.onRoot().captureRoboImage(
            filePath = "$name.png",
            roborazziOptions = ScreenshotOptions,
        )
    }

    @OptIn(ExperimentalRoborazziApi::class)
    private fun requireScreenshotMode() {
        val taskType = roborazziSystemPropertyTaskType()
        check(taskType.isVerifying() || taskType.isRecording()) {
            "Screenshot capture is not enabled. Run ./gradlew :shared:verifyAndroidScreenshots " +
                "to verify against the committed goldens, or " +
                "./gradlew :shared:recordAndroidScreenshots to explicitly re-record them after " +
                "review."
        }
    }

    protected companion object {
        /**
         * Same deliberate threshold as the Desktop suite: a meaningful layout, colour, or copy
         * regression covers far more than 0.1% of the frame, while same-host Robolectric renders
         * are deterministic. Do not widen it to hide a real change.
         */
        val ScreenshotOptions = RoborazziOptions(
            compareOptions = RoborazziOptions.CompareOptions(changeThreshold = 0.001F),
        )
    }
}
