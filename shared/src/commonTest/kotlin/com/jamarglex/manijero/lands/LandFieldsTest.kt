package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Pure parsing/formatting contract for the new land fields; no Compose or storage is involved. */
class LandFieldsTest {
    @Test
    fun `approved lengths are pinned`() {
        assertEquals(80, ZONE_MAX_LENGTH)
        assertEquals(40, VARIETY_OTHER_MAX_LENGTH)
    }

    @Test
    fun `zone is required after trimming and has a hard length limit`() {
        assertEquals(ZoneProblem.BLANK, zoneProblem(""))
        assertEquals(ZoneProblem.BLANK, zoneProblem("   "))
        assertEquals(ZoneProblem.BLANK, zoneProblem("\n\t"))
        assertNull(zoneProblem("El Llano"))
        assertNull(zoneProblem("  El Llano  "))
        assertNull(zoneProblem("x".repeat(ZONE_MAX_LENGTH)))
        assertEquals(ZoneProblem.TOO_LONG, zoneProblem("x".repeat(ZONE_MAX_LENGTH + 1)))
        assertEquals(
            ZoneProblem.TOO_LONG,
            zoneProblem("  " + "x".repeat(ZONE_MAX_LENGTH + 1) + "  "),
        )
        assertTrue(isValidZone("Camino de la Fuente"))
        assertFalse(isValidZone(" "))
    }

    @Test
    fun `custom variety is required only for Otra and is trimmed`() {
        assertTrue(isValidVarietyOther(LandVariety.PICUAL, ""))
        assertFalse(isValidVarietyOther(LandVariety.OTHER, ""))
        assertFalse(isValidVarietyOther(LandVariety.OTHER, "   "))
        assertTrue(isValidVarietyOther(LandVariety.OTHER, "Royal de Cazorla"))
        assertTrue(isValidVarietyOther(LandVariety.OTHER, "x".repeat(VARIETY_OTHER_MAX_LENGTH)))
        assertFalse(
            isValidVarietyOther(LandVariety.OTHER, "x".repeat(VARIETY_OTHER_MAX_LENGTH + 1)),
        )

        assertEquals(
            "Royal de Cazorla",
            normalizedVarietyOther(LandVariety.OTHER, "  Royal de Cazorla  "),
        )
        assertNull(normalizedVarietyOther(LandVariety.OTHER, "   "))
        assertNull(normalizedVarietyOther(LandVariety.PICUAL, "Royal de Cazorla"))
        assertNull(normalizedVarietyOther(LandVariety.UNKNOWN, "Royal de Cazorla"))
    }

    @Test
    fun `blank surface is valid and absent`() {
        val result = parseAreaHectares("   ")
        assertTrue(result.isValid)
        assertNull(result.valueOrNull())
    }

    @Test
    fun `surface accepts comma or dot and rounds to two decimals`() {
        assertEquals(MeasureResult.Valid(1.5), parseAreaHectares("1,5"))
        assertEquals(MeasureResult.Valid(1.5), parseAreaHectares("1.5"))
        assertEquals(MeasureResult.Valid(0.75), parseAreaHectares("0,75"))
        assertEquals(MeasureResult.Valid(85.0), parseAreaHectares("85"))
        assertEquals(MeasureResult.Valid(2.0), parseAreaHectares("2."))
        assertEquals(MeasureResult.Valid(0.5), parseAreaHectares(".5"))
        assertEquals(MeasureResult.Valid(0.0), parseAreaHectares("0"))
        assertEquals(MeasureResult.Valid(1.5), parseAreaHectares(" 1,5 "))
        assertEquals(MeasureResult.Valid(1.23), parseAreaHectares("1,234"))
        assertEquals(MeasureResult.Valid(1.23), parseAreaHectares("1.234"))
        assertEquals(MeasureResult.Valid(1.24), parseAreaHectares("1,236"))
        assertEquals(MeasureResult.Valid(2.0), parseAreaHectares("1,999"))
    }

    @Test
    fun `surface rejects letters signs several separators and overflow`() {
        assertFalse(parseAreaHectares("9".repeat(400)).isValid)
        listOf("letras", "-1", "+1", "1,2,3", "NaN", "Infinity", "1e3")
            .forEach { raw ->
                assertFalse(parseAreaHectares(raw).isValid, "<$raw> must not be a valid surface")
                assertNull(parseAreaHectares(raw).valueOrNull())
            }
    }

    @Test
    fun `tree count accepts only whole ASCII numbers of at least one`() {
        assertEquals(MeasureResult.Valid(null), parseTreeCount(""))
        assertEquals(MeasureResult.Valid(1), parseTreeCount("1"))
        assertEquals(MeasureResult.Valid(85), parseTreeCount(" 85 "))
        assertEquals(MeasureResult.Valid(Int.MAX_VALUE), parseTreeCount(Int.MAX_VALUE.toString()))

        listOf("0", "-1", "+1", "1,5", "1.5", "árbol", "٨٥", Int.MAX_VALUE.toString() + "0")
            .forEach { raw ->
                assertFalse(parseTreeCount(raw).isValid, "<$raw> must not be a valid tree count")
                assertNull(parseTreeCount(raw).valueOrNull())
            }
    }

    @Test
    fun `rounding and formatting never invent decimals or thousands dots`() {
        assertEquals(1.24, roundHectares(1.236))
        assertEquals(2.0, roundHectares(2.0))
        assertEquals(1e307, roundHectares(1e307))
        assertEquals("1,5", formatHectares(1.5))
        assertEquals("2", formatHectares(2.0))
        assertEquals("0,75", formatHectares(0.75))
        assertEquals("12", formatHectares(12.0))
        assertEquals("1,2", formatHectares(1.2))
        assertEquals("1234,5", formatHectares(1234.5))
        assertEquals("", areaInputText(null))
        assertEquals("2,5", areaInputText(2.5))
    }

    @Test
    fun `tree formatting uses a plain space between thousands`() {
        assertEquals("0", formatTreeCount(0))
        assertEquals("85", formatTreeCount(85))
        assertEquals("1 200", formatTreeCount(1200))
        assertEquals("1 234 567", formatTreeCount(1_234_567))
        assertEquals("-1 200", formatTreeCount(-1200))
    }

    @Test
    fun `summed tree counts use the same grouping through the Long entry point`() {
        assertEquals("1 285", formatTreeCount(1285L))
        assertEquals("1 200 000", formatTreeCount(1_200_000L))
        assertEquals("1", formatTreeCount(1L))
        assertEquals("0", formatTreeCount(0L))
        assertEquals(
            "4 294 967 294",
            formatTreeCount(Int.MAX_VALUE.toLong() + Int.MAX_VALUE.toLong()),
        )
    }

    @Test
    fun `variety options use the approved shortlist order`() {
        assertEquals(
            listOf(
                LandVariety.PICUAL,
                LandVariety.HOJIBLANCA,
                LandVariety.PICUDO,
                LandVariety.LECHIN_DE_SEVILLA,
                LandVariety.ARBEQUINA,
                LandVariety.MANZANILLA,
                LandVariety.GORDAL,
                LandVariety.MIXED,
                LandVariety.OTHER,
                LandVariety.UNKNOWN,
            ),
            LAND_VARIETY_OPTIONS,
        )
        assertEquals(LandVariety.entries.toSet(), LAND_VARIETY_OPTIONS.toSet())
    }
}
