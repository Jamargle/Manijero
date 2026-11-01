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
// property; `TestBuildGatingGuardTest` keeps it that way.
tasks.withType<JavaExec>().matching { it.name == "run" }.configureEach {
    systemProperty("manijero.testBuild", "true")
}
