package com.jamarglex.manijero.connection

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The Android address store keeps the one remembered address in its own private preferences file
 * and never touches the land store. Robolectric supplies the preferences on the host JVM.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidServiceAddressStoreTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @BeforeTest
    fun clearPreferences() {
        listOf(AndroidServiceAddressStore.PREFERENCES_FILE, "manijero_lands").forEach { name ->
            context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear().commit()
        }
    }

    @Test
    fun address_round_trips_and_clears_in_its_own_preferences_file() {
        val lands = context.getSharedPreferences("manijero_lands", Context.MODE_PRIVATE)
        lands.edit().putString("land_store", "sin tocar").commit()
        val store = AndroidServiceAddressStore(context)
        assertNull(store.load())

        store.save("http://192.168.1.20:8000")
        assertEquals("http://192.168.1.20:8000", AndroidServiceAddressStore(context).load())
        assertEquals(
            setOf("http://192.168.1.20:8000"),
            context.getSharedPreferences("manijero_connection", Context.MODE_PRIVATE).all.values.toSet(),
        )

        store.clear()
        assertNull(store.load())
        assertEquals(mapOf<String, Any?>("land_store" to "sin tocar"), lands.all)
    }

    @Test
    fun active_address_survives_a_new_store_instance_like_a_restart() {
        ActiveServiceAddress("http://10.0.2.2:8000", AndroidServiceAddressStore(context))
            .save("http://192.168.1.20:8000")

        val restarted = ActiveServiceAddress("http://10.0.2.2:8000", AndroidServiceAddressStore(context))
        assertEquals("http://192.168.1.20:8000", restarted.current)
        assertEquals(ServiceAddressSource.Saved, restarted.source)
    }
}
