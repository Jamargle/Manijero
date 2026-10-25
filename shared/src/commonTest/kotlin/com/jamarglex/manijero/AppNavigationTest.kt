package com.jamarglex.manijero

import com.jamarglex.manijero.design.selectedDestinationIndex
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * The shell's route table is pure, so it can be pinned without rendering anything: which tabs
 * exist, which tab owns each screen, when the bars are hidden, and where back goes.
 */
class AppNavigationTest {

    @Test
    fun `lands tab exists only with a local repository`() {
        assertEquals(
            listOf(AppSection.Assistant, AppSection.Lands, AppSection.Help),
            availableSections(landsAvailable = true),
        )
        assertEquals(
            listOf(AppSection.Assistant, AppSection.Help),
            availableSections(landsAvailable = false),
        )
    }

    @Test
    fun `each tab opens its own top-level screen`() {
        assertEquals(AppDestination.Chat, sectionDestination(AppSection.Assistant))
        assertEquals(AppDestination.LandList, sectionDestination(AppSection.Lands))
        assertEquals(AppDestination.Coverage, sectionDestination(AppSection.Help))
    }

    @Test
    fun `top-level screens round-trip through their tab`() {
        availableSections(landsAvailable = true).forEach { section ->
            assertEquals(section, tabForDestination(sectionDestination(section), AppSection.Help))
        }
    }

    @Test
    fun `detail routes keep the section they belong to`() {
        assertEquals(
            AppSection.Lands,
            tabForDestination(AppDestination.AddLand, AppSection.Assistant),
        )
        assertEquals(
            AppSection.Lands,
            tabForDestination(AppDestination.EditLand, AppSection.Assistant),
        )
        assertEquals(
            AppSection.Lands,
            tabForDestination(AppDestination.RemoveLand, AppSection.Assistant),
        )
        assertEquals(
            AppSection.Help,
            tabForDestination(AppDestination.Coverage, AppSection.Assistant),
        )
    }

    @Test
    fun `privacy reports the section it was opened from`() {
        AppSection.entries.forEach { fallback ->
            assertEquals(fallback, tabForDestination(AppDestination.Privacy, fallback))
        }
    }

    @Test
    fun `a missing destination can never be selected`() {
        val sections = availableSections(landsAvailable = false)
        val landsIndex = sections.indexOf(AppSection.Lands)

        assertEquals(-1, landsIndex)
        assertEquals(-1, selectedDestinationIndex(sections.size, landsIndex))
    }

    @Test
    fun `only the land forms hide the navigation bars`() {
        assertFalse(navigationVisible(AppDestination.AddLand))
        assertFalse(navigationVisible(AppDestination.EditLand))
        assertFalse(navigationVisible(AppDestination.RemoveLand))

        assertTrue(navigationVisible(AppDestination.Chat))
        assertTrue(navigationVisible(AppDestination.LandList))
        assertTrue(navigationVisible(AppDestination.Coverage))
        assertTrue(navigationVisible(AppDestination.Privacy))
    }

    @Test
    fun `assistant keeps the platform default instead of a back route`() {
        assertNull(backTarget(AppDestination.Chat, AppSection.Assistant, AppDestination.Chat))
    }

    @Test
    fun `lands and forms return to their parent without loops`() {
        val back = backTarget(AppDestination.LandList, AppSection.Lands, AppDestination.Chat)
        assertEquals(AppDestination.Chat, back)

        listOf(
            AppDestination.AddLand,
            AppDestination.EditLand,
            AppDestination.RemoveLand,
        ).forEach { form ->
            assertEquals(
                AppDestination.LandList,
                backTarget(form, AppSection.Lands, AppDestination.Chat),
            )
        }
    }

    @Test
    fun `help returns to the tab it was entered from`() {
        assertEquals(
            AppDestination.Chat,
            backTarget(AppDestination.Coverage, AppSection.Assistant, AppDestination.Chat),
        )
        assertEquals(
            AppDestination.LandList,
            backTarget(AppDestination.Coverage, AppSection.Lands, AppDestination.Chat),
        )
    }

    @Test
    fun `help never returns to itself`() {
        assertEquals(
            AppDestination.Chat,
            backTarget(AppDestination.Coverage, AppSection.Help, AppDestination.Chat),
        )
    }

    @Test
    fun `privacy returns exactly where it was opened from`() {
        assertEquals(
            AppDestination.Chat,
            backTarget(AppDestination.Privacy, AppSection.Assistant, AppDestination.Chat),
        )
        assertEquals(
            AppDestination.Coverage,
            backTarget(AppDestination.Privacy, AppSection.Help, AppDestination.Coverage),
        )
    }

    @Test
    fun `no back route points at the screen it leaves`() {
        AppDestination.entries.forEach { destination ->
            AppSection.entries.forEach { previousSection ->
                listOf(AppDestination.Chat, AppDestination.Coverage).forEach { privacyReturn ->
                    backTarget(destination, previousSection, privacyReturn)?.let { target ->
                        assertNotEquals(destination, target)
                    }
                }
            }
        }
    }
}
