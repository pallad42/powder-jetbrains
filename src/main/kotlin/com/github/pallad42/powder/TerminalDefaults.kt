package com.github.pallad42.powder

import org.jetbrains.plugins.terminal.TerminalFontSettings
import org.jetbrains.plugins.terminal.TerminalFontSettingsService
import org.jetbrains.plugins.terminal.TerminalOptionsProvider

/**
 * Terminal settings. Loaded only when the terminal plugin is there (optional dependency); the font settings
 * service is internal terminal API, so callers expect a LinkageError when it changes.
 */
internal object TerminalDefaults {
    fun apply() {
        val fonts = TerminalFontSettingsService.getInstance()
        fonts.setSettings(TerminalFontSettings(PowderFonts.preferences(), fonts.getSettings().columnSpacing))
        TerminalOptionsProvider.instance.enforceMinContrastRatio = false
    }
}
