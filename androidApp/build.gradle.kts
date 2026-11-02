import com.android.build.api.variant.BuildConfigField
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.androidApplication)
    alias(libs.plugins.composeCompiler)
}

// Build target (client_environment_builds): the Gradle property `manijeroEnvironment` picks `local`
// (the default) or `qa`. A QA build is a separate app (`.qa` application id, label `Manijero QA`), points
// at the address in the git-ignored `qa-address.local` (or the placeholder), and sends the QA access key.
// A local build never reads the QA address file or the QA key.
val manijeroEnvironment: String = providers.gradleProperty("manijeroEnvironment").orElse("local").get()
if (manijeroEnvironment != "local" && manijeroEnvironment != "qa") {
    throw GradleException("manijeroEnvironment must be local or qa; prod is not configured.")
}
val qaBuild = manijeroEnvironment == "qa"

val qaPlaceholderAddress = "https://qa.manijero.invalid"
val qaAddressPattern = Regex(
    "^https://[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*" +
        "(:([0-9]{1,5}))?(/[A-Za-z0-9._~%!$&'()*+,;=:@/-]*)?$",
)
// The QA address: the test override file or `qa-address.local`, or the
// placeholder when there is no file. Read only for QA builds; a bad file fails without echoing it.
val qaAskBaseUrl: String? = if (qaBuild) {
    val addressFile = rootProject.layout.projectDirectory.file(
        providers.environmentVariable("MANIJERO_QA_ADDRESS_FILE").orElse("qa-address.local"),
    )
    val raw = providers.fileContents(addressFile).asText.orNull
    if (raw == null) {
        logger.quiet(
            "The QA address is a placeholder ($qaPlaceholderAddress) until the QA server is chosen; " +
                "this app cannot reach QA yet.",
        )
        qaPlaceholderAddress
    } else {
        val address = raw.trim().trimEnd('/')
        val port = qaAddressPattern.matchEntire(address)?.groups?.get(5)?.value?.toInt()
        if (address.length > 512 || !qaAddressPattern.matches(address) || (port != null && port !in 1..65535)) {
            throw GradleException(
                "qa-address.local is not a valid QA address. Write one https:// address on one line, for example https://qa.example.org",
            )
        }
        address
    }
} else {
    null
}

// Pilot bearer token (client_pilot_credentials): a local build reads only the git-ignored
// `pilot-token.local` at the repository root; a QA build reads only the QA access key made by
// ./scripts/init.sh --qa-settings-setup. MANIJERO_PILOT_TOKEN_FILE overrides either path (tests and
// checks use fake files). Never from the SDK properties file. The file is read lazily, only when
// BuildConfig is generated, so a malformed file fails app builds without echoing its content and
// leaves other tasks untouched.
val localPilotTokenFile: Provider<RegularFile> = rootProject.layout.projectDirectory.file(
    providers.environmentVariable("MANIJERO_PILOT_TOKEN_FILE").orElse("pilot-token.local"),
)
val qaAccessKeyFile: Provider<RegularFile> = rootProject.layout.projectDirectory.file(
    providers.environmentVariable("MANIJERO_PILOT_TOKEN_FILE").orElse(
        providers.environmentVariable("MANIJERO_QA_HOME").orElse(System.getProperty("user.home") + "/manijero/qa")
            .map { "$it/credentials/qa-test-device.token" },
    ),
)
val pilotTokenFile: Provider<RegularFile> = if (qaBuild) qaAccessKeyFile else localPilotTokenFile
val pilotTokenInvalidMessage: String = if (qaBuild) {
    "The QA access key is not valid. Run ./scripts/init.sh --qa-settings-setup again."
} else {
    "pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again."
}
// The message is copied into a local so the lambda holds no reference to the script object.
val pilotTokenBuildConfigValue: Provider<String> = pilotTokenInvalidMessage.let { invalidMessage ->
    providers.fileContents(pilotTokenFile).asText
        .map { raw ->
            val token = raw.trim()
            if (token.length !in 32..512 || !Regex("^[A-Za-z0-9._~+/-]+=*$").matches(token)) {
                throw GradleException(invalidMessage)
            }
            "\"$token\""
        }
        .orElse("null")
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
        if (qaBuild) applicationIdSuffix = ".qa"
        manifestPlaceholders["appLabel"] = if (qaBuild) "Manijero QA" else "@string/app_name"
        minSdk = libs.versions.android.minSdk.get().toInt()
        targetSdk = libs.versions.android.targetSdk.get().toInt()
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // QA ignores manijeroAskBaseUrl, so a QA app never targets a local address by default.
        val askBaseUrl = qaAskBaseUrl ?: providers.gradleProperty("manijeroAskBaseUrl").orElse("http://10.0.2.2:8000").get()
        buildConfigField("String", "ASK_BASE_URL", "\"$askBaseUrl\"")
        buildConfigField("String", "MANIJERO_ENVIRONMENT", "\"$manijeroEnvironment\"")
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
        // Only debug carries the pilot token; release gets PILOT_TOKEN = null. See androidComponents.
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

// Only debug (test) builds may carry the pilot token (owner decision 5): debug gets the quoted
// token when one is saved, or the literal `null`. Every other build type, including release, gets a
// constant `null` that never touches the token file, so the field stays declared for src/main but
// the token is never read, validated, or a release task input. MainActivity turns the field into a
// PilotToken, which re-checks the shape.
androidComponents {
    onVariants { variant ->
        if (variant.buildType == "debug") {
            variant.buildConfigFields?.put(
                "PILOT_TOKEN",
                pilotTokenBuildConfigValue.map { BuildConfigField("String", it, null) },
            )
        } else {
            variant.buildConfigFields?.put("PILOT_TOKEN", BuildConfigField("String", "null", null))
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
