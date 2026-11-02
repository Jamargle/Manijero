import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    alias(libs.plugins.kotlinJvm)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
}

dependencies {
    implementation(project(":shared"))
    implementation(libs.ktor.client.cio)

    implementation(compose.desktop.currentOs)
    implementation(libs.kotlinx.coroutinesSwing)
    implementation(libs.compose.uiToolingPreview)
}

// Build target (client_environment_builds): the Gradle property `manijeroEnvironment` picks `local`
// (the default) or `qa`; androidApp/build.gradle.kts applies the same rules. A QA build uses the address
// in the git-ignored `qa-address.local` (or the placeholder), its own data folder, and the QA access key.
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
val qaAskBaseUrl: String? = if (qaBuild) {
    val addressFile = rootProject.layout.projectDirectory.file(
        providers.environmentVariable("MANIJERO_QA_ADDRESS_FILE").orElse("qa-address.local"),
    )
    val raw = providers.fileContents(addressFile).asText.orNull
    if (raw == null) {
        // The notice about the placeholder is printed once, by androidApp/build.gradle.kts (every build
        // configures both apps).
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

// Non-secret environment resource (`manijero/environment.properties`, read by `desktopEnvironment()`):
// the environment name and, in QA, the address. It is on the main resources, so jars carry it; it
// holds no token. Its inputs are the two values, so switching local and QA never reuses a stale file.
val generateEnvironmentResource = tasks.register("generateEnvironmentResource") {
    val environmentName = manijeroEnvironment
    val address = qaAskBaseUrl ?: ""
    val outputDirectory = layout.buildDirectory.dir("generated/environment")
    inputs.property("environment", environmentName)
    inputs.property("askBaseUrl", address)
    outputs.dir(outputDirectory)
    doLast {
        val output = outputDirectory.get().asFile
        output.deleteRecursively()
        output.resolve("manijero").mkdirs()
        val lines = buildList {
            add("environment=" + environmentName)
            if (address.isNotEmpty()) add("askBaseUrl=" + address)
        }
        output.resolve("manijero/environment.properties").writeText(lines.joinToString("\n", postfix = "\n"))
    }
}
sourceSets.named("main") {
    resources.srcDir(generateEnvironmentResource)
}

// Pilot bearer token (client_pilot_credentials): a local build reads only the git-ignored
// `pilot-token.local` at the repository root; a QA build reads only the QA access key made by
// ./scripts/init.sh --qa-settings-setup. MANIJERO_PILOT_TOKEN_FILE overrides either path (tests and
// checks use fake files).
// The task declares the file, never its value, as an input, and writes the classpath resource that
// `desktopPilotToken()` reads. Only the development `run` task has that folder on its classpath
// (owner decision 5), so `jar`, packaged, and release outputs never contain the token. No token
// file: no resource.
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
val generatePilotTokenResource = tasks.register("generatePilotTokenResource") {
    val tokenFile = pilotTokenFile
    val outputDirectory = layout.buildDirectory.dir("generated/pilotToken")
    val invalidMessage = pilotTokenInvalidMessage
    inputs.files(tokenFile).withPropertyName("pilotTokenFile").withPathSensitivity(PathSensitivity.NONE)
    outputs.dir(outputDirectory)
    doLast {
        val output = outputDirectory.get().asFile
        output.deleteRecursively()
        output.mkdirs()
        val source = tokenFile.get().asFile
        if (source.isFile) {
            val token = source.readText().trim()
            if (token.length !in 32..512 || !Regex("^[A-Za-z0-9._~+/-]+=*$").matches(token)) {
                throw GradleException(invalidMessage)
            }
            output.resolve("manijero").mkdirs()
            output.resolve("manijero/pilot-token.txt").writeText(token)
        }
    }
}

compose.desktop {
    application {
        mainClass = "com.jamarglex.manijero.MainKt"

        nativeDistributions {
            targetFormats(TargetFormat.Dmg, TargetFormat.Msi, TargetFormat.Deb)
            packageName = if (qaBuild) "com.jamarglex.manijero.qa" else "com.jamarglex.manijero"
            packageVersion = "1.0.0"
        }
    }
}

// Test-build tools (`Conexión`): only the development `run` task (`./scripts/init.sh --desktop`)
// marks the JVM as a test build. Packaged apps, `runDistributable`, and `runRelease` never carry the
// property; `TestBuildGatingGuardTest` keeps it that way. The same task alone gets the generated
// pilot-token folder on its classpath; `PilotTokenGuardTest` keeps it off every other path. Compose
// sets the `run` classpath after this action, so the folder is appended when the task starts.
tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
    systemProperty("manijero.testBuild", "true")
    dependsOn(generatePilotTokenResource)
    val pilotTokenFolder = layout.buildDirectory.dir("generated/pilotToken")
    doFirst { (this as JavaExec).classpath(pilotTokenFolder) }
}
