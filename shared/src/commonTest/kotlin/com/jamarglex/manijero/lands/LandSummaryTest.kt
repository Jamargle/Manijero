package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class LandSummaryTest {
    private fun land(
        id: String,
        name: String = "Terreno $id",
        areaHectares: Double? = null,
        treeCount: Int? = null,
    ) = Land(
        id = id,
        name = name,
        zone = "El Llano",
        areaHectares = areaHectares,
        treeCount = treeCount,
        createdAtEpochMillis = 0,
        updatedAtEpochMillis = 0,
    )

    @Test
    fun `an empty list has no total and no known value`() {
        val summary = summarizeLands(emptyList())

        assertEquals(0, summary.total)
        assertNull(summary.surfaceTotal)
        assertEquals(0, summary.surfaceKnownCount)
        assertNull(summary.treeTotal)
        assertEquals(0, summary.treeKnownCount)
    }

    @Test
    fun `a partial list totals only the annotated values`() {
        val summary = summarizeLands(
            listOf(
                land("land-1", areaHectares = 1.5, treeCount = 85),
                land("land-2", areaHectares = 0.75),
                land("land-3", treeCount = 1200),
            ),
        )

        assertEquals(3, summary.total)
        assertEquals(2.25, summary.surfaceTotal)
        assertEquals(2, summary.surfaceKnownCount)
        assertEquals(1285L, summary.treeTotal)
        assertEquals(2, summary.treeKnownCount)
    }

    @Test
    fun `a fully annotated list counts every land`() {
        val summary = summarizeLands(
            listOf(
                land("land-1", areaHectares = 1.0, treeCount = 100),
                land("land-2", areaHectares = 2.0, treeCount = 200),
            ),
        )

        assertEquals(2, summary.total)
        assertEquals(3.0, summary.surfaceTotal)
        assertEquals(2, summary.surfaceKnownCount)
        assertEquals(300L, summary.treeTotal)
        assertEquals(2, summary.treeKnownCount)
    }

    @Test
    fun `the surface sum is rounded once with the stored precision`() {
        val summary = summarizeLands(
            listOf(
                land("land-1", areaHectares = 0.1),
                land("land-2", areaHectares = 0.2),
            ),
        )

        assertEquals(0.3, summary.surfaceTotal)
    }

    @Test
    fun `a single land summarizes itself`() {
        val summary = summarizeLands(listOf(land("land-1", areaHectares = 0.75, treeCount = 1)))

        assertEquals(1, summary.total)
        assertEquals(0.75, summary.surfaceTotal)
        assertEquals(1, summary.surfaceKnownCount)
        assertEquals(1L, summary.treeTotal)
        assertEquals(1, summary.treeKnownCount)
    }

    @Test
    fun `a filtered subset counts only the lands it received`() {
        val all = listOf(
            land("land-1", areaHectares = 1.5, treeCount = 85),
            land("land-2", areaHectares = 0.75),
            land("land-3", treeCount = 1200),
        )

        val summary = summarizeLands(all.take(2))

        assertEquals(2, summary.total)
        assertEquals(2.25, summary.surfaceTotal)
        assertEquals(2, summary.surfaceKnownCount)
        assertEquals(85L, summary.treeTotal)
        assertEquals(1, summary.treeKnownCount)
    }

    @Test
    fun `an absent value is never a zero and no total is derived from another attribute`() {
        val noSurface = summarizeLands(
            listOf(
                land("land-1", treeCount = 85),
                land("land-2", treeCount = 1200),
            ),
        )
        assertNull(noSurface.surfaceTotal, "no surface is annotated, so there is no surface total")
        assertEquals(0, noSurface.surfaceKnownCount)
        assertEquals(1285L, noSurface.treeTotal)

        val noTrees = summarizeLands(
            listOf(
                land("land-1", areaHectares = 1.5),
                land("land-2", areaHectares = 0.75),
            ),
        )
        assertNull(noTrees.treeTotal, "no tree count is annotated, so there is no tree total")
        assertEquals(0, noTrees.treeKnownCount)
        assertEquals(2.25, noTrees.surfaceTotal)

        val nothingAnnotated = summarizeLands(listOf(land("land-1")))
        assertNull(nothingAnnotated.surfaceTotal)
        assertNull(nothingAnnotated.treeTotal)
        assertEquals(1, nothingAnnotated.total)
    }

    @Test
    fun `the tree total accumulates in Long and cannot wrap`() {
        val summary = summarizeLands(
            listOf(
                land("land-1", treeCount = Int.MAX_VALUE),
                land("land-2", treeCount = Int.MAX_VALUE),
            ),
        )

        assertEquals(4_294_967_294L, summary.treeTotal)
        assertEquals(2, summary.treeKnownCount)
    }
}
