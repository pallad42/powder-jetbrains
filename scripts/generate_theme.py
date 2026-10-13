#!/usr/bin/env python3
"""Generates the Powder UI theme and editor colour scheme.

A calm, Xcode-style dark theme: neutral graphite backgrounds, powder pink keywords, salmon strings, sand numbers,
teal function declarations, lavender types - the colours of Xcode's Default (Dark), toned down. Calls get a lighter
teal, operators are dimmed, fields and variables stay plain text.

The theme inherits from the bundled Islands Dark theme and repaints it: every named colour of Islands Dark
(and of its parent, the new UI dark theme) is replaced with one of these, and so is every hard-coded colour the
parents use. The editor scheme starts from Darcula + Islands Dark (plus the Darcula additions of bundled plugins);
their syntax colours are translated by meaning (SYNTAX_COLORS: keywords pink, strings salmon, functions teal...),
and the theme's own syntax highlighting (SYNTAX) goes on top.

The base files are read from an installed IntelliJ IDEA, so after an IDE update simply run it again:

    python3 scripts/generate_theme.py ["/Applications/IntelliJ IDEA.app"]
"""

import colorsys
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

IDE = Path(sys.argv[1] if len(sys.argv) > 1 else "/Applications/IntelliJ IDEA.app")
ROOT = Path(__file__).resolve().parent.parent
OUT_THEME = ROOT / "src/main/resources/themes/Powder.theme.json"
OUT_SCHEME = ROOT / "src/main/resources/themes/Powder.xml"

THEME_NAME = "Powder"

# ---------------------------------------------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------------------------------------------
# Neutral graphite, as in Xcode's Default (Dark).
FRAME = "#18181c"  # window frame around the islands
BG_DIM = "#1f1f24"  # editor, tool windows, terminal
BG0 = "#28282e"  # popups
BG1 = "#2d2d33"
BG2 = "#35353c"
BG3 = "#3d3d45"
BG4 = "#45454e"
BG5 = "#505158"
BG_VISUAL = "#414a5c"  # editor selection: Xcode's slate blue, toned down
LIST_SELECTION = "#3d4454"  # selected row in trees and lists
CURRENT_LINE = "#242429"  # gray-20, halfway between BG_DIM and BG0

FG = "#d9d9de"
GREY0 = "#5c636b"
GREY1 = "#6f7a85"  # comments
GREY2 = "#8a939c"
WHITE = "#f5f5f7"

# Syntax: Xcode's Default (Dark) colours, toned down.
PINK = "#d895b4"  # keywords
SALMON = "#e3a08c"  # strings
SAND = "#d2c283"  # numbers, constants
TEAL = "#8fb3c9"  # function declarations: powder blue
CALL = "#b5c8d5"  # function and method calls: a lighter powder blue
PUNCTUATION = "#a5acb4"  # operators, braces, commas, dots: dimmed so the names stand out
LAVENDER = "#c3b4e8"  # classes and types
BRONZE = "#c29a74"  # annotations

# Status and UI colours (errors, warnings, VCS, accents).
RED = "#e5848c"
ORANGE = SALMON
YELLOW = SAND
GREEN = "#8fc79a"
AQUA = TEAL
BLUE = "#6aa6e8"  # UI accent: buttons, focus, links
PURPLE = LAVENDER

ANSI = [  # terminal colours 0-15 from the same palette, in IntelliJ's ANSI key order
    ("BLACK", GREY1), ("RED", RED), ("GREEN", GREEN), ("YELLOW", SAND),
    ("BLUE", BLUE), ("MAGENTA", PINK), ("CYAN", TEAL), ("GRAY", FG),
    ("DARKGRAY", GREY2), ("RED_BRIGHT", "#f0a0a6"), ("GREEN_BRIGHT", "#ace0b5"), ("YELLOW_BRIGHT", "#e6d79e"),
    ("BLUE_BRIGHT", "#94c0f2"), ("MAGENTA_BRIGHT", "#e8b3cc"), ("CYAN_BRIGHT", "#9acfdf"), ("WHITE", WHITE),
]
BLOCK_TERMINAL = ["BLACK", "RED", "GREEN", "YELLOW", "BLUE", "MAGENTA", "CYAN", "WHITE"]


# ---------------------------------------------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------------------------------------------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return hexc(tuple(x + (y - x) * t for x, y in zip(a, b)))


def lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


# Islands Dark grey ramp -> the graphite grey ramp.
GRAYS = {
    10: BG_DIM, 20: mix(BG_DIM, BG0, 0.5), 30: BG0, 40: BG1, 50: BG2, 60: BG3, 70: mix(BG5, GREY0, 0.3),
    80: GREY0, 90: GREY1, 100: GREY2, 110: mix(GREY2, FG, 0.4), 120: mix(GREY2, FG, 0.7), 130: FG,
    140: mix(FG, WHITE, 0.35), 150: mix(FG, WHITE, 0.65), 160: WHITE,
}

