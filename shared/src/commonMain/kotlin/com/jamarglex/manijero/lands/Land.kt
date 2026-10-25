package com.jamarglex.manijero.lands

/**
 * One saved land.
 *
 * [zone] is required for every record the app writes; it is `null` only for a record that was
 * saved before this field existed (a `land-store-v1` file). [variety] is `UNKNOWN` until the person
 * chooses one, and [varietyOther] holds the custom text only for [LandVariety.OTHER]. Optional
 * measures stay `null` when the person did not provide them: absence is never a zero or a guess.
 */
data class Land(
    val id: String,
    val name: String,
    val zone: String? = null,
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
 * The values one add or edit action may write. [zone] is required: a new or edited record can never
 * be saved without it, while a stored legacy record keeps its readable `null` zone until edited.
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
