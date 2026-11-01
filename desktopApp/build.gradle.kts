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

// Pilot bearer token (client_pilot_credentials): only from the git-ignored `pilot-token.local` at the
// repository root, or the file named by MANIJERO_PILOT_TOKEN_FILE (tests and checks use fake files).
// The task declares the file, never its value, as an input, and writes the classpath resource that
// `desktopPilotToken()` reads. Only the development `run` task has that folder on its classpath
// (owner decision 5), so `jar`, packaged, and release outputs never contain the token. No token
// file: no resource.
val pilotTokenFile: Provider<RegularFile> = rootProject.layout.projectDirectory.file(
    providers.environmentVariable("MANIJERO_PILOT_TOKEN_FILE").orElse("pilot-token.local"),
)
val generatePilotTokenResource = tasks.register("generatePilotTokenResource") {
    val tokenFile = pilotTokenFile
    val outputDirectory = layout.buildDirectory.dir("generated/pilotToken")
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
                throw GradleException(
                    "pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again.",
                )
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
            packageName = "com.jamarglex.manijero"
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
