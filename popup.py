import random
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt

class PopupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Example")
        self.setGeometry(100, 100, 300, 200)
        
        self.waveform_heights = [random.randint(-20, 20) for _ in range(100)]  # Initial random heights
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_waveform)
        self.timer.start(50)  # Update every 50 ms

    def update_waveform(self):
        # Gradually change the heights of the waveform bars
        for i in range(len(self.waveform_heights)):
            change = random.choice([-1, 0, 1])  # Change the height slightly (up, down, or no change)
            self.waveform_heights[i] += change
            # Clamp the height to keep it within a reasonable range
            self.waveform_heights[i] = max(min(self.waveform_heights[i], 20), -20)
        
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.draw_waveform(painter)

    def draw_waveform(self, painter):
        waveform_width = self.width() * 0.8  # Width of the waveform
        waveform_height = 40  # Height of the waveform
        y_offset = int(self.height() / 2 - waveform_height / 2)  # Center the waveform vertically

        # Set the pen for drawing the waveform
        pen = QPen(Qt.white)
        pen.setWidth(2)
        painter.setPen(pen)

        # Number of waveform "bars"
        num_bars = len(self.waveform_heights)
        x_step = waveform_width / num_bars

        # Draw the waveform bars with varying heights
        for i in range(num_bars):
            x = int(i * x_step)
            height = self.waveform_heights[i]
            y = int(y_offset + height)
            
            # Draw a vertical line (bar), ensuring all coordinates are integers
            painter.drawLine(x, y_offset, x, y)
