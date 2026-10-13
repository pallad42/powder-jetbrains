package com.github.pallad42.powder

import com.intellij.ide.AppLifecycleListener
import com.intellij.ide.ui.LafManager
import com.intellij.ide.ui.LafManagerListener
import com.intellij.openapi.application.ApplicationManager

class PowderAppListener : AppLifecycleListener {
    override fun appFrameCreated(commandLineArgs: MutableList<String>) {
        // Before any project opens its editors.
        PowderFonts.register()
        ApplicationManager.getApplication().invokeLater { FontDefaults.applyOnceIfThemeActive() }
    }
}

class PowderThemeListener : LafManagerListener {
    override fun lookAndFeelChanged(source: LafManager) {
        // Also covers installing the plugin without a restart, when appFrameCreated has long passed.
        PowderFonts.register()
        ApplicationManager.getApplication().invokeLater { FontDefaults.applyOnceIfThemeActive() }
    }
}
