package com.jamarglex.manijero.lands

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class LandSearchTest {
    /**
     * The shipped Spanish labels, copied here because a non-composable test may not read
     * `strings.xml`. They must stay equal to the `add_land_water_*`, `add_land_production_*`,
     * `add_land_variety_*` and `add_land_unknown` values.
     */
    private val labels = LandSearchLabels(
        waterRegime = mapOf(
            WaterRegime.UNKNOWN to "No lo sé",
            WaterRegime.DRYLAND to "Secano",
            WaterRegime.IRRIGATED to "Regadío",
            WaterRegime.MIXED to "Una parte de regadío y otra de secano",
        ),
        productionMethod = mapOf(
            ProductionMethod.UNKNOWN to "No lo sé",
            ProductionMethod.CONVENTIONAL to "Convencional",
            ProductionMethod.ORGANIC to "Ecológico",
            ProductionMethod.MIXED to "Una parte de cada uno",
        ),
        variety = mapOf(
            LandVariety.UNKNOWN to "No lo sé",
            LandVariety.PICUAL to "Picual",
            LandVariety.HOJIBLANCA to "Hojiblanca",
            LandVariety.PICUDO to "Picudo",
            LandVariety.LECHIN_DE_SEVILLA to "Lechín de Sevilla",
            LandVariety.ARBEQUINA to "Arbequina",
            LandVariety.MANZANILLA to "Manzanilla",
            LandVariety.GORDAL to "Gordal",
            LandVariety.MIXED to "Mezcla de variedades",
            LandVariety.OTHER to "Otra",
        ),
    )

    private fun land(
        id: String,
        name: String,
        zone: String = "El Llano",
        municipality: String? = null,
        variety: LandVariety = LandVariety.UNKNOWN,
        varietyOther: String? = null,
        waterRegime: WaterRegime = WaterRegime.UNKNOWN,
        productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
        areaHectares: Double? = null,
        treeCount: Int? = null,
        notes: String? = null,
    ) = Land(
        id = id,
        name = name,
        zone = zone,
        municipality = municipality,
        waterRegime = waterRegime,
        productionMethod = productionMethod,
        variety = variety,
        varietyOther = varietyOther,
        areaHectares = areaHectares,
        treeCount = treeCount,
        notes = notes,
        createdAtEpochMillis = 1_700_000_000_000,
        updatedAtEpochMillis = 1_700_000_000_001,
    )

    private fun ids(lands: List<Land>) = lands.map { it.id }

    @Test
    fun `folding lowercases and strips accents and the tilde`() {
        assertEquals("pena de los olivos", foldForSearch("Peña de los Olivos"))
        assertEquals("ubeda", foldForSearch("ÚBEDA"))
        assertEquals("lechin de sevilla", foldForSearch("Lechín de Sevilla"))
        assertEquals("regadio", foldForSearch("Regadío"))
        assertEquals("ecologico", foldForSearch("Ecológico"))
        assertEquals("aguila", foldForSearch("Águila"))
        assertEquals("paraguas", foldForSearch("paragüas"))
    }

    @Test
    fun `the same land is found with or without accents and case`() {
        val pena = land(
            id = "land-1",
            name = "Peña de los Olivos",
            zone = "Camino de la Fuente",
            municipality = "Úbeda",
            variety = LandVariety.LECHIN_DE_SEVILLA,
        )
        val lands = listOf(pena)

        listOf(
            "pena",
            "PEÑA",
            "Peña",
            "ubeda",
            "ÚBEDA",
            "lechin",
            "lechín.",
            "olivos ubeda",
            "ubeda olivos",
        ).forEach { query ->
            assertEquals(listOf("land-1"), ids(filterLands(lands, query, labels)), "query: $query")
        }
    }

    @Test
    fun `punctuation emoji blank and whitespace behave like a blank query`() {
        val lands = listOf(
            land("land-1", "Los Olivos"),
            land("land-2", "La Loma"),
        )

        listOf("", "   ", "\n\t", "...", "¿?", "😀", "... 😀 ...").forEach { query ->
            assertSame(lands, filterLands(lands, query, labels), "query: $query")
        }
    }

    @Test
    fun `only a query with a letter or digit counts as a search`() {
        listOf("", "   ", "\n\t", "...", "¿?", "😀", "... 😀 ...").forEach { query ->
            assertFalse(hasSearchTokens(query), "query: $query")
        }
        listOf("olivos", "lechín.", "85").forEach { query ->
            assertTrue(hasSearchTokens(query), "query: $query")
        }
    }

    @Test
    fun `a query that matches nothing returns no land`() {
        val lands = listOf(land("land-1", "Los Olivos"))

        assertEquals(emptyList(), filterLands(lands, "zzz", labels))
    }

    @Test
    fun `measures ids notes and timestamps are never matched`() {
        val target = land(
            id = "land-1",
            name = "Los Olivos",
            areaHectares = 1.5,
            treeCount = 85,
            notes = "aceituna",
        )
        val lands = listOf(target)

        listOf("85", "1,5", "1.5", "2,5", "land-1", "aceituna", "1700000000000").forEach { query ->
            assertEquals(emptyList(), filterLands(lands, query, labels), "query: $query")
        }
    }

    @Test
    fun `name zone municipality variety water and production text are matched`() {
        val target = land(
            id = "land-1",
            name = "Los Olivos",
            zone = "Camino de la Fuente",
            municipality = "Martos",
            variety = LandVariety.PICUAL,
            waterRegime = WaterRegime.DRYLAND,
            productionMethod = ProductionMethod.ORGANIC,
        )
        val lands = listOf(target)

        listOf(
            "olivos",
            "fuente",
            "martos",
            "picual",
            "secano",
            "ecologico",
        ).forEach { query ->
            assertEquals(listOf("land-1"), ids(filterLands(lands, query, labels)), "query: $query")
        }
    }

    @Test
    fun `the custom Otra text is matched and the Otra label is not required`() {
        val custom = land(
            id = "land-1",
            name = "La Loma",
            variety = LandVariety.OTHER,
            varietyOther = "Royal de Cazorla",
        )
        val lands = listOf(custom)

        assertEquals(listOf("land-1"), ids(filterLands(lands, "royal", labels)))
        assertEquals(listOf("land-1"), ids(filterLands(lands, "cazorla", labels)))
        assertEquals(emptyList(), filterLands(lands, "otra", labels))
    }

    @Test
    fun `every mixed and unknown label is searchable`() {
        val mixed = land(
            id = "land-1",
            name = "La Loma",
            waterRegime = WaterRegime.MIXED,
            productionMethod = ProductionMethod.MIXED,
            variety = LandVariety.MIXED,
        )

        listOf("mezcla", "una parte", "regadio", "cada uno").forEach { query ->
            assertEquals(listOf("land-1"), ids(filterLands(listOf(mixed), query, labels)), "query: $query")
        }

        // A land still missing an answer is found by the same `No lo sé` label the row shows. Its
        // own name and zone carry none of those letters, so only the labels can match here.
        val unknown = land(id = "land-2", name = "Finca Alta", zone = "Las Eras")
        assertEquals(listOf("land-2"), ids(filterLands(listOf(unknown), "no lo sé", labels)))
    }

    @Test
    fun `every token must appear in the same land`() {
        val martos = land("land-1", "Los Olivos", municipality = "Martos")
        val ubeda = land("land-2", "Los Olivos", municipality = "Úbeda")
        val lands = listOf(martos, ubeda)

        assertEquals(listOf("land-1"), ids(filterLands(lands, "olivos martos", labels)))
        assertEquals(emptyList(), filterLands(lands, "olivos granada", labels))
    }

    @Test
    fun `repository order is preserved and duplicate names stay separate rows`() {
        val first = land("land-1", "Los Olivos", municipality = "Martos")
        val second = land("land-2", "La Loma", municipality = "Úbeda")
        val third = land("land-3", "Los Olivos", municipality = "Úbeda")
        val lands = listOf(first, second, third)

        assertEquals(listOf("land-1", "land-3"), ids(filterLands(lands, "olivos", labels)))
        assertEquals(listOf("land-1", "land-2", "land-3"), ids(filterLands(lands, "o", labels)))
    }
}
