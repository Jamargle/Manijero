package com.jamarglex.manijero

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import io.ktor.client.engine.android.Android
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.platform.androidAskBaseUrl
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.SharedPreferencesLandStorage

class MainActivity : ComponentActivity() {
    private val answerClient by lazy { answerHttpClient(Android.create()) }
    private val answerService by lazy { KtorAnswerService(answerClient, androidAskBaseUrl(BuildConfig.ASK_BASE_URL)) }
    private val landRepository by lazy {
        LandRepository(SharedPreferencesLandStorage(applicationContext))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            App(landRepository, answerService)
        }
    }

    override fun onDestroy() {
        answerClient.close()
        super.onDestroy()
    }
}

@Preview
@Composable
fun AppAndroidPreview() {
    App()
}