# Colour ramps: level 100 is the colour itself (Islands uses it for text: links, errors...),
# lower levels fade into the background, higher ones towards white.
DOWN = {10: 0.07, 20: 0.10, 30: 0.14, 40: 0.20, 50: 0.28, 60: 0.38, 70: 0.50, 80: 0.64, 90: 0.82}
UP = {110: 0.15, 120: 0.30, 130: 0.45, 140: 0.60, 150: 0.75, 160: 0.88}


def ramp(base):
    r = {lvl: mix(BG_DIM, base, t) for lvl, t in DOWN.items()}
    r[100] = base
    r.update({lvl: mix(base, WHITE, t) for lvl, t in UP.items()})
    return r


HUES = {"blue": BLUE, "green": GREEN, "red": RED, "yellow": YELLOW, "orange": ORANGE, "purple": PURPLE,
        "teal": AQUA}
RAMPS = {name: ramp(c) for name, c in HUES.items()}
ACCENTS = [RED, ORANGE, YELLOW, GREEN, AQUA, BLUE, PURPLE, PINK]

BG_RED = mix(BG_DIM, RED, 0.22)
BG_YELLOW = mix(BG_DIM, YELLOW, 0.2)
BG_GREEN = mix(BG_DIM, GREEN, 0.2)
BG_BLUE = mix(BG_DIM, BLUE, 0.22)

# Original Islands greys, to translate arbitrary greys by lightness.
ISLANDS_GRAYS = {10: "#191A1C", 20: "#212326", 30: "#26282C", 40: "#33353B", 50: "#40434A", 60: "#4C4F56",
                 70: "#5F6269", 80: "#73767C", 90: "#8B8E94", 100: "#9FA2A8", 110: "#B5B7BD", 120: "#C3C5CB",
                 130: "#D1D3D9", 140: "#DDDFE4", 150: "#E9EAEE", 160: "#F7F8F9"}
GRAY_POINTS = sorted([(lum("#000000"), "#000000")] + [(lum(ISLANDS_GRAYS[k]), GRAYS[k]) for k in GRAYS]
                     + [(1.0, "#ffffff")])


def accent_path(accent):
    """Colours from the background through the accent to white, keyed by luminance."""
    pts = [mix(BG_DIM, accent, i / 60) for i in range(61)] + [mix(accent, WHITE, i / 30) for i in range(1, 31)]
    return [(lum(p), p) for p in pts]


ACCENT_PATHS = {a: accent_path(a) for a in ACCENTS}

# Every colour the theme is built from; repainted colours within SNAP units of one are snapped onto it.
PALETTE = sorted({c.lower() for c in [FRAME, BG_DIM, BG0, BG1, BG2, BG3, BG4, BG5, BG_VISUAL, LIST_SELECTION,
                                      CURRENT_LINE, FG, GREY0, GREY1, GREY2, WHITE, PINK, SALMON, SAND, TEAL, CALL,
                                      PUNCTUATION, LAVENDER, BRONZE, RED, GREEN, BLUE]
                  + list(GRAYS.values()) + [c for r in RAMPS.values() for c in r.values()]})
SNAP = 4
# Foregrounds repainted from the parents are lifted to at least this contrast on their background (WCAG's minimum
# for large text; dimmed text such as comments and hints sits just above it).
MIN_CONTRAST = 3.0

# IntelliJ Dark's (and Darcula's, for the language keys IntelliJ Dark inherits) syntax colours, translated by what
# they mean, so language-specific keys follow the same style as SYNTAX below.
SYNTAX_COLORS = {
    # text (bbbbbb: Darcula's label text, which Islands keeps on a few keys)
    "bbbbbb": FG, "bcbec4": FG, "a9b7c6": FG, "bababa": FG, "c9cbd6": FG, "ced0d6": mix(FG, WHITE, 0.2), "dfe1e5": mix(FG, WHITE, 0.3),
    # keywords
    "cf8e6d": PINK, "cc7832": PINK,
    # strings
    "6aab73": SALMON, "6a8759": SALMON,
    # numbers
    "2aacb8": SAND, "6897bb": SAND,
    # regular expressions, labels, named arguments, custom tags
    "42c3d4": SALMON, "32b8af": FG, "56c1d6": FG, "2fbaa3": LAVENDER,
    # function declarations and calls
    "56a8f5": TEAL, "ffc66d": TEAL, "57aaf7": CALL,
    # links
    "589df6": BLUE, "548af7": BLUE, "5c92ff": BLUE, "83acfc": BLUE, "287bde": BLUE,
    # fields, properties, static members, globals: plain text (constants get sand in SYNTAX)
    "c77dbb": FG, "c77dba": FG, "9876aa": FG,
    # visited links, template variables, client components
    "b189f5": LAVENDER, "9c9cff": LAVENDER,
    # annotations, metadata
    "b3ae60": BRONZE, "b2ae60": BRONZE, "bbb529": BRONZE,
    # markup tags
    "d5b778": LAVENDER, "e8bf6a": LAVENDER,
    # errors
    "f75464": RED, "ff6b68": RED, "bc3f3c": RED,
    # comments and documentation
    "7a7e85": GREY1, "808080": GREY1, "5f826b": GREY1, "629755": GREY1, "67a37c": GREY2, "68a67e": GREY2,
    "abadb3": GREY2,
    # hints and dimmed text
    "6f737a": GREY0, "868a91": GREY1, "868991": GREY1, "858a94": GREY1, "727782": GREY0, "9da0a8": GREY2,
}
_cache = {}


