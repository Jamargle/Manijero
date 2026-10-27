package com.jamarglex.manijero.lands

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
 * Android storage check for the same-device automatic copies: they rotate in the app's private
 * preferences file, stay bounded, and let the repository recover a damaged primary value. Robolectric
 * supplies the preferences implementation on the host JVM; no device is involved.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidLandStorageTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @BeforeTest
    fun clearPrivateStore() {
        context.getSharedPreferences("manijero_lands", Context.MODE_PRIVATE)
            .edit()
            .clear()
            .commit()
    }

    @Test
    fun automatic_copies_rotate_in_the_private_preferences_file() {
        val storage = SharedPreferencesLandStorage(context)
        repeat(5) { index -> storage.writeSnapshot("copia-$index") }

        assertEquals(
            listOf("copia-4", "copia-3", "copia-2"),
            storage.readSnapshots(),
            "the newest copy is first and the retained count stays bounded",
        )

        storage.replaceSnapshots(listOf("limpia"))
        assertEquals(listOf("limpia"), storage.readSnapshots())

        storage.writePurgeMarker("land-1")
        assertEquals("land-1", storage.readPurgeMarker())
        storage.writePurgeMarker(null)
        assertNull(storage.readPurgeMarker())
    }

    @Test
    fun a_damaged_primary_value_is_recovered_from_the_private_copy() {
        var next = 0
        val storage = SharedPreferencesLandStorage(context)
        val writer = LandRepository(
            storage = storage,
            idGenerator = { "land-${next++}" },
        )
        val first = writer.create(LandDraft("Los Olivos", "El Llano"), now = 1)
        val second = writer.create(LandDraft("La Loma", "La Vega"), now = 2)
        // Damage the primary value in place; the copies stay as the private preferences wrote them.
        storage.write("no es un almacén de terrenos")

        val reopened = LandRepository(storage, storage)

        assertEquals(listOf(first, second), reopened.list())
        assertEquals(
            LandStoreRecovery.RESTORED_FROM_AUTOMATIC_COPY,
            reopened.consumeRecovery(),
        )
        assertEquals(
            LandStoreFormat.encode(LandSnapshot(active = listOf(first, second))),
            storage.read(),
            "the recovered aggregate is written back to the primary value",
        )
    }
}
