package com.jamarglex.manijero.lands

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

/**
 * The largest portable backup file the app reads or writes, in UTF-8 bytes.
 *
 * A complete land record is well under a kilobyte, so this leaves room for tens of thousands of
 * lands while refusing to load an unrelated large file (a photo, a video) into memory. The exporter
 * refuses to write a file above this size, so the app never produces a file it would then reject.
 */
const val MAX_LAND_BACKUP_BYTES: Int = 4 * 1024 * 1024

/** The file name the save dialog suggests. The person can change it and its location. */
const val LAND_BACKUP_SUGGESTED_FILE_NAME: String = "manijero-terrenos.json"

/** Why a file was not accepted as a backup. Every case leaves the store and its copies untouched. */
enum class LandBackupProblem {
    /** The file is larger than [MAX_LAND_BACKUP_BYTES]. */
    TOO_LARGE,

    /** The file is not a Manijero land backup at all (another document, a photo, random text). */
    NOT_A_BACKUP,

    /** The file is a Manijero backup of a format version this app does not read. */
    UNSUPPORTED_VERSION,

    /** The file claims to be a backup but is truncated, malformed, or fails its integrity check. */
    DAMAGED,

    /** The file is well formed but its records break a land rule (a repeated id, a blank zone…). */
    INVALID_CONTENT,
}

/** The outcome of reading one candidate backup file: the complete aggregate, or why it was refused. */
sealed interface LandBackupDecodeResult {
    data class Valid(val snapshot: LandSnapshot) : LandBackupDecodeResult

    data class Invalid(val problem: LandBackupProblem) : LandBackupDecodeResult
}

/**
 * The portable land backup: one plaintext JSON file that Android and Desktop both write and read.
 *
 * This is the **external** contract, deliberately separate from the private `land-store-v2` codec
 * ([LandStoreFormat]): the private store may change shape without breaking files people already keep.
 *
 * ```json
 * {
 *   "format": "manijero-land-backup",
 *   "version": 1,
 *   "checksum": "fnv1a64:<hex>",
 *   "lands": {
 *     "active":  [ { "id": "…", "name": "…", "zone": "…", "waterRegime": "DRYLAND", … } ],
 *     "removed": [ { "land": { … }, "removedAtEpochMillis": 0 } ]
 *   }
 * }
 * ```
 *
 * - Only land data is written: no chat history, request log, device identifier, account, or service
 *   data. An absent optional value is omitted, never written as zero or as an empty string.
 * - `checksum` is FNV-1a 64 over the compact canonical JSON of `lands`, so it ignores whitespace and
 *   escaping differences but catches a truncated or altered record list.
 * - [decode] validates the **whole** file before anything else may look at it: size, format marker,
 *   version, strict shape (unknown or missing keys are refused), checksum, every record value, and
 *   ids unique across both lists. It returns the aggregate only when every record is valid.
 * - Record values follow the rules every stored land already satisfies, so any file this exporter
 *   wrote from a readable store is accepted back unchanged.
 */
object LandBackupFormat {
    const val FORMAT: String = "manijero-land-backup"
    const val VERSION: Int = 1
    private const val CHECKSUM_PREFIX = "fnv1a64:"
    private const val BYTE_ORDER_MARK = '﻿'

    private val fileJson = Json {
        prettyPrint = true
        encodeDefaults = true
        explicitNulls = false
    }

    private val canonicalJson = Json {
        encodeDefaults = true
        explicitNulls = false
    }

    // Strict reading: unknown keys, lenient literals, and NaN/Infinity are refused.
    private val strictJson = Json {
        ignoreUnknownKeys = false
        isLenient = false
        explicitNulls = false
        allowSpecialFloatingPointValues = false
    }

    /** The complete backup file for [snapshot], active and removed lands in their stored order. */
    fun encode(snapshot: LandSnapshot): String = encodeFile(snapshot.toPortable())

    /** Writes [lands] as a file with a correct checksum; tests use it to build well-formed edge cases. */
    internal fun encodeFile(lands: PortableLands, version: Int = VERSION): String {
        val file = PortableLandBackupFile(
            format = FORMAT,
            version = version,
            checksum = checksumOf(lands),
            lands = lands,
        )
        return fileJson.encodeToString(PortableLandBackupFile.serializer(), file) + "\n"
    }

    internal fun portable(snapshot: LandSnapshot): PortableLands = snapshot.toPortable()

