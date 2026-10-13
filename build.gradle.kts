import org.jetbrains.intellij.platform.gradle.tasks.VerifyPluginTask

plugins {
    id("org.jetbrains.kotlin.jvm") version "2.4.21"
    id("org.jetbrains.intellij.platform") version "2.19.0"
}

group = "com.github.pallad42"
version = "0.1.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

/** Your installed IntelliJ IDEA when there is one (faster, no download); otherwise (CI) the version from gradle.properties. */
val localIde: File? = providers.gradleProperty("ideaPath").orNull?.let(::file)?.takeIf { it.exists() }

dependencies {
    intellijPlatform {
        if (localIde != null) local(localIde) else intellijIdea(providers.gradleProperty("platformVersion").get())
        bundledPlugin("org.jetbrains.plugins.terminal")
    }
}

kotlin {
    jvmToolchain(21)
}

intellijPlatform {
    // Keep the sandbox IDE under build/ so opening this project in the sandbox does not index it.
    sandboxContainer = layout.buildDirectory.dir("idea-sandbox")
    pluginConfiguration {
        ideaVersion {
            sinceBuild = "262"
            untilBuild = provider { null }
        }
    }
    buildSearchableOptions = false
    instrumentCode = false

    pluginVerification {
        ides {
            current()
        }
        // TerminalDefaults sets the terminal font through the terminal plugin's internal font settings service
        // (there is no public API for it); it is guarded and reported, so internal API usage alone does not fail.
        failureLevel = listOf(
            VerifyPluginTask.FailureLevel.COMPATIBILITY_PROBLEMS,
            VerifyPluginTask.FailureLevel.INVALID_PLUGIN,
            VerifyPluginTask.FailureLevel.SCHEDULED_FOR_REMOVAL_API_USAGES,
            VerifyPluginTask.FailureLevel.NON_EXTENDABLE_API_USAGES,
            VerifyPluginTask.FailureLevel.OVERRIDE_ONLY_API_USAGES,
        )
    }

    // Marketplace release: ./gradlew signPlugin publishPlugin with these environment variables set.
    signing {
        certificateChain = providers.environmentVariable("CERTIFICATE_CHAIN")
        privateKey = providers.environmentVariable("PRIVATE_KEY")
        password = providers.environmentVariable("PRIVATE_KEY_PASSWORD")
    }
    publishing {
        token = providers.environmentVariable("PUBLISH_TOKEN")
    }
}

/** Installs the freshly built plugin straight into your everyday IntelliJ (takes effect after an IDE restart). */
val installPlugin by tasks.registering(Sync::class) {
    group = "intellij platform"
    description = "Builds the plugin and installs it into the IntelliJ configured by ideaConfigDir"

    val configDir = file(
        providers.gradleProperty("ideaConfigDir")
            .orElse(System.getProperty("user.home") + "/Library/Application Support/JetBrains/IntelliJIdea2026.2")
            .get(),
    )
    val disabledPlugins = configDir.resolve("disabled_plugins.txt")
    val pluginId = "com.github.pallad42.powder"

    val pluginZip = tasks.named<Zip>("buildPlugin").flatMap { it.archiveFile }
    dependsOn("buildPlugin")
    from(zipTree(pluginZip)) {
        // The zip contains a top-level "powder/" folder; strip it.
        eachFile { relativePath = RelativePath(true, *relativePath.segments.drop(1).toTypedArray()) }
        includeEmptyDirs = false
    }
    into(configDir.resolve("plugins/powder"))

    doLast {
        if (disabledPlugins.exists()) {
            disabledPlugins.writeText(disabledPlugins.readLines().filter { it.trim() != pluginId }.joinToString("\n", postfix = "\n"))
        }
        println("Installed into ${configDir.resolve("plugins/powder")} - restart IntelliJ to load it.")
    }
}

tasks.withType<JavaExec>().matching { it.name.startsWith("runIde") }.configureEach {
    // The plugin's debug logging (font registration, font defaults) in the sandbox IDE's idea.log.
    jvmArgs("-Didea.log.debug.categories=#com.github.pallad42.powder")
}

// ./gradlew runIdeWithFrost: a sandbox IDE with Frost (../frost, build it there first) installed next to the theme,
// to see the theme translucent and blurred.
intellijPlatformTesting {
    runIde {
        register("runIdeWithFrost") {
            plugins {
                localPlugin(file("../frost/build/distributions/frost-0.1.1.zip"))
            }
        }
    }
}