def remap(value):
    """Repaints any colour: IntelliJ Dark's syntax colours by SYNTAX_COLORS, others keeping their lightness - greys
    onto the graphite grey ramp, colours onto the palette colour with the nearest hue. Translucent black/white/grey
    overlays are kept."""
    short = re.fullmatch(r"(#?)([0-9A-Fa-f]{1,5})", value or "")
    if short:  # schemes may drop leading zeros ("DA19E"), the IDE reads them as a number
        value = short.group(1) + short.group(2).zfill(6)
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?", value or "")
    if not m:
        return value
    key = value.lower()
    if key in _cache:
        return _cache[key]
    base, alpha = "#" + m.group(1), m.group(2) or ""
    r, g, b = (v / 255 for v in rgb(base))
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    if m.group(1).lower() in SYNTAX_COLORS:
        out = SYNTAX_COLORS[m.group(1).lower()] + alpha
    elif alpha and alpha.lower() != "ff" and sat < 0.08:
        out = value  # neutral overlay (shadows, hover tints): no colour to repaint
    elif sat < 0.16 or light < 0.06:
        y = lum(base)
        for (y0, c0), (y1, c1) in zip(GRAY_POINTS, GRAY_POINTS[1:]):
            if y0 <= y <= y1:
                out = mix(c0, c1, 0 if y1 == y0 else (y - y0) / (y1 - y0))
                break
        out = out + alpha
    else:
        def hue_dist(a):
            ha = colorsys.rgb_to_hls(*(v / 255 for v in rgb(a)))[0]
            d = abs(ha - hue)
            return min(d, 1 - d)
        accent = min(ACCENTS, key=hue_dist)
        y = lum(base)
        out = min(ACCENT_PATHS[accent], key=lambda p: abs(p[0] - y))[1] + alpha
    out = snap(out[:7]) + out[7:]
    if value.startswith("#"):
        out = out if out.startswith("#") else "#" + out
    else:
        out = out.lstrip("#")
    _cache[key] = out
    return out


def saturation(c):
    return colorsys.rgb_to_hls(*(v / 255 for v in rgb(c)))[2]


def snap(c):
    """A repainted colour a few units off a palette colour becomes that colour, so near-twins do not multiply. Greys
    snap onto greys only, so a neutral surface never picks up a tint."""
    grey = saturation(c) < 0.16
    candidates = [p for p in PALETTE + _snapped if (saturation(p) < 0.16) == grey]
    near = min(candidates, key=lambda p: max(abs(x - y) for x, y in zip(rgb(p), rgb(c))))
    if max(abs(x - y) for x, y in zip(rgb(near), rgb(c))) <= SNAP:
        return near
    _snapped.append(c.lower())  # later colours close to this one become this one
    return c


_snapped = []


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable(fg, bg):
    """fg, lifted along its grey ramp or accent path until it reads on bg (MIN_CONTRAST)."""
    if contrast(fg, bg) >= MIN_CONTRAST:
        return fg
    r, g, b = (v / 255 for v in rgb(fg))
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.16:
        steps = [GRAYS[k] for k in sorted(GRAYS)]
    else:
        def hue_dist(a):
            d = abs(colorsys.rgb_to_hls(*(v / 255 for v in rgb(a)))[0] - hue)
            return min(d, 1 - d)
        steps = [p for _, p in sorted(ACCENT_PATHS[min(ACCENTS, key=hue_dist)])]
    return next((s for s in steps if lum(s) > lum(fg) and contrast(s, bg) >= MIN_CONTRAST), fg)


def bare(c):
    return c.lstrip("#").upper()


# ---------------------------------------------------------------------------------------------------------------
# Reading the IDE
# ---------------------------------------------------------------------------------------------------------------
LIB = IDE / "Contents/lib"


def read_resource(jar, name):
    with zipfile.ZipFile(jar) as z:
        return z.read(name).decode("utf-8")


