plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.mumbai"

    // ADR-007 sets minSdk 29 (the stated device floor, and the version that deletes every
    // pre-scoped-storage branch from the photo/receipt/export paths).
    //
    // ADR-007 also asks for targetSdk 36. AGP 8.7 cannot compile against API 36, so this targets
    // 35 for now and moves to 36 with the AGP bump. Stated here rather than silently diverging
    // from the decision record.
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mumbai"
        minSdk = 29
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0-tb1"
        resourceConfigurations += listOf("en")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    // A debug APK is what actually reaches the phone before the trip: ADR-008 wants release-signed,
    // but that needs a keystore that must survive, and one does not exist yet. CI publishes debug
    // unconditionally and release only when a keystore secret is present. Debug is marked so the
    // two are never confused on a device.
    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Left unsigned deliberately. A release build signed with the debug key would be a
            // release build in name only, and this app holds money and location data.
            signingConfig = null
        }
    }

    // No tracking, no ads, no analytics — and nothing that would need a network permission.
    // The absence of INTERNET in the manifest is the enforcement, not a policy document.
    packaging {
        resources.excludes += setOf("/META-INF/{AL2.0,LGPL2.1}")
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
    compilerOptions {
        // Not allWarningsAsErrors here, unlike :domain. Compose and AGP emit warnings from
        // generated code that a UI module cannot fix, and a gate that has to be suppressed to pass
        // stops being a gate. :domain keeps the strict setting because that is where money maths
        // lives and a silent warning becomes a rounding bug.
        freeCompilerArgs.add("-Xjvm-default=all")
    }
}

dependencies {
    implementation(project(":domain"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.datetime)

    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.compose.ui.tooling.preview)
    debugImplementation(libs.compose.ui.tooling)
}
