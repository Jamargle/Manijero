package com.jamarglex.manijero.design

import androidx.compose.ui.unit.dp
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Common tests for the pure helpers the component layer introduces.
 *
 * Everything else in the layer is verified by compile, previews, the review gallery and the host
 * screenshot suites; those are not behavior claims and no Compose UI test dependency is added here.
 */
class ManijeroComponentsTest {

    @Test
    fun compactWindowsKeepTheNarrowScreenPadding() {
        assertEquals(24.dp, screenHorizontalPadding(320.dp))
        assertEquals(24.dp, screenHorizontalPadding(360.dp))
        assertEquals(24.dp, screenHorizontalPadding(600.dp))
    }

    @Test
    fun theWideBreakpointAppliesExactlyAt840Dp() {
        assertEquals(24.dp, screenHorizontalPadding(839.dp))
        assertEquals(40.dp, screenHorizontalPadding(840.dp))
    }

    @Test
    fun wideWindowsUseTheWideScreenPadding() {
        assertEquals(40.dp, screenHorizontalPadding(1200.dp))
        assertEquals(40.dp, screenHorizontalPadding(1920.dp))
    }

    @Test
    fun aValidIndexSelectsThatDestination() {
        assertEquals(0, selectedDestinationIndex(destinationsCount = 3, requestedIndex = 0))
        assertEquals(1, selectedDestinationIndex(destinationsCount = 3, requestedIndex = 1))
        assertEquals(2, selectedDestinationIndex(destinationsCount = 3, requestedIndex = 2))
        assertEquals(0, selectedDestinationIndex(destinationsCount = 1, requestedIndex = 0))
    }

    @Test
    fun anIndexEqualToTheCountSelectsNothing() {
        assertEquals(-1, selectedDestinationIndex(destinationsCount = 3, requestedIndex = 3))
        assertEquals(-1, selectedDestinationIndex(destinationsCount = 1, requestedIndex = 1))
    }

    @Test
    fun aNegativeOrEmptySelectionSelectsNothing() {
        assertEquals(-1, selectedDestinationIndex(destinationsCount = 3, requestedIndex = -1))
        assertEquals(-1, selectedDestinationIndex(destinationsCount = 3, requestedIndex = -7))
        assertEquals(-1, selectedDestinationIndex(destinationsCount = 0, requestedIndex = 0))
    }
}
