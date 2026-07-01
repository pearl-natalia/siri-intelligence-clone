import json
import sys

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import agent
import memory
from model import add_assistant_message, add_user_message, get_history
from transcription.speech import speech
from transcription.transcribe import transcribe


GREEN = "#2F5D50"
LIGHT = "#EAF6F1"
TEXT = "#202124"
MUTED = "#5F6368"


def _settings() -> dict:
    with open("settings.json", "r") as f:
        return json.load(f)


class AssistantWorker(QObject):
    status = pyqtSignal(str)
    transcript = pyqtSignal(str)
    response = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def run(self):
        try:
            settings = _settings()

            self.status.emit("Listening")
            text = transcribe()
            if not text:
                self.failed.emit("I didn't catch that.")
                self.finished.emit(True)
                return

            self.transcript.emit(text)
            add_user_message(text)

            self.status.emit("Thinking")
            answer, done = agent.run(text, settings)
            add_assistant_message(answer)
            self.response.emit(answer)

            self.status.emit("Speaking")
            speech(answer)
            self.finished.emit(done)
        except Exception as exc:
            self.failed.emit(f"Sorry, something went wrong: {exc}")
            self.finished.emit(True)


class Pulse(QWidget):
    def __init__(self):
        super().__init__()
        self._radius = 18
        self._growing = True
        self._active = False
        self.setFixedSize(86, 86)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def _tick(self):
        if not self._active:
            return
        self._radius += 1 if self._growing else -1
        if self._radius >= 28:
            self._growing = False
        if self._radius <= 18:
            self._growing = True
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = self.rect().center()
        pulse_color = QColor(GREEN)
        pulse_color.setAlpha(45 if self._active else 18)
        painter.setBrush(pulse_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, self._radius + 18, self._radius + 18)

        core = QColor(GREEN)
        painter.setBrush(core)
        painter.drawEllipse(center, 18, 18)


class SwiftWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._thread = None
        self._worker = None
        self._waiting_for_followup = False
        self._drag_position = None

        self.setWindowTitle("Swift")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(500, 660)

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"""
            QFrame#card {{
                background: rgba(255, 255, 255, 245);
                border: 1px solid #D7DFDC;
                border-radius: 28px;
            }}
            QLabel {{
                color: {TEXT};
            }}
            QPushButton {{
                background: {GREEN};
                color: white;
                border: none;
                border-radius: 32px;
                font-size: 24px;
                font-weight: 600;
            }}
            QPushButton:disabled {{
                background: #A8B9B2;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 12)
        card.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)

        self.title = QLabel("Swift")
        self.title.setFont(QFont("Avenir", 22, QFont.Bold))
        self.title.setStyleSheet(f"color: {GREEN};")
        self.title.setAlignment(Qt.AlignCenter)

        self.status = QLabel("Ready")
        self.status.setFont(QFont("Avenir", 13, QFont.Bold))
        self.status.setStyleSheet(f"color: {MUTED};")
        self.status.setAlignment(Qt.AlignCenter)

        self.messages = QWidget()
        self.messages_layout = QVBoxLayout(self.messages)
        self.messages_layout.setContentsMargins(0, 8, 0, 8)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.messages)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(400)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.button = QPushButton("▶")
        self.button.setFixedSize(64, 64)
        self.button.clicked.connect(self.start_turn)

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet(
            "background: transparent; color: #5F6368; border: none; padding: 6px; font-size: 13px;"
        )
        self.close_button.clicked.connect(self.close)

        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.scroll, stretch=1)
        layout.addWidget(self.button, alignment=Qt.AlignCenter)
        layout.addWidget(self.close_button)
        self.add_message("swift", "Tap play and ask Swift something.")

    def start_turn(self):
        self.button.setEnabled(False)
        self.button.setText("…")
        if self._waiting_for_followup:
            self.status.setText("Listening for your answer")
        else:
            self.status.setText("Listening")

        self._thread = QThread()
        self._worker = AssistantWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.set_status)
        self._worker.transcript.connect(self.set_transcript)
        self._worker.response.connect(self.set_response)
        self._worker.failed.connect(self.set_error)
        self._worker.finished.connect(self.finish_turn)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._turn_stopped)
        self._thread.start()

    def set_status(self, status: str):
        self.status.setText(status)

    def set_transcript(self, text: str):
        self.add_message("user", text)

    def set_response(self, text: str):
        self.add_message("swift", text)

    def set_error(self, text: str):
        self.status.setText("Error")
        self.add_message("swift", text)

    def finish_turn(self, done: bool):
        self._waiting_for_followup = not done
        if self._waiting_for_followup:
            self.status.setText("Listening for your answer")
            self.button.setText("…")
            self.button.setEnabled(False)
            QTimer.singleShot(900, self._start_followup_turn)
        else:
            self.status.setText("Ready")
            self.button.setText("▶")
            self.button.setEnabled(True)

    def _start_followup_turn(self):
        if not self._waiting_for_followup:
            return
        if self._thread:
            QTimer.singleShot(200, self._start_followup_turn)
        else:
            self.start_turn()

    def _turn_stopped(self):
        self._thread = None
        self._worker = None

    def add_message(self, sender: str, text: str):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Avenir", 15))
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        bubble.setMaximumWidth(330)

        if sender == "user":
            row.addStretch(1)
            bubble.setStyleSheet(
                f"background: {GREEN}; color: white; border-radius: 16px; padding: 12px 14px;"
            )
            row.addWidget(bubble, alignment=Qt.AlignRight)
        else:
            bubble.setStyleSheet(
                f"background: {LIGHT}; color: {TEXT}; border-radius: 16px; padding: 12px 14px;"
            )
            row.addWidget(bubble, alignment=Qt.AlignLeft)
            row.addStretch(1)

        insert_at = max(0, self.messages_layout.count() - 1)
        self.messages_layout.insertLayout(insert_at, row)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def closeEvent(self, event):
        memory.save_session(get_history())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_position and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_position)
            event.accept()


def main():
    app = QApplication(sys.argv)
    window = SwiftWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
