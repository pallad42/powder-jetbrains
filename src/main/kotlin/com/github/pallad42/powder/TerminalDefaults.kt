package com.github.pallad42.powder

import org.jetbrains.plugins.terminal.TerminalOptionsProvider

/**
 * Terminal settings. Loaded only when the terminal plugin is there (optional dependency). The contrast option is
 * experimental terminal API, so callers expect a LinkageError when it changes. The terminal font is not set: the
 * terminal has no public API for it, the user sets it in Settings | Tools | Terminal.
 */
internal object TerminalDefaults {
    fun apply() {
        TerminalOptionsProvider.instance.enforceMinContrastRatio = false
    }
}
