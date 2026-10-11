package com.jamarglex.manijero.lands

data class Land(
    val id: String,
    val name: String,
    val municipality: String? = null,
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val areaHectares: Double? = null,
    val notes: String? = null,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
)

data class LandDraft(
    val name: String,
    val municipality: String? = null,
    val waterRegime: WaterRegime = WaterRegime.UNKNOWN,
    val productionMethod: ProductionMethod = ProductionMethod.UNKNOWN,
    val areaHectares: Double? = null,
    val notes: String? = null,
)

enum class WaterRegime { UNKNOWN, DRYLAND, IRRIGATED, MIXED }

enum class ProductionMethod { UNKNOWN, CONVENTIONAL, ORGANIC, MIXED }
