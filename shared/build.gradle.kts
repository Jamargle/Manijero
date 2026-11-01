import org.gradle.api.tasks.testing.Test
import org.gradle.process.CommandLineArgumentProvider
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
            // Local mock answer service (./scripts/init.sh --mock). Test-only: no product source
            // set, app host, or shipped artifact gains a server dependency.
            implementation(libs.ktor.server.core)
            implementation(libs.ktor.server.cio)
            implementation(libs.ktor.server.test.host)
            // Local smoke test (./scripts/init.sh --local-smoke): the Desktop driver uses the same CIO
            // answer client as the Desktop app. Test-only.
            implementation(libs.ktor.client.cio)
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
        // The live local smoke check reaches the real local answer service; only
        // :shared:runDesktopLocalSmoke runs it.
        excludeTestsMatching("com.jamarglex.manijero.smoke.DesktopLocalSmokeRun")
    }
    // AndroidBackupExclusionGuardTest reads the checked-in Android manifest and backup rule files
    // (it needs no Android SDK), so declare them as inputs: editing them must rerun the guard
    // locally, not only on a clean CI build.
    inputs.files(
        file("../androidApp/src/main/AndroidManifest.xml"),
        file("../androidApp/src/main/res/xml"),
    ).withPropertyName("androidBackupConfiguration")
        .withPathSensitivity(org.gradle.api.tasks.PathSensitivity.RELATIVE)
    // PilotTokenGuardTest reads the host build scripts, the host entry points, and .gitignore.
    inputs.files(
        file("../.gitignore"),
        file("../androidApp/build.gradle.kts"),
        file("../desktopApp/build.gradle.kts"),
        file("../androidApp/src/main/kotlin/com/jamarglex/manijero/MainActivity.kt"),
        file("../desktopApp/src/main/kotlin/com/jamarglex/manijero/main.kt"),
    ).withPropertyName("pilotTokenGuardFiles")
        .withPathSensitivity(org.gradle.api.tasks.PathSensitivity.RELATIVE)
    // The mock answer service tests read the committed contract examples.
    inputs.dir(file("../contracts/examples"))
        .withPropertyName("contractExamples")
        .withPathSensitivity(org.gradle.api.tasks.PathSensitivity.RELATIVE)
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

// ---------------------------------------------------------------------------------------------
// Local mock answer service (test-only)
// ---------------------------------------------------------------------------------------------
// ./scripts/init.sh --mock runs this task, then launches com.jamarglex.manijero.mock.MockAnswerServerKt
// from the compiled jvmTest classes. The task writes the runtime classpath and the Java executable
// Gradle uses for jvmTest, so the launch never depends on whichever `java` is first on PATH.
// Values are resolved into file collections and providers here, so the action touches no `project`
// and stays configuration-cache safe.
val mockAnswerServerDir = layout.buildDirectory.dir("mock-answer-server")
val mockAnswerServerCompilation = kotlin.jvm().compilations.getByName("test")
val mockAnswerServerClasspath = files(
    mockAnswerServerCompilation.output.allOutputs,
    mockAnswerServerCompilation.runtimeDependencyFiles,
)
val mockAnswerServerJava = jvmTestTask
    .flatMap { it.javaLauncher }
    .map { it.executablePath.asFile.absolutePath }
    .orElse(providers.systemProperty("java.home").map { File(it, "bin/java").absolutePath })

tasks.register("prepareMockAnswerServer") {
    group = "application"
    description = "Compile the test-only mock answer service and record how ./scripts/init.sh --mock launches it."
    inputs.files(mockAnswerServerClasspath).withPropertyName("runtimeClasspath")
    inputs.property("javaExecutable", mockAnswerServerJava)
    val classpathFile = mockAnswerServerDir.map { it.file("classpath.txt") }
    val javaFile = mockAnswerServerDir.map { it.file("java.txt") }
    outputs.file(classpathFile).withPropertyName("classpathFile")
    outputs.file(javaFile).withPropertyName("javaFile")
    val classpath = mockAnswerServerClasspath
    val java = mockAnswerServerJava
    doLast {
        classpathFile.get().asFile.apply {
            parentFile.mkdirs()
            writeText(classpath.files.joinToString(File.pathSeparator) { it.absolutePath } + "\n")
        }
        javaFile.get().asFile.writeText(java.get() + "\n")
    }
}

// ---------------------------------------------------------------------------------------------
// Local smoke test (test-only, never part of a tier)
// ---------------------------------------------------------------------------------------------
// ./scripts/init.sh --local-smoke runs this task through backend/app/local_smoke.py. It renders the
// shared App offscreen against the running local answer service and writes one result line to the
// file named by -PmanijeroSmokeResult. -PmanijeroSmokeExpected is the Desktop service address. The
// task reuses the jvmTest classes, runs headless, and is never up to date.
val smokeExpected = providers.gradleProperty("manijeroSmokeExpected")
val smokeResult = providers.gradleProperty("manijeroSmokeResult")

tasks.register<Test>("runDesktopLocalSmoke") {
    group = "verification"
    description = "Ask the running local answer service once through the shared Desktop UI (./scripts/init.sh --local-smoke)."
    testClassesDirs = jvmTestTask.get().testClassesDirs
    classpath = jvmTestTask.get().classpath
    useJUnit()
    filter {
        includeTestsMatching("com.jamarglex.manijero.smoke.DesktopLocalSmokeRun")
        isFailOnNoMatchingTests = true
    }
    systemProperty("java.awt.headless", "true")
    val expected = smokeExpected
    val result = smokeResult
    jvmArgumentProviders.add(
        CommandLineArgumentProvider {
            listOfNotNull(
                expected.orNull?.let { "-Dmanijero.smoke.expected=$it" },
                result.orNull?.let { "-Dmanijero.smoke.result=$it" },
            )
        },
    )
    outputs.upToDateWhen { false }
}
