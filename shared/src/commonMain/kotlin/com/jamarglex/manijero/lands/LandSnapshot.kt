package com.jamarglex.manijero.lands

/**
 * One land the person moved out of `Mis terrenos`, kept on the device so it can be restored.
 *
 * [land] is the record exactly as it was saved: moving a land in or out of this list rewrites no
 * field, and [removedAtEpochMillis] only records when the move happened. A removed land is never part
 * of the active list, the chat context, or an answer request.
 */
data class RemovedLand(
    val land: Land,
    val removedAtEpochMillis: Long,
)

/**
 * The whole local land aggregate: the active lands the person keeps using plus the removed lands they
 * may still restore or delete permanently.
 *
 * Each list keeps its own documented order. [active] stays in creation order and a restored land is
 * appended at the end, so a restore can never reorder the lands the person did not touch. [removed]
 * stays in removal order, so the list reads the way the person emptied it and a restore never shuffles
 * the others.
 */
data class LandSnapshot(
    val active: List<Land> = emptyList(),
    val removed: List<RemovedLand> = emptyList(),
)

/**
 * What one lifecycle transition did, so the surface can tell a record that is no longer there from a
 * device that refused the write. No member ever implies that a write happened: only [Done] does.
 */
sealed interface LandLifecycleResult {
    /** The whole aggregate was written; [land] is the record the transition acted on, unchanged. */
    data class Done(val land: Land) : LandLifecycleResult

    /** No record with that id was in the list the transition reads, so nothing was written. */
    data object Missing : LandLifecycleResult

    /** The device refused the write; the stored aggregate is unchanged. */
    data object StorageFailed : LandLifecycleResult
}
