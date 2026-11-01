package com.jamarglex.manijero.connection

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class LocalSmokeTest {

    @Test
    fun codesAreUniqueStableAndOnlyAnsweredOrAbstainedPass() {
        assertEquals(
            listOf(
                "answered", "abstained", "answered_without_sources", "land_clarification", "unreachable",
                "service_error", "not_ready", "ready_unknown", "not_manijero", "other_address", "no_answer", "error",
            ),
            SmokeOutcome.entries.map { it.code },
        )
        assertEquals(SmokeOutcome.entries.size, SmokeOutcome.entries.map { it.code }.toSet().size)
        assertEquals(setOf(SmokeOutcome.Answered, SmokeOutcome.Abstained), SmokeOutcome.entries.filter { it.passes }.toSet())
    }

    @Test
    fun theSameAddressAfterNormalizationIsNotADifferentAddress() {
        assertNull(smokeAddressOutcome("http://127.0.0.1:8000", "http://127.0.0.1:8000"))
        assertNull(smokeAddressOutcome(" HTTP://127.0.0.1:8000/ ", "http://127.0.0.1:8000"))
        assertNull(smokeAddressOutcome("http://10.0.2.2:8765", "http://10.0.2.2:8765/"))
    }

    @Test
    fun aDifferentPortHostSchemeOrUnusableAddressIsOtherAddress() {
        val expected = "http://127.0.0.1:8000"
        listOf(
            "http://127.0.0.1:8001",
            "http://127.0.0.1",
            "http://localhost:8000",
            "https://127.0.0.1:8000",
            "http://10.0.2.2:8000",
            "http://127.0.0.1:8000/api",
            "not an address",
            "",
        ).forEach { inUse ->
            assertEquals(SmokeOutcome.OtherAddress, smokeAddressOutcome(inUse, expected), inUse)
        }
        assertEquals(SmokeOutcome.OtherAddress, smokeAddressOutcome(expected, "garbage"))
    }

    @Test
    fun eachProbeResultMapsToOneOutcome() {
        assertNull(smokeOutcomeFor(ServiceCheckResult.Ready))
        assertEquals(SmokeOutcome.NotReady, smokeOutcomeFor(ServiceCheckResult.NotReady))
        assertEquals(SmokeOutcome.ReadyUnknown, smokeOutcomeFor(ServiceCheckResult.ReadyUnknown))
        assertEquals(SmokeOutcome.Unreachable, smokeOutcomeFor(ServiceCheckResult.Unreachable))
        assertEquals(SmokeOutcome.NotManijero, smokeOutcomeFor(ServiceCheckResult.NotManijero))
    }

    @Test
    fun theScreenIsClassifiedWithSourcesFirst() {
        assertEquals(SmokeOutcome.Answered, smokeOutcomeFor(SmokeScreen(answered = true, sourceCards = 2)))
        assertEquals(SmokeOutcome.AnsweredWithoutSources, smokeOutcomeFor(SmokeScreen(answered = true)))
        assertEquals(SmokeOutcome.Abstained, smokeOutcomeFor(SmokeScreen(abstained = true)))
        assertEquals(SmokeOutcome.LandClarification, smokeOutcomeFor(SmokeScreen(landClarification = true)))
        assertEquals(SmokeOutcome.ServiceError, smokeOutcomeFor(SmokeScreen(serviceError = true)))
        assertEquals(SmokeOutcome.Unreachable, smokeOutcomeFor(SmokeScreen(unreachable = true)))
        assertEquals(SmokeOutcome.NoAnswer, smokeOutcomeFor(SmokeScreen()))
        assertFalse(SmokeScreen(sourceCards = 3).settled)
        assertTrue(SmokeScreen(unreachable = true).settled)
    }

    @Test
    fun theResultLineCarriesOnlyTheCodeCountSourceAndAddress() {
        val line = smokeResultLine(SmokeReport(SmokeOutcome.Answered, 2, ServiceAddressSource.Default, "http://127.0.0.1:8000"))
        assertEquals("MANIJERO_SMOKE_RESULT outcome=answered sources=2 address=default url=http://127.0.0.1:8000", line)
        assertFalse(LOCAL_SMOKE_QUESTION in line)
        assertFalse("solicitud" in line.lowercase())

        val saved = smokeResultLine(SmokeReport(SmokeOutcome.OtherAddress, -1, ServiceAddressSource.Saved, "http://Host.Example:9/x/"))
        assertEquals("MANIJERO_SMOKE_RESULT outcome=other_address sources=0 address=saved url=http://host.example:9/x", saved)

        val odd = smokeResultLine(SmokeReport(SmokeOutcome.Error, 0, ServiceAddressSource.Saved, "http://a b"))
        assertEquals("MANIJERO_SMOKE_RESULT outcome=error sources=0 address=saved url=invalid", odd)
    }

    @Test
    fun theReadOnlyStoreReadsButRefusesEveryWrite() {
        val inner = object : ServiceAddressStore {
            var writes = 0
            override fun load(): String = "http://10.0.2.2:8000"
            override fun save(address: String) { writes++ }
            override fun clear() { writes++ }
        }
        val store = ReadOnlyServiceAddressStore(inner)
        assertEquals("http://10.0.2.2:8000", store.load())
        assertFailsWith<UnsupportedOperationException> { store.save("http://x") }
        assertFailsWith<UnsupportedOperationException> { store.clear() }

        val address = ActiveServiceAddress("http://10.0.2.2:8000", store)
        assertFalse(address.save("http://10.0.2.2:9000"))
        assertFalse(address.reset())
        assertEquals(0, inner.writes)
    }
}