def flatten(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flatten(v, prefix + k + ".")
        else:
            yield prefix + k, v


def effective_ui(chain):
    """The UI values the IDE ends up with for a parent chain (root first), as UIThemeBean and UITheme compute them: a
    theme keeps its parent's keys it does not set itself, ahead of its own; then the keys are applied in that order,
    and a "*.x" pattern overwrites every key set so far that ends with ".x". Values a pattern overwrote are dropped:
    they are no longer used. The patterns are returned too, in the order they apply."""
    merged = {}
    for theme in chain:
        own = {k: v for k, v in flatten(theme.get("ui", {})) if not (".os." in "." + k + "." or k.startswith("os."))}
        merged = {**{k: v for k, v in merged.items() if k not in own}, **own}
    applied = {}
    for key, value in merged.items():
        if key.startswith("*."):
            tail = key[1:]
            for k in [k for k in applied if k.endswith(tail) and not k.startswith("*.")]:
                del applied[k]
        applied[key] = value
    return applied


# ---------------------------------------------------------------------------------------------------------------
# UI theme
# ---------------------------------------------------------------------------------------------------------------
def build_theme():
    impl = LIB / "intellij.platform.ide.impl.jar"
    chain = [json.loads(read_resource(impl, p)) for p in
             ("themes/darcula.theme.json", "themes/expUI/expUI_dark.theme.json",
              "themes/islands/ManyIslandsDark.theme.json")]

    colors = {}
    # Named colours of the new UI dark theme: Gray1..14, Blue1..13, ...
    for name, value in chain[1]["colors"].items():
        colors[name] = remap(value)
    # Named colours of Islands Dark: palette ramps first...
    islands = chain[2]["colors"]
    for name, value in islands.items():
        m = re.fullmatch(r"(gray|blue|green|red|yellow|orange|purple|teal)-(\d+)", name)
        if m:
            colors[name] = GRAYS[int(m.group(2))] if m.group(1) == "gray" else RAMPS[m.group(1)][int(m.group(2))]
    # ...then the semantic ones that are literal colours.
    for name, value in islands.items():
        if name not in colors and isinstance(value, str) and value.startswith("#"):
            colors[name] = remap(value)
    colors.update({
        "white": WHITE,
        "text-over-accent": WHITE,
        "editor-text": FG,
        "main-window-bg": FRAME,
        "transparent": BG_DIM + "00",
        # The accent is a soft system blue: default buttons, selected tabs, progress...
        "accent-brand-bg": RAMPS["blue"][70],
        "accent-brand-border": RAMPS["blue"][70],
        "accent-brand-bg-secondary": RAMPS["blue"][40],
        "accent-brand-border-secondary": RAMPS["blue"][60],
        "selection-bg-active": LIST_SELECTION,
        "selection-bg-active-muted": mix(BG_DIM, LIST_SELECTION, 0.7),
        "selection-bg-inactive": BG2,
        "tab-selected-bg-active": RAMPS["blue"][40],
        "tab-selected-border-active": RAMPS["blue"][60],
        "toolbar-selected-bg": RAMPS["blue"][60],
        "toolbar-selected-bg-hovered": RAMPS["blue"][70],
        "got-it-bg": RAMPS["blue"][60],
        "got-it-border": RAMPS["blue"][60],
        "got-it-text-link": RAMPS["blue"][110],
        "presentation-assistant-bg": RAMPS["blue"][60],
        "popup-completion-match-text": BLUE,
        "search-match-bg": RAMPS["yellow"][80],
        "tab-file-color-mask-bg": BG_DIM + "80",
        "icon-default-stroke": GRAYS[120],
    })

    # Hard-coded colours the parent chain really ends up with. Repainting a key the IDE no longer uses would bring it
    # back: our "ui" is applied after the parents' "*.x" patterns, so a Darcula Tree.background repainted here would
    # beat Islands' "*.background" and paint trees, tables and fields in a colour of their own.
    effective = effective_ui(chain)
    overrides = {}
    for key, value in effective.items():
        if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", value):
            new = remap(value)
            if new.lower() != value.lower():
                overrides[key] = new
    overrides.update({
        "Editor.ToolTip.selectionBackground": BG1,
        "MainWindow.Tab.background": BG_DIM,
        "DragAndDrop.rowBackground": BLUE + "26",
        "ToolWindow.Button.DragAndDrop.buttonDropBackground": BLUE + "80",
        "ToolWindow.DragAndDrop.areaBackground": BLUE + "4D",
        "MemoryIndicator.usedBackground": RAMPS["blue"][50] + "80",
        # Darcula's pre-new-UI keys that Islands never repaints: the surfaces and text of the islands, so that nothing
        # built on the old look-and-feel keys shows a colour of its own.
        "*.textBackground": BG_DIM,
        "*.textForeground": FG,
        "*.caretForeground": FG,
        "*.selectionForegroundInactive": FG,
        "*.selectionBackgroundInactive": BG2,  # selection-bg-inactive
        "control": BG_DIM,
        "window": BG_DIM,
        "controlText": FG,
        "text": FG,
        "textText": FG,
        "infoText": FG,
        "textInactiveText": GREY1,
    })
    # A repainted "*.x" pattern of ours runs after every parent key, so the keys ending with ".x" that the parents set
    # after their own pattern have to be set again (ours apply in sorted order: patterns first).
    for pattern in [k for k in overrides if k.startswith("*.")]:
        for key, value in effective.items():
            if key.endswith(pattern[1:]) and not key.startswith("*.") and key not in overrides:
                overrides[key] = value

    # The icon colour Islands repaints its monochrome icons with.
    icons = {"ColorPalette": {"#CED0D6": GRAYS[120]}}

    theme = {
        "name": THEME_NAME,
        "dark": True,
        "author": "pallad42",
        "parentTheme": "Islands Dark",
        "editorScheme": THEME_NAME,
        "colors": colors,
        "ui": dict(sorted(overrides.items())),
        "icons": icons,
    }
    OUT_THEME.parent.mkdir(parents=True, exist_ok=True)
    OUT_THEME.write_text(json.dumps(theme, indent=2) + "\n")
    print(f"{OUT_THEME.relative_to(ROOT)}: {len(colors)} named colours, {len(overrides)} UI keys")


# ---------------------------------------------------------------------------------------------------------------
# Editor colour scheme
# ---------------------------------------------------------------------------------------------------------------
COLOR_VALUE_OPTIONS = {"FOREGROUND", "BACKGROUND", "EFFECT_COLOR", "ERROR_STRIPE_COLOR"}


def remap_attr_value(value_el):
    for opt in value_el.findall("option"):
        if opt.get("name") in COLOR_VALUE_OPTIONS:
            for a in ("value", "deuteranopia", "protanopia"):
                if opt.get(a):
                    opt.set(a, bare(remap("#" + opt.get(a))))
    # Text must read on its own background, or on the editor's.
    options = {o.get("name"): o for o in value_el.findall("option")}
    fg, bg = options.get("FOREGROUND"), options.get("BACKGROUND")
    if fg is not None and len(fg.get("value") or "") == 6:
        back = "#" + bg.get("value") if bg is not None and len(bg.get("value") or "") == 6 else BG_DIM
        fg.set("value", bare(readable("#" + fg.get("value"), back)))


def attr(fg=None, bg=None, font=None, effect=None, effect_color=None, stripe=None):
    """FONT_TYPE: 1 bold, 2 italic, 3 both. EFFECT_TYPE: 1 underline, 2 wave, 3 strikeout, 4 bold dotted, 5 box."""
    v = ET.Element("value")
    for name, val in (("FOREGROUND", fg), ("BACKGROUND", bg), ("FONT_TYPE", font), ("EFFECT_COLOR", effect_color),
                      ("EFFECT_TYPE", effect), ("ERROR_STRIPE_COLOR", stripe)):
        if val is not None:
            ET.SubElement(v, "option", name=name, value=bare(val) if isinstance(val, str) and val.startswith("#")
                          else str(val))
    return v


BOLD, ITALIC, BOLD_ITALIC = 1, 2, 3
UNDERLINE, WAVE, STRIKEOUT, BOX = 1, 2, 3, 5

# Xcode's Default (Dark) syntax colours, toned down: keywords, strings, values, function declarations, types,
# annotations and comments are coloured, calls get a lighter teal; fields and variables stay plain text and
# punctuation is dimmed. No bold, as in Xcode.
SYNTAX = {
    "TEXT": attr(FG, BG_DIM),
    "DEFAULT_IDENTIFIER": attr(FG),
    "DEFAULT_KEYWORD": attr(PINK),
    "DEFAULT_STRING": attr(SALMON),
    "DEFAULT_VALID_STRING_ESCAPE": attr(SAND),
    "DEFAULT_INVALID_STRING_ESCAPE": attr(RED, effect=WAVE, effect_color=RED),
    "DEFAULT_NUMBER": attr(SAND),
    "DEFAULT_CONSTANT": attr(SAND),
    "DEFAULT_PREDEFINED_SYMBOL": attr(PINK),
    "DEFAULT_LINE_COMMENT": attr(GREY1, font=ITALIC),
    "DEFAULT_BLOCK_COMMENT": attr(GREY1, font=ITALIC),
    "DEFAULT_DOC_COMMENT": attr(GREY1, font=ITALIC),
    "DEFAULT_DOC_COMMENT_TAG": attr(GREY2, font=ITALIC),
    "DEFAULT_DOC_COMMENT_TAG_VALUE": attr(GREY2, font=ITALIC),
    "DEFAULT_DOC_MARKUP": attr(GREY2),
    "DEFAULT_FUNCTION_DECLARATION": attr(TEAL),
    "DEFAULT_FUNCTION_CALL": attr(CALL),
    "DEFAULT_INSTANCE_METHOD": attr(CALL),
    "DEFAULT_STATIC_METHOD": attr(CALL),
    "DEFAULT_INSTANCE_FIELD": attr(FG),
    "DEFAULT_STATIC_FIELD": attr(FG),
    "DEFAULT_CLASS_NAME": attr(LAVENDER),
    "DEFAULT_CLASS_REFERENCE": attr(LAVENDER),
    "DEFAULT_INTERFACE_NAME": attr(LAVENDER),
    "TYPE_PARAMETER_NAME_ATTRIBUTES": attr(LAVENDER),
    "TS.TYPE_PARAMETER": attr(LAVENDER),
    "DEFAULT_LOCAL_VARIABLE": attr(FG),
    "DEFAULT_PARAMETER": attr(FG),
    "DEFAULT_GLOBAL_VARIABLE": attr(FG),
    "DEFAULT_OPERATION_SIGN": attr(PUNCTUATION),
    "DEFAULT_BRACES": attr(PUNCTUATION),
    "DEFAULT_BRACKETS": attr(PUNCTUATION),
    "DEFAULT_PARENTHS": attr(PUNCTUATION),
    "DEFAULT_COMMA": attr(PUNCTUATION),
    "DEFAULT_SEMICOLON": attr(PUNCTUATION),
    "DEFAULT_DOT": attr(PUNCTUATION),
    "DEFAULT_METADATA": attr(BRONZE),
    "ANNOTATION_NAME_ATTRIBUTES": attr(BRONZE),
    "DEFAULT_LABEL": attr(FG),
    "DEFAULT_TAG": attr(LAVENDER),
    "DEFAULT_ATTRIBUTE": attr(FG),
    "DEFAULT_ENTITY": attr(SAND),
    "DEFAULT_TEMPLATE_LANGUAGE_COLOR": attr(FG, BG0),
    "HTML_TAG_NAME": attr(LAVENDER),
    "HTML_CUSTOM_TAG_NAME": attr(LAVENDER),
    "HTML_ATTRIBUTE_NAME": attr(FG),
    "HTML_ATTRIBUTE_VALUE": attr(SALMON),
    "HTML_ENTITY_REFERENCE": attr(SAND),
    "XML_TAG_NAME": attr(LAVENDER),
    "XML_CUSTOM_TAG_NAME": attr(LAVENDER),
    "XML_ATTRIBUTE_NAME": attr(FG),
    "XML_ATTRIBUTE_VALUE": attr(SALMON),
    "XML_ENTITY_REFERENCE": attr(SAND),
    "XML_PROLOGUE": attr(GREY1),
    "CSS.PROPERTY_NAME": attr(FG),
    "CSS.PROPERTY_VALUE": attr(SALMON),
    "CSS.IDENT": attr(FG),
    "CSS.COLOR": attr(SAND),
    "CSS.IMPORTANT": attr(PINK),
    # Languages whose own colours the translation by meaning gets wrong: comments are comments, variables plain text.
    "HAML_COMMENT": attr(GREY1, font=ITALIC),
    "SASS_COMMENT": attr(GREY1, font=ITALIC),
    "LESS_VARIABLE": attr(FG),
    "SASS_VARIABLE": attr(FG),
    "XPATH.KEYWORD": attr(PINK),
    "PROPERTIES.KEY": attr(TEAL),
    "PROPERTIES.VALUE": attr(SALMON),
    "YAML_SCALAR_KEY": attr(TEAL),
    "JSON.PROPERTY_KEY": attr(TEAL),
    "MARKDOWN_HEADER_LEVEL_1": attr(PINK, font=BOLD),
    "MARKDOWN_HEADER_LEVEL_2": attr(PINK, font=BOLD),
    "MARKDOWN_HEADER_LEVEL_3": attr(PINK, font=BOLD),
    "MARKDOWN_HEADER_LEVEL_4": attr(PINK, font=BOLD),
    "MARKDOWN_HEADER_LEVEL_5": attr(PINK, font=BOLD),
    "MARKDOWN_HEADER_LEVEL_6": attr(PINK, font=BOLD),
    "MARKDOWN_CODE_SPAN": attr(SALMON),
    "MARKDOWN_LINK_TEXT": attr(BLUE, effect=UNDERLINE, effect_color=BLUE),
    "MARKDOWN_AUTO_LINK": attr(BLUE),
    "MARKDOWN_BOLD": attr(FG, font=BOLD),
    "MARKDOWN_ITALIC": attr(FG, font=ITALIC),
    "TODO_DEFAULT_ATTRIBUTES": attr(BLUE, font=ITALIC, stripe=BLUE),
    "HYPERLINK_ATTRIBUTES": attr(BLUE, effect=UNDERLINE, effect_color=BLUE),
    "FOLLOWED_HYPERLINK_ATTRIBUTES": attr(LAVENDER, effect=UNDERLINE, effect_color=LAVENDER),
    "CTRL_CLICKABLE": attr(BLUE, effect=UNDERLINE, effect_color=BLUE),
    "ERRORS_ATTRIBUTES": attr(effect=WAVE, effect_color=RED, stripe=RED),
    "WARNING_ATTRIBUTES": attr(effect=WAVE, effect_color=YELLOW, stripe=YELLOW),
    "WRONG_REFERENCES_ATTRIBUTES": attr(RED),
    "NOT_USED_ELEMENT_ATTRIBUTES": attr(GREY2),
    "BAD_CHARACTER": attr(RED, effect=WAVE, effect_color=RED),
    "MATCHED_BRACE_ATTRIBUTES": attr(bg=BG4),
    "UNMATCHED_BRACE_ATTRIBUTES": attr(RED, effect=WAVE, effect_color=RED),
    "IDENTIFIER_UNDER_CARET_ATTRIBUTES": attr(bg=BG2, stripe=GREY1),
    "WRITE_IDENTIFIER_UNDER_CARET_ATTRIBUTES": attr(bg=BG_RED, stripe=RED),
    "SEARCH_RESULT_ATTRIBUTES": attr(bg=mix(BG_DIM, BLUE, 0.30), stripe=BLUE),
    "WRITE_SEARCH_RESULT_ATTRIBUTES": attr(bg=mix(BG_DIM, RED, 0.28), stripe=RED),
    "TEXT_SEARCH_RESULT_ATTRIBUTES": attr(bg=mix(BG_DIM, SAND, 0.28), stripe=SAND),
    "FOLDED_TEXT_ATTRIBUTES": attr(GREY2, BG1),
    "LIVE_TEMPLATE_ATTRIBUTES": attr(effect=BOX, effect_color=BLUE),
    "INLAY_DEFAULT": attr(GREY2, BG0),
    "INLINE_PARAMETER_HINT": attr(GREY2, BG0),
    "INLINE_PARAMETER_HINT_CURRENT": attr(FG, BG2),
    "INLINE_PARAMETER_HINT_HIGHLIGHTED": attr(FG, BG1),
    "INLAY_TEXT_WITHOUT_BACKGROUND": attr(GREY2),
    "BREADCRUMBS_DEFAULT": attr(GREY2),
    "BREADCRUMBS_CURRENT": attr(FG, BG1),
    "BREADCRUMBS_HOVERED": attr(FG, BG1),
    "BREADCRUMBS_INACTIVE": attr(GREY0),
    "CONSOLE_NORMAL_OUTPUT": attr(FG),
    "CONSOLE_ERROR_OUTPUT": attr(RED),
    "CONSOLE_SYSTEM_OUTPUT": attr(GREY2),
    "CONSOLE_USER_INPUT": attr(GREEN),
    "LOG_ERROR_OUTPUT": attr(RED),
    "LOG_WARNING_OUTPUT": attr(YELLOW),
    "LOG_INFO_OUTPUT": attr(FG),
    "LOG_DEBUG_OUTPUT": attr(GREY2),
    "LOG_VERBOSE_OUTPUT": attr(GREY1),
}
for name, color in ANSI:
    SYNTAX[f"CONSOLE_{name}_OUTPUT"] = attr(color, color)  # same colour as text and as background, like a terminal emulator
for i, name in enumerate(BLOCK_TERMINAL):
    SYNTAX[f"BLOCK_TERMINAL_{name}"] = attr(ANSI[i][1], ANSI[i][1])
    SYNTAX[f"BLOCK_TERMINAL_{name}_BRIGHT"] = attr(ANSI[i + 8][1], ANSI[i + 8][1])

COLORS = {
    "CARET_COLOR": WHITE,
    "CARET_ROW_COLOR": CURRENT_LINE,
    "SELECTION_BACKGROUND": BG_VISUAL,
    "SELECTION_FOREGROUND": "",  # keep syntax colours in a selection
    "CONSOLE_BACKGROUND_KEY": BG_DIM,
    "LINE_NUMBERS_COLOR": GREY0,
    "GUTTER_BACKGROUND": BG_DIM,  # legacy key Darcula still sets; the gutter is the editor
    "LINE_NUMBER_ON_CARET_ROW_COLOR": GREY2,
    "INDENT_GUIDE": BG1,
    "SELECTED_INDENT_GUIDE": BG4,
    "MATCHED_BRACES_INDENT_GUIDE_COLOR": BG4,
    "VISUAL_INDENT_GUIDE": BG1,
    "RIGHT_MARGIN_COLOR": BG1,
    "METHOD_SEPARATORS_COLOR": BG2,
    "WHITESPACES": BG4,
    "TEARLINE_COLOR": BG2,
    "SELECTED_TEARLINE_COLOR": GREY1,
    "ADDED_LINES_COLOR": mix(BG_DIM, GREEN, 0.6),
    "MODIFIED_LINES_COLOR": mix(BG_DIM, BLUE, 0.6),
    "DELETED_LINES_COLOR": mix(BG_DIM, RED, 0.6),
    "WHITESPACES_MODIFIED_LINES_COLOR": mix(BG_DIM, ORANGE, 0.3),
    "IGNORED_ADDED_LINES_BORDER_COLOR": mix(BG_DIM, GREEN, 0.6),
    "IGNORED_MODIFIED_LINES_BORDER_COLOR": mix(BG_DIM, BLUE, 0.6),
    "IGNORED_DELETED_LINES_BORDER_COLOR": mix(BG_DIM, RED, 0.6),
    "LOOKUP_COLOR": BG0,
    "DOCUMENTATION_COLOR": BG0,
    "INFORMATION_HINT": BG1,
    "QUESTION_HINT": BG_BLUE,
    "ERROR_HINT": BG_RED,
    "NOTIFICATION_BACKGROUND": BG_GREEN,
    "PROMOTION_PANE": BG_GREEN,
    "HINT_BORDER": BG3,
    "FOLDED_TEXT_BORDER_COLOR": BG2,
    "DIFF_SEPARATORS_BACKGROUND": BG1,
    "ANNOTATIONS_COLOR": GREY1,
    "ANNOTATIONS_LAST_COMMIT_COLOR": FG,
    "FILESTATUS_ADDED": GREEN,
    "FILESTATUS_COPIED": GREEN,
    "FILESTATUS_addedOutside": GREEN,
    "FILESTATUS_MODIFIED": BLUE,
    "FILESTATUS_modifiedOutside": BLUE,
    "FILESTATUS_NOT_CHANGED_IMMEDIATE": BLUE,
    "FILESTATUS_NOT_CHANGED_RECURSIVE": BLUE,
    "FILESTATUS_RENAMED": BLUE,
    "FILESTATUS_DELETED": GREY0,
    "FILESTATUS_IDEA_FILESTATUS_DELETED_FROM_FILE_SYSTEM": GREY0,
    "FILESTATUS_IDEA_FILESTATUS_IGNORED": ORANGE,
    "FILESTATUS_UNKNOWN": RED,
    "FILESTATUS_MERGED": PURPLE,
    "FILESTATUS_IDEA_FILESTATUS_MERGED_WITH_CONFLICTS": RED,
    "FILESTATUS_IDEA_FILESTATUS_MERGED_WITH_BOTH_CONFLICTS": RED,
    "FILESTATUS_IDEA_FILESTATUS_MERGED_WITH_PROPERTY_CONFLICTS": RED,
    "FILESTATUS_changelistConflict": RED,
}


def build_scheme():
    impl = LIB / "intellij.platform.ide.impl.jar"
    defaults = ET.fromstring(read_resource(impl, "DefaultColorSchemesManager.xml"))
    darcula = next(s for s in defaults.iter("scheme") if s.get("name") == "Darcula")
    islands = ET.fromstring(read_resource(impl, "themes/islands/IslandSchemeDark.xml"))

    colors, attributes = {}, {}

    def take(colors_el, attrs_el):
        if colors_el is not None:
            for o in colors_el.findall("option"):
                colors[o.get("name")] = o
        if attrs_el is not None:
            for o in attrs_el.findall("option"):
                attributes[o.get("name")] = o

    take(darcula.find("colors"), darcula.find("attributes"))
    # What bundled plugins add to Darcula (JavaScript, SQL, Markdown, YAML...).
    for jar in sorted(list(LIB.glob("*.jar")) + list((IDE / "Contents/plugins").glob("*/lib/**/*.jar"))):
        try:
            with zipfile.ZipFile(jar) as z:
                names = [n for n in z.namelist() if re.fullmatch(r"colorSchemes/[^/]*Darcula\.xml", n)]
                for n in names:
                    take(None, ET.fromstring(z.read(n)))
        except zipfile.BadZipFile:
            pass
    take(islands.find("colors"), islands.find("attributes"))

    for o in colors.values():
        for a in ("value", "deuteranopia", "protanopia"):
            if o.get(a):
                o.set(a, bare(remap("#" + o.get(a))))
    for o in attributes.values():
        v = o.find("value")
        if v is not None:
            remap_attr_value(v)

    for name, value in COLORS.items():
        colors[name] = ET.Element("option", name=name, value=bare(value) if value else "")
    for name, value in SYNTAX.items():
        el = ET.Element("option", name=name)
        el.append(value)
        attributes[name] = el

    scheme = ET.Element("scheme", name=THEME_NAME, version="142", parent_scheme="Darcula")
    meta = ET.SubElement(scheme, "metaInfo")
    ET.SubElement(meta, "property", name="ide").text = "idea"
    ET.SubElement(meta, "property", name="ideVersion").text = "2026.2.0.0"
    ET.SubElement(meta, "property", name="originalScheme").text = THEME_NAME
    # No font here: a scheme stores whole font sizes only, so the plugin sets the font (13.5) in the editor's own
    # font settings instead (FontDefaults), and the scheme keeps using them.
    colors_el = ET.SubElement(scheme, "colors")
    for name in sorted(colors):
        colors_el.append(colors[name])
    attrs_el = ET.SubElement(scheme, "attributes")
    for name in sorted(attributes):
        o = attributes[name]
        o.tail = None
        attrs_el.append(o)

    ET.indent(scheme, space="  ")
    OUT_SCHEME.write_text(ET.tostring(scheme, encoding="unicode") + "\n")
    print(f"{OUT_SCHEME.relative_to(ROOT)}: {len(colors)} colours, {len(attributes)} attributes")


if __name__ == "__main__":
    build_theme()
    build_scheme()
