package com.jamarglex.manijero.privacy

/**
 * One land attribute that may leave the device with a land-aware question. It mirrors exactly the
 * optional dimensions `chat/LandContextBuilder.landContextNeeds` can request; a fourth sendable
 * attribute must update this enum (a test fails otherwise), so the notice cannot under-describe the
 * payload.
 *
 * Standard-library only: no Compose, no I/O. Adding a sendable dimension is a spec and test change,
 * never a silent one.
 */
enum class SharedLandAttribute { MUNICIPALITY, WATER_REGIME, PRODUCTION_METHOD }

/**
 * The pinned order the on-screen copy renders. The notice lists the sendable attributes in this
 * order, and [SharedLandAttribute] plus this list are the single source the payload-correspondence
 * test checks against the real encoded request.
 */
val SHARED_LAND_ATTRIBUTES: List<SharedLandAttribute> = listOf(
    SharedLandAttribute.MUNICIPALITY,
    SharedLandAttribute.WATER_REGIME,
    SharedLandAttribute.PRODUCTION_METHOD,
)
