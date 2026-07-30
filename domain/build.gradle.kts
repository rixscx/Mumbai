plugins {
    alias(libs.plugins.kotlin.jvm)
}

// No Android dependencies here. Ever. This is enforced by a check in CI (see
// .github/workflows/ci.yml) rather than left to reviewer memory.
dependencies {
    implementation(libs.kotlinx.datetime)
    testImplementation(libs.kotlin.test)
}

kotlin {
    jvmToolchain(21)
    compilerOptions {
        allWarningsAsErrors.set(true)
    }
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "failed", "skipped")
    }
}
