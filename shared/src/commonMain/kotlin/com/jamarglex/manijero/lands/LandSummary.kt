package com.jamarglex.manijero.lands

/**
 * The annotated totals of exactly the lands it was given, plus how many of them carry each value.
 *
 * [total] is the size of the received list, so a search result set is summarized on its own. Each
 * total is `null` exactly when its known count is `0`: a value nobody wrote is never a zero, and no
 * total is derived from another attribute (no surface from trees, no trees from surface). The
 * counts are the denominators the copy has to state, so a partial total can never read as a total
 * for every saved land. This layer formats nothing and holds no copy: the caller owns the wording
 * and formats with the accepted `formatHectares`/`formatTreeCount`.
 */
data class LandSummary(
    val total: Int,
    val surfaceTotal: Double?,
    val surfaceKnownCount: Int,
    val treeTotal: Long?,
    val treeKnownCount: Int,
)

/**
 * Totals the annotated surface and olive-tree count of [lands], in the order received.
 *
 * Only `areaHectares` and `treeCount` are read; no other attribute contributes to a total. The
 * surface sum is rounded once with [roundHectares] so the stored precision is kept, and the tree
 * sum accumulates in [Long] so many lands cannot wrap the total.
 */
fun summarizeLands(lands: List<Land>): LandSummary {
    var surfaceKnownCount = 0
    var surfaceSum = 0.0
    var treeKnownCount = 0
    var treeSum = 0L

    lands.forEach { land ->
        land.areaHectares?.let { value ->
            surfaceKnownCount += 1
            surfaceSum += value
        }
        land.treeCount?.let { value ->
            treeKnownCount += 1
            treeSum += value
        }
    }

    return LandSummary(
        total = lands.size,
        surfaceTotal = if (surfaceKnownCount == 0) null else roundHectares(surfaceSum),
        surfaceKnownCount = surfaceKnownCount,
        treeTotal = if (treeKnownCount == 0) null else treeSum,
        treeKnownCount = treeKnownCount,
    )
}
