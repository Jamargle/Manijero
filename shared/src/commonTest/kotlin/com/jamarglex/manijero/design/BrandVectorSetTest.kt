package com.jamarglex.manijero.design

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertSame
import kotlin.test.assertTrue
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.allDrawableResources
import manijero.shared.generated.resources.brand_mark
import manijero.shared.generated.resources.ic_add
import manijero.shared.generated.resources.ic_back
import manijero.shared.generated.resources.ic_chat
import manijero.shared.generated.resources.ic_check
import manijero.shared.generated.resources.ic_chevron_down
import manijero.shared.generated.resources.ic_clear
import manijero.shared.generated.resources.ic_delete
import manijero.shared.generated.resources.ic_edit
import manijero.shared.generated.resources.ic_external_link
import manijero.shared.generated.resources.ic_help
import manijero.shared.generated.resources.ic_info
import manijero.shared.generated.resources.ic_lands
import manijero.shared.generated.resources.ic_retry
import manijero.shared.generated.resources.ic_search
import manijero.shared.generated.resources.ic_send
import manijero.shared.generated.resources.ic_warning
import manijero.shared.generated.resources.olive_branch
import org.jetbrains.compose.resources.DrawableResource

/**
 * Pins the published brand-vector inventory: exactly the sixteen `ic_*` glyphs the spec names, plus
 * the brand mark and the olive-branch illustration.
 *
 * A renamed or deleted file stops this test from compiling, because every accessor is referenced by
 * name. The registry checks then prove that each name the wrappers use resolves to its own drawable
 * resource, so a stray or duplicated `ic_*` entry cannot slip into the shipped set unnoticed.
 *
 * The per-file style rules (24 dp grid, 2 dp round stroke, no filled shape, no baked appearance
 * colour) cannot be asserted from `commonTest`, which has no file system or XML access; the focused
 * shell gates in `docs/specs/brand_vectors.md` enforce them.
 */
class BrandVectorSetTest {

    private val icons: List<Pair<String, DrawableResource>> = listOf(
        "ic_chat" to Res.drawable.ic_chat,
        "ic_lands" to Res.drawable.ic_lands,
        "ic_help" to Res.drawable.ic_help,
        "ic_search" to Res.drawable.ic_search,
        "ic_add" to Res.drawable.ic_add,
        "ic_edit" to Res.drawable.ic_edit,
        "ic_delete" to Res.drawable.ic_delete,
        "ic_back" to Res.drawable.ic_back,
        "ic_retry" to Res.drawable.ic_retry,
        "ic_send" to Res.drawable.ic_send,
        "ic_external_link" to Res.drawable.ic_external_link,
        "ic_info" to Res.drawable.ic_info,
        "ic_warning" to Res.drawable.ic_warning,
        "ic_check" to Res.drawable.ic_check,
        "ic_chevron_down" to Res.drawable.ic_chevron_down,
        "ic_clear" to Res.drawable.ic_clear,
    )

    private val mark: Pair<String, DrawableResource> = "brand_mark" to Res.drawable.brand_mark
    private val illustration: Pair<String, DrawableResource> = "olive_branch" to Res.drawable.olive_branch
    private val namedVectors: List<Pair<String, DrawableResource>> = icons + mark + illustration

    @Test
    fun `the published inventory is exactly the sixteen named glyphs plus mark and illustration`() {
        assertEquals(16, icons.size, "the spec fixes sixteen icons")
        assertEquals(
            listOf(
                "ic_chat", "ic_lands", "ic_help", "ic_search", "ic_add", "ic_edit", "ic_delete",
                "ic_back", "ic_retry", "ic_send", "ic_external_link", "ic_info", "ic_warning",
                "ic_check", "ic_chevron_down", "ic_clear",
            ),
            icons.map { it.first },
        )
        assertEquals(listOf("brand_mark", "olive_branch"), listOf(mark.first, illustration.first))
    }

    @Test
    fun `the drawable registry contains the same names and no stray icon`() {
        val registry = Res.allDrawableResources

        val registeredIcons = registry.keys.filter { it.startsWith("ic_") }.sorted()
        assertEquals(icons.map { it.first }.sorted(), registeredIcons)

        namedVectors.forEach { (name, resource) ->
            assertSame(resource, registry[name], "$name is not the resource the wrappers load")
        }
    }

    @Test
    fun `every published vector is its own resource`() {
        assertEquals(
            namedVectors.size,
            namedVectors.map { it.second }.toSet().size,
            "two published names resolve to the same drawable resource",
        )
        for (first in namedVectors.indices) {
            for (second in first + 1 until namedVectors.size) {
                assertNotEquals(
                    namedVectors[first].second,
                    namedVectors[second].second,
                    "${namedVectors[first].first} and ${namedVectors[second].first} are the same resource",
                )
            }
        }
    }

    @Test
    fun `the wizard placeholder stays out of the inventory`() {
        assertTrue(
            "compose_multiplatform" in Res.allDrawableResources,
            "the wizard placeholder drawable is untouched by this feature",
        )
        assertTrue(namedVectors.none { it.first == "compose_multiplatform" })
    }
}
