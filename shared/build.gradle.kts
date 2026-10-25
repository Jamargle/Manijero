import org.gradle.api.tasks.testing.Test
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidMultiplatformLibrary)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
    alias(libs.plugins.kotlinSerialization)
}

kotlin {
    listOf(
        iosArm64(),
        iosSimulatorArm64(),
    ).forEach { iosTarget ->
        iosTarget.binaries.framework {
            baseName = "Shared"
            isStatic = true
        }
    }
    
    jvm()
    
    android {
       namespace = "com.jamarglex.manijero.shared"
       compileSdk = libs.versions.android.compileSdk.get().toInt()
       minSdk = libs.versions.android.minSdk.get().toInt()
    
       compilerOptions {
           jvmTarget = JvmTarget.JVM_11
       }
       androidResources {
           enable = true
       }
       withHostTest {
           isIncludeAndroidResources = true
       }
       withDeviceTestBuilder {
           sourceSetTreeName = "test"
       }.configure {
           instrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
       }
    }
    
    sourceSets {
        androidMain.dependencies {
            implementation(libs.compose.uiToolingPreview)
            implementation(libs.compose.uiTooling)
        }
        commonMain.dependencies {
            implementation(libs.compose.runtime)
            implementation(libs.compose.foundation)
            implementation(libs.compose.material3)
            implementation(libs.compose.ui)
            implementation(libs.compose.components.resources)
            implementation(libs.compose.uiToolingPreview)
            implementation(libs.androidx.lifecycle.viewmodelCompose)
            implementation(libs.androidx.lifecycle.runtimeCompose)
            implementation(libs.kotlinx.coroutines.core)
            implementation(libs.ktor.client.core)
            implementation(libs.ktor.client.content.negotiation)
            implementation(libs.ktor.serialization.kotlinx.json)
            implementation(libs.kotlinx.serialization.json)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.kotlinx.coroutines.test)
            implementation(libs.ktor.client.mock)
        }
        // Screenshot regression: Compose Desktop rendering plus the pinned Roborazzi capture
        // path. Test-only, so no Android/iOS source set gains a dependency.
        jvmTest.dependencies {
            implementation(compose.desktop.currentOs)
            implementation(libs.compose.uiTestJunit4Desktop)
            implementation(libs.roborazzi.composeDesktop)
        }
    }
}

dependencies {
    androidRuntimeClasspath(libs.compose.uiTooling)
}

// ---------------------------------------------------------------------------------------------
// Screenshot regression (Compose Desktop, shared UI)
// ---------------------------------------------------------------------------------------------
// The suite renders the shared commonMain screens on the JVM/Desktop target and compares them
// with committed goldens. It is deliberately NOT part of :shared:jvmTest:
//
//  - Fonts are resolved from the host by Compose Desktop, so a golden recorded on one operating
//    system is not a valid expectation on another. The goldens in src/jvmTest/screenshots were
//    recorded on macOS; the existing CI gate runs on Linux, so wiring this into jvmTest/--fast
//    would make CI render against a baseline it cannot reproduce. It stays an explicit,
//    host-pinned task until a baseline is recorded on the CI image.
//  - Verification must stay read-only. The verify task only reads goldens; the record task is
//    the one explicitly documented action that rewrites them.
val screenshotGoldenDir = layout.projectDirectory.dir("src/jvmTest/screenshots")
val screenshotReportDir = layout.buildDirectory.dir("reports/screenshot-regression")

fun Test.configureScreenshotRun(record: Boolean) {
    group = "verification"
    useJUnit()
    filter {
        includeTestsMatching("com.jamarglex.manijero.screenshots.*")
        isFailOnNoMatchingTests = true
    }
    // Roborazzi reads its mode from system properties. Exactly one mode is ever enabled, so a
    // verify run can never record and a record run never pretends to verify.
    systemProperty("roborazzi.test.record", record.toString())
    systemProperty("roborazzi.test.verify", (!record).toString())
    systemProperty("roborazzi.output.dir", screenshotGoldenDir.asFile.absolutePath)
    systemProperty("roborazzi.compare.output.dir", screenshotReportDir.get().asFile.absolutePath)
    systemProperty("roborazzi.result.dir", screenshotReportDir.get().dir("results").asFile.absolutePath)
    systemProperty("roborazzi.record.filePathStrategy", "relativePathFromRoborazziContextOutputDirectory")
    systemProperty("roborazzi.record.image.extension", "png")
    systemProperty("java.awt.headless", "true")
    // The comparison is the gate: rerun it even when no declared input changed, so a modified
    // golden is always noticed.
    outputs.upToDateWhen { false }
    testLogging {
        events("passed", "failed", "skipped")
    }
}

val jvmTestTask = tasks.named<Test>("jvmTest") {
    filter {
        // See the comment above: the host-pinned screenshot suite has its own explicit tasks.
        excludeTestsMatching("com.jamarglex.manijero.screenshots.*")
    }
}

tasks.register<Test>("verifyScreenshots") {
    description = "Verify shared Compose Desktop screenshots against committed goldens (read-only)."
    testClassesDirs = jvmTestTask.get().testClassesDirs
    classpath = jvmTestTask.get().classpath
    configureScreenshotRun(record = false)
}

tasks.register<Test>("recordScreenshots") {
    description = "Re-record shared Compose Desktop screenshots after human review of each image."
    testClassesDirs = jvmTestTask.get().testClassesDirs
    classpath = jvmTestTask.get().classpath
    configureScreenshotRun(record = true)
}
