package com.github.pallad42.powder

import com.intellij.ide.util.PropertiesComponent
import com.intellij.ide.ui.LafManager
import com.intellij.notification.NotificationGroupManager
import com.intellij.notification.NotificationType
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.logger
import com.intellij.openapi.editor.colors.EditorColorsManager
import com.intellij.openapi.editor.colors.impl.AppEditorFontOptions

/**
 * The first time the theme is switched on, sets its font in the editor (Settings | Editor | Font: a colour scheme
 * only stores whole font sizes) and the terminal, and stops the terminal adjusting the ANSI colours for contrast.
 * Done once only, so whatever the user changes afterwards stays.
 */
object FontDefaults {
    const val THEME_ID = "powder"

    private const val APPLIED_KEY = "powder.fontDefaultsApplied"
    private val log = logger<FontDefaults>()

    fun applyOnceIfThemeActive() {
        val theme = LafManager.getInstance().currentUIThemeLookAndFeel?.id
        val properties = PropertiesComponent.getInstance()
        log.debug("Theme $theme, font defaults applied before: ${properties.getBoolean(APPLIED_KEY)}")
        if (theme != THEME_ID || properties.getBoolean(APPLIED_KEY)) return
        properties.setValue(APPLIED_KEY, true)

        // AppEditorFontOptions is internal API too: if it changes, the theme still works, only the font is not set.
        try {
            AppEditorFontOptions.getInstance().update(PowderFonts.preferences())
            // update() only stores the font; re-setting the scheme makes open editors pick it up.
            val colors = EditorColorsManager.getInstance()
            colors.setGlobalScheme(colors.globalScheme)
        } catch (e: LinkageError) {
            log.info("Editor font not applied (its API changed): $e")
        }

        val terminal = try {
            TerminalDefaults.apply()
            true
        } catch (e: LinkageError) {
            log.info("Terminal settings not applied (no terminal plugin or its API changed): $e")
            false
        } catch (e: Exception) {
            log.warn("Terminal settings not applied", e)
            false
        }

        // Persist the "applied" flag right away: settings are otherwise saved later, and after a crash the font
        // would be forced again on the next start, over whatever the user picked meanwhile.
        ApplicationManager.getApplication().saveSettings()

        val content = buildString {
            append("${PowderFonts.FAMILY} ${PowderFonts.SIZE}, line height ${PowderFonts.LINE_SPACING} in the editor")
            append(if (terminal) " and the terminal; terminal colours are no longer adjusted for contrast." else ".")
            append("<br>Change them any time in Settings | Editor | Font")
            if (terminal) append(" and Settings | Tools | Terminal")
            append(".")
        }
        NotificationGroupManager.getInstance().getNotificationGroup("Powder")
            .createNotification("Powder: font applied", content, NotificationType.INFORMATION)
            .notify(null)
    }
}
