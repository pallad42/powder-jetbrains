package com.github.pallad42.powder

import com.intellij.openapi.diagnostic.logger
import com.intellij.openapi.editor.colors.impl.FontPreferencesImpl
import java.awt.Font
import java.awt.GraphicsEnvironment

/**
 * Bitstream Vera Sans Mono, the theme's font. It is not part of macOS, so the plugin carries it and registers it
 * with the JVM; a copy installed on the system takes precedence.
 */
object PowderFonts {
    const val FAMILY = "Bitstream Vera Sans Mono"
    const val SIZE = 13.5f
    const val LINE_SPACING = 1.1f

    fun preferences(): FontPreferencesImpl = FontPreferencesImpl().apply {
        register(FAMILY, SIZE)
        lineSpacing = LINE_SPACING
    }

    private val FILES = listOf("VeraMono.ttf", "VeraMoBd.ttf", "VeraMoIt.ttf", "VeraMoBI.ttf")
    private val log = logger<PowderFonts>()

    @Volatile
    private var registered = false

    fun register() {
        if (registered) return
        registered = true
        val env = GraphicsEnvironment.getLocalGraphicsEnvironment()
        for (file in FILES) {
            try {
                val stream = PowderFonts::class.java.getResourceAsStream("/fonts/$file") ?: continue
                // false: a font with this name is already available (installed on the system).
                val added = stream.use { env.registerFont(Font.createFont(Font.TRUETYPE_FONT, it)) }
                log.debug("$file registered: $added")
            } catch (e: Exception) {
                log.warn("Cannot register bundled font $file", e)
            }
        }
    }
}
