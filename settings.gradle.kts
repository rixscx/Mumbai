// Android modules join this list once the Android SDK is available to the build.
// :domain is deliberately a plain JVM module with zero Android imports — that rule started as
// architecture hygiene and turned out to be load-bearing: it is the only module that compiles and
// tests in the authoring container, which cannot reach Google's Maven. See ADR-009.
rootProject.name = "mumbai"

pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositories {
        mavenCentral()
    }
}

include(":domain")
