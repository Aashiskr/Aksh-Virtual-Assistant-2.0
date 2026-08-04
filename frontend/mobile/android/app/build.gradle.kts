plugins {
    id("com.android.application")
}

android {
    namespace = "com.aksh.remote"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.aksh.remote"
        minSdk = 26
        targetSdk = 36
        versionCode = 12
        versionName = "2.0.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
