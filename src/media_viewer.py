from .theme_manager import theme
import os

from PyQt5.QtCore import QSize, Qt, QUrl
from PyQt5.QtGui import QFont, QMovie, QPixmap, QWheelEvent
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class ImageViewer(QWidget):
    def __init__(self, filepath):
        super().__init__()
        self.is_modified = None
        self.filepath = os.path.abspath(filepath)
        self.editor = None
        self.tabname = (
            os.path.splitext(os.path.basename(filepath))[0][:27] + "..."
            if len(os.path.splitext(os.path.basename(filepath))[0]) > 26
            else os.path.basename(filepath)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        self.scale_factor = 1.0
        self.original_size = None
        self.movie = None
        self.load_image(filepath)

    def load_image(self, filepath):
        if filepath.lower().endswith(".gif"):
            self.movie = QMovie(filepath)
            if self.movie.isValid():
                self.label.setMovie(self.movie)
                self.movie.start()
                self.original_size = self.movie.currentPixmap().size()
                return
            else:
                QMessageBox.warning(self, "Error", "Could not load GIF.")
                self.close()
                return
        self.original_pixmap = QPixmap(filepath)
        if self.original_pixmap.isNull():
            QMessageBox.warning(self, "Error", "Could not load image.")
            self.close()
            return
        self.original_size = self.original_pixmap.size()
        if self.original_size.width() > 2000 or self.original_size.height() > 2000:
            self.scale_factor = min(
                2000 / self.original_size.width(), 2000 / self.original_size.height()
            )
        self.update_image()

    def update_image(self):
        if self.movie:
            available_size = self.size() * 0.9
            current_size = self.original_size * self.scale_factor
            if (
                current_size.width() > available_size.width()
                or current_size.height() > available_size.height()
            ):
                width_ratio = available_size.width() / self.original_size.width()
                height_ratio = available_size.height() / self.original_size.height()
                self.scale_factor = min(width_ratio, height_ratio)
                current_size = self.original_size * self.scale_factor
            scaled_size = QSize(int(current_size.width()), int(current_size.height()))
            self.movie.setScaledSize(scaled_size)
            self.label.setFixedSize(scaled_size)
            return
        if not self.original_pixmap.isNull():
            available_size = self.size() * 0.9
            current_pixmap_size = self.original_pixmap.size() * self.scale_factor
            if (
                current_pixmap_size.width() > available_size.width()
                or current_pixmap_size.height() > available_size.height()
            ):
                width_ratio = available_size.width() / self.original_size.width()
                height_ratio = available_size.height() / self.original_size.height()
                self.scale_factor = min(width_ratio, height_ratio)
            final_scale = self.scale_factor
            new_size = self.original_size * final_scale
            scaled_pixmap = self.original_pixmap.scaled(
                int(new_size.width()),
                int(new_size.height()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    def wheelEvent(self, event: QWheelEvent):
        if self.movie or not self.original_pixmap.isNull():
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            new_factor = self.scale_factor * factor
            if 0.1 <= new_factor <= 5.0:
                self.scale_factor = new_factor
                self.update_image()


class VideoViewer(QWidget):
    def __init__(self, filepath):
        super().__init__()
        self.setStyleSheet("background-color: black;")
        self.is_modified = None
        self.filepath = os.path.abspath(filepath)
        self.tabname = (
            os.path.splitext(os.path.basename(filepath))[0][:27] + "..."
            if len(os.path.splitext(os.path.basename(filepath))[0]) > 26
            else os.path.basename(filepath)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.media_player = QMediaPlayer(self, QMediaPlayer.VideoSurface)
        video_widget = QVideoWidget()
        layout.addWidget(video_widget)
        self.media_player.setVideoOutput(video_widget)
        controls_layout = QGridLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.color2};
                border: 1px solid {theme.color12};
                padding: 5px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.color9};
            }}
            QPushButton:pressed {{
                background-color: {theme.color12};
            }}
            """)
        self.play_button.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_button, 0, 0)
        stop_button = QPushButton()
        stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.color2};
                border: 1px solid {theme.color12};
                padding: 5px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.color9};
            }}
            QPushButton:pressed {{
                background-color: {theme.color12};
            }}
            """)
        stop_button.clicked.connect(self.stop_media)
        controls_layout.addWidget(stop_button, 0, 1)
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setStyleSheet(f"background-color: {theme.color6};")
        self.progress_slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.progress_slider, 0, 2)
        self.duration_label = QLabel("00:00 / 00:00")
        self.duration_label.setStyleSheet(
            f"QLabel {{ color: {theme.color27}; background-color: {theme.color6}; }}"
        )
        controls_layout.addWidget(self.duration_label, 0, 3)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet(f"background-color: {theme.color6};")
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
        controls_layout.addWidget(self.volume_slider, 0, 4)
        layout.addLayout(controls_layout)
        self.media_player.stateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.filepath)))
        self.media_player.play()

    def handle_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.media_player.setPosition(0)
            self.media_player.play()

    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_media(self):
        self.media_player.stop()

    def set_position(self, position):
        self.media_player.setPosition(position)

    def update_position(self, position):
        self.progress_slider.setValue(position)
        self.update_duration_label(position, self.media_player.duration())

    def update_duration(self, duration):
        self.progress_slider.setRange(0, duration)
        self.update_duration_label(self.media_player.position(), duration)

    def update_duration_label(self, position, duration):
        pos_seconds = position // 1000
        dur_seconds = duration // 1000
        pos_str = f"{pos_seconds // 60:02}:{pos_seconds % 60:02}"
        dur_str = f"{dur_seconds // 60:02}:{dur_seconds % 60:02}"
        self.duration_label.setText(f"{pos_str} / {dur_str}")

    def update_play_button_icon(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def closeEvent(self, event):
        self.media_player.stop()
        super().closeEvent(event)


class AudioViewer(QWidget):
    def __init__(self, filepath):
        super().__init__()
        self.is_modified = None
        self.filepath = os.path.abspath(filepath)
        self.tabname = (
            os.path.splitext(os.path.basename(filepath))[0][:27] + "..."
            if len(os.path.splitext(os.path.basename(filepath))[0]) > 26
            else os.path.basename(filepath)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)
        self.media_player = QMediaPlayer()
        filename_label = QLabel(os.path.basename(self.filepath))
        filename_label.setAlignment(Qt.AlignCenter)
        filename_label.setFont(QFont("Arial", 12))
        filename_label.setStyleSheet(f"QLabel {{ color: {theme.color27}; }}")
        layout.addWidget(filename_label)
        controls_layout = QGridLayout()
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.play_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.color2};
                border: 1px solid {theme.color12};
                padding: 5px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.color9};
            }}
            QPushButton:pressed {{
                background-color: {theme.color12};
            }}
            """)
        controls_layout.addWidget(self.play_button, 0, 0)
        stop_button = QPushButton()
        stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.color2};
                border: 1px solid {theme.color12};
                padding: 5px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.color9};
            }}
            QPushButton:pressed {{
                background-color: {theme.color12};
            }}
            """)
        stop_button.clicked.connect(self.stop_media)
        controls_layout.addWidget(stop_button, 0, 1)
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setStyleSheet(f"background-color: {theme.color6};")
        self.progress_slider.sliderMoved.connect(self.set_position)
        controls_layout.addWidget(self.progress_slider, 0, 2)
        self.duration_label = QLabel("00:00 / 00:00")
        self.duration_label.setStyleSheet(
            f"QLabel {{ color: {theme.color27}; background-color: {theme.color6}; }}"
        )
        controls_layout.addWidget(self.duration_label, 0, 3)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet(f"background-color: {theme.color6};")
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
        controls_layout.addWidget(self.volume_slider, 0, 4)
        layout.addLayout(controls_layout)
        self.media_player.stateChanged.connect(self.update_play_button_icon)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.filepath)))
        self.media_player.play()

    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_media(self):
        self.media_player.stop()

    def set_position(self, position):
        self.media_player.setPosition(position)

    def update_position(self, position):
        self.progress_slider.setValue(position)
        self.update_duration_label(position, self.media_player.duration())

    def update_duration(self, duration):
        self.progress_slider.setRange(0, duration)
        self.update_duration_label(self.media_player.position(), duration)

    def update_duration_label(self, position, duration):
        pos_seconds = position // 1000
        dur_seconds = duration // 1000
        pos_str = f"{pos_seconds // 60:02}:{pos_seconds % 60:02}"
        dur_str = f"{dur_seconds // 60:02}:{dur_seconds % 60:02}"
        self.duration_label.setText(f"{pos_str} / {dur_str}")

    def update_play_button_icon(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def closeEvent(self, event):
        self.media_player.stop()
        super().closeEvent(event)
