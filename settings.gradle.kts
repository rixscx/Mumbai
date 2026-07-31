// :domain is deliberately a plain JVM module with zero Android imports — that rule started as
// architecture hygiene and turned out to be load-bearing: it is the only module that compiles and
// tests in the authoring container, which cannot reach Google's Maven. See ADR-009.
rootProject.name = "mumbai"

pluginManagement {
    repositories {
        // mavenCentral FIRST, deliberately. Kotlin and kotlinx artifacts resolve there, so a
        // container that cannot reach Google's Maven never has to contact it to build :domain.
        // Only AGP and AndroidX fall through to google(), and only when :android is in the build.
        mavenCentral()
        gradlePluginPortal()
        google()
    }
}

dependencyResolutionManagement {
    repositories {
        mavenCentral()
        google()
    }
}

include(":domain")

// The Android module joins the build only where an SDK actually exists. Without this guard a
// checkout in the authoring container fails at configuration time on a missing SDK, before it can
// run the :domain tests — which are the one thing that *can* be verified there. CI sets
// ANDROID_HOME, so CI always gets the full build and the APK.
val hasAndroidSdk = sequenceOf("ANDROID_HOME", "ANDROID_SDK_ROOT")
    .mapNotNull(System::getenv)
    .any { it.isNotBlank() } || file("local.properties").exists()

if (hasAndroidSdk) {
    include(":android")
} else {
    logger.lifecycle(
        "No Android SDK found (ANDROID_HOME / ANDROID_SDK_ROOT / local.properties) — " +
            "configuring :domain only. Expected off an Android machine; CI builds the APK.",
    )
}
