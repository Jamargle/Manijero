package com.jamarglex.manijero.connection

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** In-memory store whose reads and writes can be made to fail. */
internal class FakeAddressStore(
    var saved: String? = null,
    var failLoad: Boolean = false,
    var failWrites: Boolean = false,
) : ServiceAddressStore {
    var writes = 0
        private set

    override fun load(): String? {
        if (failLoad) error("unreadable")
        return saved
    }

    override fun save(address: String) {
        writes++
        if (failWrites) error("refused")
        saved = address
    }

    override fun clear() {
        writes++
        if (failWrites) error("refused")
        saved = null
    }
}

private const val DEFAULT_URL = "http://10.0.2.2:8000"
private const val LAN_URL = "http://192.168.1.20:8000"

class ActiveServiceAddressTest {
    @Test
    fun `the build default is used when nothing is saved`() {
        val address = ActiveServiceAddress(DEFAULT_URL, FakeAddressStore())
        assertEquals(DEFAULT_URL, address.current)
        assertEquals(ServiceAddressSource.Default, address.source)
    }

    @Test
    fun `a saved address wins over the default`() {
        val address = ActiveServiceAddress(DEFAULT_URL, FakeAddressStore(saved = LAN_URL))
        assertEquals(LAN_URL, address.current)
        assertEquals(ServiceAddressSource.Saved, address.source)
    }

    @Test
    fun `an invalid or unreadable stored value falls back to the default`() {
        listOf(
            FakeAddressStore(saved = "not an address"),
            FakeAddressStore(saved = "ftp://192.168.1.20"),
            FakeAddressStore(saved = ""),
            FakeAddressStore(saved = LAN_URL, failLoad = true),
        ).forEach { store ->
            val address = ActiveServiceAddress(DEFAULT_URL, store)
            assertEquals(DEFAULT_URL, address.current)
            assertEquals(ServiceAddressSource.Default, address.source)
        }
    }

    @Test
    fun `save and reset apply in memory immediately`() {
        val store = FakeAddressStore()
        val address = ActiveServiceAddress(DEFAULT_URL, store)

        assertTrue(address.save(LAN_URL))
        assertEquals(LAN_URL, address.current)
        assertEquals(ServiceAddressSource.Saved, address.source)
        assertEquals(LAN_URL, store.saved)

        assertTrue(address.reset())
        assertEquals(DEFAULT_URL, address.current)
        assertEquals(ServiceAddressSource.Default, address.source)
        assertNull(store.saved)
    }

    @Test
    fun `a refused save or clear leaves the address in use unchanged`() {
        val store = FakeAddressStore(saved = LAN_URL, failWrites = true)
        val address = ActiveServiceAddress(DEFAULT_URL, store)

        assertFalse(address.save("http://10.0.0.5:8000"))
        assertEquals(LAN_URL, address.current)
        assertEquals(ServiceAddressSource.Saved, address.source)

        assertFalse(address.reset())
        assertEquals(LAN_URL, address.current)
        assertEquals(ServiceAddressSource.Saved, address.source)
    }
}
