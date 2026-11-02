package com.jamarglex.manijero.welcome

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class AndroidWelcomeNoticeStoreTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    @BeforeTest
    fun clearPreferences() {
        listOf(AndroidWelcomeNoticeStore.PREFERENCES_FILE, "manijero_lands").forEach { name ->
            context.getSharedPreferences(name, Context.MODE_PRIVATE).edit().clear().commit()
        }
    }

    @Test
    fun flagSurvivesANewInstance() {
        assertFalse(AndroidWelcomeNoticeStore(context).isDismissed())
        AndroidWelcomeNoticeStore(context).markDismissed()
        assertTrue(AndroidWelcomeNoticeStore(context).isDismissed())
    }

    @Test
    fun landStoreIsNotTouched() {
        val lands = context.getSharedPreferences("manijero_lands", Context.MODE_PRIVATE)
        lands.edit().putString("land_store", "sin tocar").commit()
        AndroidWelcomeNoticeStore(context).markDismissed()
        assertEquals(mapOf<String, Any?>("land_store" to "sin tocar"), lands.all)
    }
}