    /** Reads one candidate file completely; nothing is returned unless the whole file is valid. */
    fun decode(text: String): LandBackupDecodeResult {
        if (text.length > MAX_LAND_BACKUP_BYTES) return invalid(LandBackupProblem.TOO_LARGE)
        val content = text.removePrefix(BYTE_ORDER_MARK.toString())
        val element = runCatching { strictJson.parseToJsonElement(content) }.getOrNull()
            ?: return invalid(
                if (content.contains(FORMAT)) LandBackupProblem.DAMAGED else LandBackupProblem.NOT_A_BACKUP,
            )
        val header = element as? JsonObject ?: return invalid(LandBackupProblem.NOT_A_BACKUP)
        val format = header["format"] as? JsonPrimitive
        if (format == null || !format.isString || format.content != FORMAT) {
            return invalid(LandBackupProblem.NOT_A_BACKUP)
        }
        val version = (header["version"] as? JsonPrimitive)?.takeUnless { it.isString }?.intOrNull
            ?: return invalid(LandBackupProblem.DAMAGED)
        if (version != VERSION) return invalid(LandBackupProblem.UNSUPPORTED_VERSION)

        val file = runCatching {
            strictJson.decodeFromJsonElement(PortableLandBackupFile.serializer(), element)
        }.getOrNull() ?: return invalid(LandBackupProblem.DAMAGED)
        if (file.checksum != checksumOf(file.lands)) return invalid(LandBackupProblem.DAMAGED)

        val snapshot = file.lands.toSnapshotOrNull() ?: return invalid(LandBackupProblem.INVALID_CONTENT)
        val ids = snapshot.active.map { it.id } + snapshot.removed.map { it.land.id }
        if (ids.size != ids.toSet().size) return invalid(LandBackupProblem.INVALID_CONTENT)
        return LandBackupDecodeResult.Valid(snapshot)
    }

    private fun checksumOf(lands: PortableLands): String =
        CHECKSUM_PREFIX + fnv1a64Hex(canonicalJson.encodeToString(PortableLands.serializer(), lands))

    private fun invalid(problem: LandBackupProblem) = LandBackupDecodeResult.Invalid(problem)
}

@Serializable
internal data class PortableLandBackupFile(
    val format: String,
    val version: Int,
    val checksum: String,
    val lands: PortableLands,
)

@Serializable
internal data class PortableLands(
    val active: List<PortableLand>,
    val removed: List<PortableRemovedLand>,
)

@Serializable
internal data class PortableRemovedLand(
    val land: PortableLand,
    val removedAtEpochMillis: Long,
)

/**
 * One land in the portable file. Enum values are written by their stable names; they are kept as
 * text here so an unknown value is reported as invalid content instead of a parser failure.
 */
@Serializable
internal data class PortableLand(
    val id: String,
    val name: String,
    val zone: String,
    val municipality: String? = null,
    val waterRegime: String,
    val productionMethod: String,
    val variety: String,
    val varietyOther: String? = null,
    val areaHectares: Double? = null,
    val treeCount: Int? = null,
    val notes: String? = null,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
)

private fun LandSnapshot.toPortable() = PortableLands(
    active = active.map { it.toPortable() },
    removed = removed.map { PortableRemovedLand(it.land.toPortable(), it.removedAtEpochMillis) },
)

private fun Land.toPortable() = PortableLand(
    id = id,
    name = name,
    zone = zone,
    municipality = municipality,
    waterRegime = waterRegime.name,
    productionMethod = productionMethod.name,
    variety = variety.name,
    varietyOther = varietyOther,
    areaHectares = areaHectares,
    treeCount = treeCount,
    notes = notes,
    createdAtEpochMillis = createdAtEpochMillis,
    updatedAtEpochMillis = updatedAtEpochMillis,
)

private fun PortableLands.toSnapshotOrNull(): LandSnapshot? {
    val activeLands = active.map { it.toLandOrNull() ?: return null }
    val removedLands = removed.map { removed ->
        RemovedLand(
            land = removed.land.toLandOrNull() ?: return null,
            removedAtEpochMillis = removed.removedAtEpochMillis,
        )
    }
    return LandSnapshot(active = activeLands, removed = removedLands)
}

/**
 * One record, or `null` when any value breaks a rule every stored land satisfies: a non-empty id and
 * name, a non-blank zone, known enum names, custom variety text only (and always) for `OTHER`, a
 * finite non-negative surface, at least one tree, and no empty text standing in for an absent value.
 */
private fun PortableLand.toLandOrNull(): Land? {
    if (id.isEmpty() || name.isEmpty() || zone.isBlank()) return null
    val water = WaterRegime.entries.firstOrNull { it.name == waterRegime } ?: return null
    val production = ProductionMethod.entries.firstOrNull { it.name == productionMethod } ?: return null
    val landVariety = LandVariety.entries.firstOrNull { it.name == variety } ?: return null
    if (landVariety == LandVariety.OTHER) {
        if (varietyOther.isNullOrBlank()) return null
    } else if (varietyOther != null) {
        return null
    }
    val area = areaHectares
    if (area != null && (!area.isFinite() || area < 0.0)) return null
    val trees = treeCount
    if (trees != null && trees < 1) return null
    if (municipality?.isEmpty() == true || notes?.isEmpty() == true) return null
    return Land(
        id = id,
        name = name,
        zone = zone,
        municipality = municipality,
        waterRegime = water,
        productionMethod = production,
        variety = landVariety,
        varietyOther = varietyOther,
        areaHectares = area,
        treeCount = trees,
        notes = notes,
        createdAtEpochMillis = createdAtEpochMillis,
        updatedAtEpochMillis = updatedAtEpochMillis,
    )
}
