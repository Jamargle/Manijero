package com.jamarglex.manijero

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import io.ktor.client.engine.android.Android
import com.jamarglex.manijero.chat.answerHttpClient
import com.jamarglex.manijero.platform.androidAskBaseUrl
import com.jamarglex.manijero.chat.KtorAnswerService
import com.jamarglex.manijero.lands.AndroidLandBackupFiles
import com.jamarglex.manijero.lands.ContentResolverBackupDocuments
import com.jamarglex.manijero.lands.LandRepository
import com.jamarglex.manijero.lands.SharedPreferencesLandStorage

class MainActivity : ComponentActivity() {
    private val localNetworkPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { }

    private val answerClient by lazy { answerHttpClient(Android.create()) }
    private val answerService by lazy { KtorAnswerService(answerClient, androidAskBaseUrl(BuildConfig.ASK_BASE_URL)) }
    private val landRepository by lazy {
        LandRepository(SharedPreferencesLandStorage(applicationContext))
    }

    // The portable land backup goes through the system document picker: the person chooses where
    // the file lives, and no storage permission is requested. Any file type can be picked because a
    // shared backup may arrive with a generic type; the shared validator refuses anything else.
    private val createBackupDocument = registerForActivityResult(
        ActivityResultContracts.CreateDocument("application/json"),
    ) { uri -> landBackupFiles.onCreateDocumentResult(uri) }

    private val openBackupDocument = registerForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri -> landBackupFiles.onOpenDocumentResult(uri) }

    private val landBackupFiles: AndroidLandBackupFiles by lazy {
        AndroidLandBackupFiles(
            documents = ContentResolverBackupDocuments(contentResolver),
            launchCreateDocument = { name -> createBackupDocument.launch(name) },
            launchOpenDocument = { openBackupDocument.launch(arrayOf("*/*")) },
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= 37 &&
            checkSelfPermission(Manifest.permission.ACCESS_LOCAL_NETWORK) != PackageManager.PERMISSION_GRANTED
        ) {
            localNetworkPermissionLauncher.launch(Manifest.permission.ACCESS_LOCAL_NETWORK)
        }

        setContent {
            App(landRepository, answerService, landBackupFiles)
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
