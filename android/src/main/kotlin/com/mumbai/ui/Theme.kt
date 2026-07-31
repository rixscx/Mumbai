package com.mumbai.ui

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

/**
 * The kaali-peeli palette from docs/PHASE-0-ALIGNMENT.md §7 — sampled from the Premier Padmini as a
 * material object, not from "Mumbai vibes".
 *
 * The two *-Text values exist because the raw palette does not survive both grounds. §7 computed
 * ochre at 2.0:1 on plate and introduced OchreText for it; the same computation gives taillight
 * 2.18:1 and jade 3.14:1 on ink, so each gets a lightened counterpart for small text while the raw
 * value stays for fills. Getting this wrong is not a style nit — it is unreadable text on a bright
 * Mumbai street, which is exactly where this app gets used.
 */
object Kaali {
    val Ink = Color(0xFF17150F)        // body black, warm not neutral
    val Plate = Color(0xFFF2F3F1)      // enamel number-plate white, cooled so it is not cream
    val Ochre = Color(0xFFD9A21B)      // roof; money numerals and the one primary action
    val OchreText = Color(0xFF7A5806)  // ochre as *text* on plate — 5.3:1
    val Jade = Color(0xFF1F7A5C)       // under budget, visited, confirmed
    val JadeText = Color(0xFF4FBF95)   // jade as text on ink — 7.2:1
    val Taillight = Color(0xFFA32017)  // over budget, destructive
    val TaillightText = Color(0xFFE8776A) // taillight as text on ink — 5.7:1
    val Fuchsia = Color(0xFFC2367E)    // the check-off moment only; never a surface

    val InkRaised = Color(0xFF211F17)
    val PlateRaised = Color(0xFFFAFAF9)
    val DimOnInk = Color(0xFFA9A395)
    val DimOnPlate = Color(0xFF5C5749)
}

private val Dark = darkColorScheme(
    primary = Kaali.Ochre,
    onPrimary = Kaali.Ink,
    secondary = Kaali.JadeText,
    background = Kaali.Ink,
    onBackground = Kaali.Plate,
    surface = Kaali.InkRaised,
    onSurface = Kaali.Plate,
    onSurfaceVariant = Kaali.DimOnInk,
    error = Kaali.TaillightText,
    outline = Color(0xFF302D23),
)

private val Light = lightColorScheme(
    primary = Kaali.Ochre,
    onPrimary = Kaali.Ink,
    secondary = Kaali.Jade,
    background = Kaali.Plate,
    onBackground = Kaali.Ink,
    surface = Kaali.PlateRaised,
    onSurface = Kaali.Ink,
    onSurfaceVariant = Kaali.DimOnPlate,
    error = Kaali.Taillight,
    outline = Color(0xFFD8D9D3),
)

/**
 * Type. §7 pairs Archivo (titles and *all* money numerals, for its lining tabular figures) with
 * IBM Plex Sans for body. Neither is bundled yet — the font files are a licensing and APK-size task
 * of their own — so this uses the platform default at the §7 sizes and weights. When the .ttf files
 * land, only the FontFamily lines below change.
 */
private val AppTypography = Typography().let { base ->
    base.copy(
        displaySmall = base.displaySmall.copy(fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp),
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.Bold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelSmall = base.labelSmall.copy(fontWeight = FontWeight.Bold, letterSpacing = 1.4.sp),
    )
}

/** Money style: large, bold, tabular. The rupees are the number; the symbol is punctuation. */
val MoneyStyle = TextStyle(
    fontSize = 34.sp,
    fontWeight = FontWeight.Bold,
    letterSpacing = (-1).sp,
    textAlign = TextAlign.Start,
)

@Composable
fun MumbaiTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val scheme = if (dark) Dark else Light
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window ?: return@SideEffect
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars =
                scheme.background.luminance() > 0.5f
        }
    }
    // LocalContext is read so previews resolve resources the same way the activity does.
    @Suppress("UNUSED_EXPRESSION") LocalContext.current
    MaterialTheme(colorScheme = scheme, typography = AppTypography, content = content)
}

val CardCorner = 14.dp
