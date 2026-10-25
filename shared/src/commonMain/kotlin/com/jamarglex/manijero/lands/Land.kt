package com.jamarglex.manijero.lands

/**
 * One saved land.
 *
 * [zone] is required for every stored record, like the name. [variety] is `UNKNOWN` until the person
 * chooses one, and [varietyOther] holds the custom text only for [LandVariety.OTHER]. Optional
 * measures stay `null` when the person did not provide them: absence is never a zero or a guess.
 */
data class Land(
    val id: String,
    val name: String,
    val zone: String,
    val municipality: String? = null,
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val variety: LandVariety = LandVariety.UNKNOWN,
    val varietyOther: String? = null,
    val areaHectares: Double? = null,
    val treeCount: Int? = null,
    val notes: String? = null,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
)

/**
 * The values one add or edit action may write. [zone] is required: a record can never be saved
 * without it.
 */
data class LandDraft(
    val name: String,
    val zone: String,
    val municipality: String? = null,
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val variety: LandVariety = LandVariety.UNKNOWN,
    val varietyOther: String? = null,
    val areaHectares: Double? = null,
    val treeCount: Int? = null,
    val notes: String? = null,
)

enum class WaterRegime { UNKNOWN, DRYLAND, IRRIGATED, MIXED }

enum class ProductionMethod { UNKNOWN, CONVENTIONAL, ORGANIC, MIXED }

/**
 * The approved olive-variety shortlist. Declaration order is the storage/enum identity order, not the
 * selector order: the display order is [LAND_VARIETY_OPTIONS] in the land surfaces.
 */
enum class LandVariety {
    UNKNOWN,
    PICUAL,
    HOJIBLANCA,
    PICUDO,
    LECHIN_DE_SEVILLA,
    ARBEQUINA,
    MANZANILLA,
    GORDAL,
    MIXED,
    OTHER,
}
