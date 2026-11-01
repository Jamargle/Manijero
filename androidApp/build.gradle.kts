import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.androidApplication)
    alias(libs.plugins.composeCompiler)
}

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

    // Test-only: the instrumented local smoke check (./scripts/init.sh --local-smoke). It runs in the
    // debug app's process; the release dependency graph is unchanged.
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.espresso.core)
    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.compose.uiTestJunit4)
    debugImplementation(libs.androidx.compose.uiTestManifest)
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
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
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

// The instrumented local smoke check runs on API 37. Espresso before 3.6 reflects on
// InputManager.getInstance, which API 34+ removed, so the test crashes before it starts. This
// offline check resolves the androidTest classpath and fails when espresso-core is older than
// 3.6.1 (local_end_to_end_smoke focused verification).
fun espressoCoreVersions() = configurations.named("debugAndroidTestRuntimeClasspath").flatMap { classpath ->
    classpath.incoming.resolutionResult.rootComponent.map { root ->
        val seen = mutableSetOf<org.gradle.api.artifacts.result.ResolvedComponentResult>()
        val queue = ArrayDeque(listOf(root))
        val versions = mutableListOf<String>()
        while (queue.isNotEmpty()) {
            val component = queue.removeFirst()
            if (!seen.add(component)) continue
            val id = component.moduleVersion
            if (id != null && id.group == "androidx.test.espresso" && id.name == "espresso-core") versions += id.version
            component.dependencies
                .filterIsInstance<org.gradle.api.artifacts.result.ResolvedDependencyResult>()
                .forEach { queue.addLast(it.selected) }
        }
        versions.distinct().joinToString(",")
    }
}

tasks.register("verifyAndroidTestDependencies") {
    group = "verification"
    description = "Fail when the androidTest classpath resolves espresso-core older than 3.6.1 (API 34+ support)."
    // Configured lazily, after AGP has created the androidTest configurations.
    val resolved = espressoCoreVersions()
    inputs.property("espressoCore", resolved)
    doLast {
        val versions = resolved.get().split(',').filter(String::isNotBlank)
        check(versions.size == 1) { "expected exactly one espresso-core on debugAndroidTestRuntimeClasspath, found $versions" }
        val parts = versions.single().split('.', '-').take(3).map { it.toIntOrNull() ?: 0 }
        val (major, minor, patch) = parts + List(3 - parts.size) { 0 }
        val supported = major > 3 || (major == 3 && (minor > 6 || (minor == 6 && patch >= 1)))
        check(supported) { "espresso-core ${versions.single()} is older than 3.6.1 and crashes on API 34+" }
    }
}
