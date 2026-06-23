import os
import json
from pathlib import Path
from PyQt5.QtGui import QColor, QPixmap, QPainter
from PyQt5.QtCore import Qt


def blend_color(base_color: QColor, target_color: QColor, ratio: float) -> str:
    r = int(base_color.red() + (target_color.red() - base_color.red()) * ratio)
    g = int(base_color.green() + (target_color.green() - base_color.green()) * ratio)
    b = int(base_color.blue() + (target_color.blue() - base_color.blue()) * ratio)
    return QColor(r, g, b).name()


class LumosThemeManager:
    def __init__(self):
        self.color_ff0000 = "#ff0000"
        self.color_ffef28 = "#ffef28"

        self._set_default_colors()

        from PyQt5.QtWidgets import QApplication

        if QApplication.instance():
            self.reload_theme()

    def _set_default_colors(self):
        self.is_dark = True
        self.color1 = "#1e1e1e"
        self.color2 = "#252526"
        self.color3 = "#2a2a2a"
        self.color4 = "#2d2d2d"
        self.color5 = "#181a1b"
        self.color6 = "#1a1a1a"
        self.color7 = "#2d2d30"
        self.color8 = "#2a2d2e"
        self.color9 = "#323232"
        self.color10 = "#333333"
        self.color11 = "#37373d"
        self.color12 = "#3a3a3a"
        self.color13 = "#3c3c3c"
        self.color14 = "#3e3e3e"
        self.color15 = "#404040"
        self.color16 = "#454545"
        self.color17 = "#4a4a4a"
        self.color18 = "#505050"
        self.color19 = "#555"
        self.color20 = "#656d76"
        self.color21 = "#666"
        self.color22 = "#666666"
        self.color23 = "#808080"
        self.color24 = "#969696"
        self.color25 = "#1177aa"
        self.color26 = "#cccccc"
        self.color27 = "#d4d4d4"
        self.color28 = "#dddddd"
        self.color29 = "#e0e0e0"
        self.color30 = "#eee"
        self.color31 = "#ffffff"
        self.color32 = "#004d99"
        self.color33 = "#005fb8"
        self.color34 = "#006bb3"
        self.color35 = "#007acc"
        self.color36 = "#007fd4"
        self.color37 = "#008ae6"
        self.color38 = "#0098ff"
        self.color39 = "#9cdcfe"
        self.color40 = "#aeafad"
        self.color41 = "#d0d7de"
        self.color42 = "#d7ba7d"
        self.color43 = "#15ffffff"
        self.color44 = "#25ffffff"

    def reload_theme(self, theme_name=None):
        if not theme_name:
            config_path = Path.home() / ".lumos_editor" / "config.json"
            theme_name = "default"
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        theme_name = cfg.get("theme", "default")
                except Exception:
                    pass

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        theme_path = os.path.join(base_dir, "themes", theme_name, "theme.json")

        theme_data = {}
        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    theme_data = json.load(f)
            except Exception:
                pass

        t = theme_data.get("theme", {})
        c_paper = QColor(t.get("paper-color", "#1e1e1e"))
        c_margin = QColor(t.get("margin-color", "#8d8a9f"))
        c_text = QColor("#d4d4d4")
        c_accent = QColor("#0098ff")

        for syntax in t.get("syntax", []):
            if "default" in syntax:
                c_text = QColor(syntax["default"].get("color", c_text.name()))
            if "keyword" in syntax:
                c_accent = QColor(syntax["keyword"].get("color", c_accent.name()))

        self.is_dark = c_paper.lightness() < 128
        bg_target = QColor("#ffffff") if self.is_dark else QColor("#000000")
        inv_target = QColor("#000000") if self.is_dark else QColor("#ffffff")

        c_ui_bg = QColor(blend_color(c_paper, inv_target, 0.12))
        c_hover = blend_color(c_ui_bg, bg_target, 0.08)
        c_border = blend_color(c_ui_bg, bg_target, 0.15)
        c_strong = blend_color(c_ui_bg, bg_target, 0.30)

        c_subtext = blend_color(c_text, c_ui_bg, 0.20)
        c_accent_dark = blend_color(c_accent, inv_target, 0.3)
        c_accent_light = blend_color(c_accent, bg_target, 0.2)

        self.color1 = c_paper.name()
        self.color2 = c_ui_bg.name()
        self.color3 = c_ui_bg.name()
        self.color4 = c_ui_bg.name()
        self.color5 = blend_color(c_ui_bg, inv_target, 0.15)
        self.color6 = blend_color(c_ui_bg, inv_target, 0.10)
        self.color7 = blend_color(c_ui_bg, inv_target, 0.05)

        self.color8 = c_hover
        self.color9 = c_hover
        self.color10 = c_hover
        self.color11 = blend_color(c_ui_bg, bg_target, 0.12)

        self.color12 = c_border
        self.color13 = c_border
        self.color14 = c_border
        self.color15 = c_border
        self.color16 = c_border

        self.color17 = c_strong
        self.color18 = c_strong
        self.color19 = blend_color(c_ui_bg, bg_target, 0.45)

        self.color20 = c_margin.name()
        self.color21 = c_margin.name()
        self.color22 = c_margin.name()
        self.color23 = c_margin.name()
        self.color24 = c_margin.name()
        self.color25 = c_margin.name()

        self.color26 = c_subtext
        self.color27 = c_text.name()
        self.color28 = c_text.name()
        self.color29 = c_text.name()
        self.color30 = c_text.name()
        self.color31 = "#ffffff" if self.is_dark else "#000000"

        self.color32 = c_accent_dark
        self.color33 = c_accent_dark
        self.color34 = c_accent_dark
        self.color35 = c_accent.name()
        self.color36 = c_accent.name()
        self.color37 = c_accent_light
        self.color38 = c_accent.name()

        self.color39 = c_text.name()
        self.color40 = blend_color(c_text, c_accent, 0.5)
        self.color41 = c_text.name()
        self.color42 = c_accent.name()

        if self.is_dark:
            self.color43 = "#15ffffff"
            self.color44 = "#25ffffff"
        else:
            self.color43 = "#10000000"
            self.color44 = "#25000000"

        self.generate_themed_icons(base_dir)

    def generate_themed_icons(self, base_dir):
        template_dir = os.path.join(base_dir, "resources", "templates")
        output_dir = os.path.join(base_dir, "resources")

        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        group_a = [
            "chevron-right-window.png",
            "close-window-icon.png",
            "minimize-window-icon.png",
            "restore-window-icon.png",
            "default-icon.png",
        ]

        group_b = [
            "chevron-down.png",
            "chevron-left.png",
            "chevron-right.png",
            "close-icon.png",
            "copy-icon.png",
            "folder-closed.png",
            "folder-open.png",
        ]

        color_a = QColor(self.color31)
        color_b = QColor(self.color38)

        def recolor_and_save(filename, target_color):
            in_path = os.path.join(template_dir, filename)
            out_path = os.path.join(output_dir, filename)

            if not os.path.exists(in_path):
                return

            pixmap = QPixmap(in_path)
            if pixmap.isNull():
                return

            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), target_color)
            painter.end()

            pixmap.save(out_path)

        for icon in group_a:
            recolor_and_save(icon, color_a)

        for icon in group_b:
            recolor_and_save(icon, color_b)


try:
    theme = LumosThemeManager()
except Exception:
    pass
