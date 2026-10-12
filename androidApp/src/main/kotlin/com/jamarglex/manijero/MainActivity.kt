package com.jamarglex.manijero

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.SharedPreferencesLandStorage

class MainActivity : ComponentActivity() {
    private val landRepository by lazy {
        LandRepository(SharedPreferencesLandStorage(applicationContext))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            App(landRepository)
        }
    }
}

@Preview
@Composable
fun AppAndroidPreview() {
    App()
}
