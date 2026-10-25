import org.gradle.api.tasks.testing.Test
import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.io.File

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
            implementation(libs.compose.uiBackhandler)
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
        // Android screenshot regression: Robolectric renders the Android target on the host JVM,
        // so no emulator or device is needed. Test-only; the main Android dependency graph is
        // unchanged.
        getByName("androidHostTest").dependencies {
            implementation(libs.androidx.activity.compose)
            implementation(libs.androidx.test.core)
            implementation(libs.androidx.test.junit)
            implementation(libs.androidx.compose.uiTestJunit4)
            implementation(libs.androidx.compose.uiTestManifest)
            implementation(libs.robolectric)
            implementation(libs.roborazzi.core)
            implementation(libs.roborazzi.compose)
        }
    }
}

dependencies {
    androidRuntimeClasspath(libs.compose.uiTooling)
}

// ---------------------------------------------------------------------------------------------
// Screenshot regression (shared UI)
// ---------------------------------------------------------------------------------------------
// Two platform suites render the same committed fixtures:
//   * :shared:verifyDesktopScreenshots / :shared:recordDesktopScreenshots run the Compose
//     Desktop JVM suite (existing target, no Android SDK).
//   * :shared:verifyAndroidScreenshots / :shared:recordAndroidScreenshots run the same states
//     through Robolectric on the host JVM, so "Android" means Android rendering without an
//     emulator or device.
// :shared:verifyScreenshots and :shared:recordScreenshots are the aggregate entry points.
//
// The suites are deliberately NOT part of :shared:jvmTest or :shared:testAndroidHostTest:
//  - Fonts and rendering differ between Desktop and Android, so each platform owns its goldens
//    and records them on the host that reviews them.
//  - The desktop goldens are host-font-pinned (recorded on macOS), and the existing CI gate runs
//    on Linux; keeping the screenshots out of the ordinary tiers avoids comparing against a
//    baseline the CI image cannot reproduce.
//  - Verification must stay read-only. The verify tasks only read goldens; the record tasks are
//    the explicit action that rewrites them.
val desktopScreenshotGoldenDir = layout.projectDirectory.dir("src/jvmTest/screenshots")
val androidScreenshotGoldenDir = layout.projectDirectory.dir("src/androidHostTest/screenshots")
val desktopScreenshotReportDir = layout.buildDirectory.dir("reports/screenshot-regression")
val androidScreenshotReportDir = layout.buildDirectory.dir("reports/screenshot-regression-android")

fun Test.configureScreenshotRun(record: Boolean, goldenDir: File, reportDir: File) {
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
    systemProperty("roborazzi.output.dir", goldenDir.absolutePath)
    systemProperty("roborazzi.compare.output.dir", reportDir.absolutePath)
    systemProperty("roborazzi.result.dir", File(reportDir, "results").absolutePath)
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

tasks.withType<Test>().matching { it.name == "testAndroidHostTest" }.configureEach {
    filter {
        // Host tests stay fast and deterministic; the screenshot suite has its own explicit tasks.
        excludeTestsMatching("com.jamarglex.manijero.screenshots.*")
    }
}

tasks.register<Test>("verifyDesktopScreenshots") {
    description = "Verify shared Compose Desktop screenshots against committed goldens (read-only)."
    testClassesDirs = jvmTestTask.get().testClassesDirs
    classpath = jvmTestTask.get().classpath
    configureScreenshotRun(
        record = false,
        goldenDir = desktopScreenshotGoldenDir.asFile,
        reportDir = desktopScreenshotReportDir.get().asFile,
    )
}

tasks.register<Test>("recordDesktopScreenshots") {
    description = "Re-record shared Compose Desktop screenshots after human review of each image."
    testClassesDirs = jvmTestTask.get().testClassesDirs
    classpath = jvmTestTask.get().classpath
    configureScreenshotRun(
        record = true,
        goldenDir = desktopScreenshotGoldenDir.asFile,
        reportDir = desktopScreenshotReportDir.get().asFile,
    )
}

tasks.register<Test>("verifyAndroidScreenshots") {
    description = "Verify shared Android screenshots (Robolectric host) against committed goldens (read-only)."
    val androidHostTest = tasks.named<Test>("testAndroidHostTest").get()
    testClassesDirs = androidHostTest.testClassesDirs
    classpath = androidHostTest.classpath
    jvmArgs(*androidHostTest.jvmArgs.toTypedArray())
    maxParallelForks = androidHostTest.maxParallelForks
    configureScreenshotRun(
        record = false,
        goldenDir = androidScreenshotGoldenDir.asFile,
        reportDir = androidScreenshotReportDir.get().asFile,
    )
}

tasks.register<Test>("recordAndroidScreenshots") {
    description = "Re-record shared Android screenshots (Robolectric host) after human review of each image."
    val androidHostTest = tasks.named<Test>("testAndroidHostTest").get()
    testClassesDirs = androidHostTest.testClassesDirs
    classpath = androidHostTest.classpath
    jvmArgs(*androidHostTest.jvmArgs.toTypedArray())
    maxParallelForks = androidHostTest.maxParallelForks
    configureScreenshotRun(
        record = true,
        goldenDir = androidScreenshotGoldenDir.asFile,
        reportDir = androidScreenshotReportDir.get().asFile,
    )
}

tasks.register("verifyScreenshots") {
    group = "verification"
    description = "Verify the Desktop and Android shared-UI screenshots (read-only, no emulator)."
    dependsOn("verifyDesktopScreenshots", "verifyAndroidScreenshots")
}

tasks.register("recordScreenshots") {
    group = "verification"
    description = "Re-record the Desktop and Android shared-UI screenshots after human review."
    dependsOn("recordDesktopScreenshots", "recordAndroidScreenshots")
}
