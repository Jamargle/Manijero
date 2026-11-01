import com.android.build.api.variant.BuildConfigField
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.androidApplication)
    alias(libs.plugins.composeCompiler)
}

// Pilot bearer token (client_pilot_credentials): only from the git-ignored `pilot-token.local` at the
// repository root, or the file named by MANIJERO_PILOT_TOKEN_FILE (tests and checks use fake files).
// Never from the SDK properties file. The file is read lazily, only when BuildConfig is generated, so a
// malformed file fails app builds without echoing its content and leaves other tasks untouched.
val pilotTokenFile: Provider<RegularFile> = rootProject.layout.projectDirectory.file(
    providers.environmentVariable("MANIJERO_PILOT_TOKEN_FILE").orElse("pilot-token.local"),
)
val pilotTokenBuildConfigValue: Provider<String> = providers.fileContents(pilotTokenFile).asText
    .map { raw ->
        val token = raw.trim()
        if (token.length !in 32..512 || !Regex("^[A-Za-z0-9._~+/-]+=*$").matches(token)) {
            throw GradleException(
                "pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again.",
            )
        }
        "\"$token\""
    }
    .orElse("null")

kotlin {
    compilerOptions {
        jvmTarget = JvmTarget.JVM_11
    }
}
dependencies {
    implementation(project(":shared"))

    implementation(libs.androidx.activity.compose)
    implementation(libs.ktor.client.android)

    implementation(libs.compose.uiToolingPreview)
    debugImplementation(libs.compose.uiTooling)
}

android {
    namespace = "com.jamarglex.manijero"
    compileSdk = libs.versions.android.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "com.jamarglex.manijero"
        minSdk = libs.versions.android.minSdk.get().toInt()
        targetSdk = libs.versions.android.targetSdk.get().toInt()
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "ASK_BASE_URL", "\"${providers.gradleProperty("manijeroAskBaseUrl").orElse("http://10.0.2.2:8000").get()}\"")
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    buildTypes {
        // Every variant (debug and release) gets the same PILOT_TOKEN field; see androidComponents.
        debug { manifestPlaceholders["usesCleartextTraffic"] = "true" }
        release {
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
}

// `PILOT_TOKEN` is the quoted token when one is saved and the literal `null` otherwise, for every
// variant. MainActivity turns it into a PilotToken, which re-checks the shape.
androidComponents {
    onVariants { variant ->
        variant.buildConfigFields?.put(
            "PILOT_TOKEN",
            pilotTokenBuildConfigValue.map { BuildConfigField("String", it, null) },
        )
    }
}
