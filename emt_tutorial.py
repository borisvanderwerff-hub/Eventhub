"""De rondleiding: een doorzichtige laag over het venster die stap voor stap een
onderdeel uitlicht. De stappen zelf komen uit het hoofdvenster.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class TutorialOverlay(QWidget):
    """Interactieve rondleiding die het besproken onderdeel in EventHub uitlicht."""

    def __init__(self, host: QWidget, steps: list[dict], finished_callback):
        super().__init__(host)
        self.host = host
        self.steps = steps
        self.finished_callback = finished_callback
        self.step_index = 0
        self._closing = False
        self._last_target_geometry = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        dark_mode = bool(getattr(host, "dark_mode_enabled", False))
        card_background = "#171b24" if dark_mode else "#ffffff"
        card_text = "#f3f6fb" if dark_mode else "#172235"
        card_muted = "#b7c1d0" if dark_mode else "#637187"
        secondary_background = "#252c38" if dark_mode else "#eef3f9"
        secondary_border = "#4b586b" if dark_mode else "#d8e0eb"

        self.card = QFrame(self)
        self.card.setObjectName("tutorialCard")
        self.card.setStyleSheet(
            f"QFrame#tutorialCard {{ background: {card_background}; border: 2px solid #91e8ba; border-radius: 12px; }}"
            f"QFrame#tutorialCard QLabel {{ background: transparent; color: {card_text}; }}"
            f"QLabel#tutorialCounter {{ color: {card_muted}; font-size: 9pt; }}"
            "QLabel#tutorialTitle { color: #91e8ba; font-size: 16pt; font-weight: 700; }"
            f"QPushButton#tutorialSecondary {{ background: {secondary_background}; color: {card_text}; "
            f"border: 1px solid {secondary_border}; border-radius: 7px; padding: 8px 12px; }}"
            "QPushButton#tutorialPrimary { background: #6c2cff; color: #ffffff; border: 1px solid #6c2cff; "
            "border-radius: 7px; padding: 8px 12px; font-weight: 700; }"
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 17, 20, 17)
        card_layout.setSpacing(9)
        self.counter = QLabel()
        self.counter.setObjectName("tutorialCounter")
        self.title = QLabel()
        self.title.setObjectName("tutorialTitle")
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        card_layout.addWidget(self.counter)
        card_layout.addWidget(self.title)
        card_layout.addWidget(self.body)

        actions = QHBoxLayout()
        self.previous_button = QPushButton("Vorige")
        self.previous_button.setObjectName("tutorialSecondary")
        self.previous_button.clicked.connect(self.previous_step)
        skip_button = QPushButton("Rondleiding sluiten")
        skip_button.setObjectName("tutorialSecondary")
        skip_button.clicked.connect(lambda: self.finish(False))
        self.next_button = QPushButton("Volgende")
        self.next_button.setObjectName("tutorialPrimary")
        self.next_button.clicked.connect(self.next_step)
        actions.addWidget(self.previous_button)
        actions.addWidget(skip_button)
        actions.addStretch()
        actions.addWidget(self.next_button)
        card_layout.addLayout(actions)

        self.host.installEventFilter(self)
        self.tracking_timer = QTimer(self)
        self.tracking_timer.setInterval(80)
        self.tracking_timer.timeout.connect(self._track_target)
        self.tracking_timer.start()
        self.setGeometry(self.host.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self.activate_step(0)

    def eventFilter(self, watched, event):
        if watched is self.host and event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.LayoutRequest):
            self.setGeometry(self.host.rect())
            self._schedule_reposition()
        return super().eventFilter(watched, event)

    def _resolve_target(self):
        if not self.steps:
            return None, None
        target_factory = self.steps[self.step_index].get("target")
        try:
            resolved = target_factory() if callable(target_factory) else target_factory
        except (AttributeError, RuntimeError, TypeError, KeyError):
            # Een rondleidingstarget mag de applicatie nooit laten crashen.
            # Als een UI-element in een latere versie is verplaatst of verwijderd,
            # toont de stap gewoon zonder spotlight.
            return None, None
        if isinstance(resolved, tuple) and len(resolved) == 2:
            target, local_rect = resolved
        else:
            target, local_rect = resolved, None
        if not isinstance(target, QWidget):
            return None, None
        return target, local_rect if isinstance(local_rect, QRect) else target.rect()

    def _target_rect(self):
        target, local_rect = self._resolve_target()
        if not isinstance(target, QWidget) or not target.isVisible():
            return None
        try:
            # Screen coordinates avoid rounding/offset errors between a
            # QMainWindow, its central widget, stacked pages and scroll areas.
            top_left = self.mapFromGlobal(target.mapToGlobal(local_rect.topLeft()))
        except RuntimeError:
            return None
        rect = QRect(top_left, local_rect.size()).adjusted(-7, -7, 7, 7)
        # Clip against every visible parent. This matters especially inside
        # QScrollArea viewports: without it the spotlight followed the widget's
        # theoretical position instead of the pixels actually on screen.
        ancestor = target.parentWidget()
        while ancestor is not None and ancestor is not self.host:
            if not ancestor.isVisible():
                return None
            try:
                ancestor_top_left = self.mapFromGlobal(ancestor.mapToGlobal(QPoint(0, 0)))
                ancestor_rect = ancestor.rect().translated(ancestor_top_left)
                rect = rect.intersected(ancestor_rect)
            except RuntimeError:
                return None
            ancestor = ancestor.parentWidget()
        return rect.intersected(self.rect().adjusted(8, 8, -8, -8))

    def _target_widget(self):
        target, _local_rect = self._resolve_target()
        return target

    def _ensure_target_visible(self):
        target = self._target_widget()
        if target is None:
            return
        ancestor = target.parentWidget()
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                try:
                    ancestor.ensureWidgetVisible(target, 24, 24)
                except RuntimeError:
                    pass
                break
            ancestor = ancestor.parentWidget()

    def _schedule_reposition(self):
        for delay in (0, 60, 180):
            QTimer.singleShot(delay, self._stabilize_target)

    def _stabilize_target(self):
        if self._closing:
            return
        self._ensure_target_visible()
        self._track_target()

    def _track_target(self):
        if self._closing or not self.isVisible():
            return
        if self.geometry() != self.host.rect():
            self.setGeometry(self.host.rect())
        rect = self._target_rect()
        geometry = (rect.x(), rect.y(), rect.width(), rect.height()) if rect and rect.isValid() else None
        if geometry != self._last_target_geometry:
            self._last_target_geometry = geometry
            self._position_card()
        else:
            self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shade = QPainterPath()
        shade.addRect(QRectF(self.rect()))
        target_rect = self._target_rect()
        if target_rect and target_rect.isValid():
            opening = QPainterPath()
            opening.addRoundedRect(QRectF(target_rect), 9, 9)
            shade = shade.subtracted(opening)
        painter.fillPath(shade, QColor(20, 13, 25, 175))
        if target_rect and target_rect.isValid():
            painter.setPen(QPen(QColor("#91e8ba"), 4))
            painter.drawRoundedRect(QRectF(target_rect), 9, 9)

    def activate_step(self, index: int):
        if not self.steps:
            self.finish(False)
            return
        self.step_index = max(0, min(index, len(self.steps) - 1))
        step = self.steps[self.step_index]
        prepare = step.get("prepare")
        if callable(prepare):
            prepare()
        self._last_target_geometry = None
        self.counter.setText(f"Stap {self.step_index + 1} van {len(self.steps)}")
        self.title.setText(str(step.get("title", "Rondleiding")))
        self.body.setText(str(step.get("body", "")))
        self.previous_button.setEnabled(self.step_index > 0)
        self.next_button.setText("Rondleiding afronden" if self.step_index == len(self.steps) - 1 else "Volgende")
        self._ensure_target_visible()
        self._schedule_reposition()
        self.update()

    def _position_card(self):
        if self._closing:
            return
        width = min(480, max(360, self.width() - 70))
        self.card.setFixedWidth(width)
        self.card.adjustSize()
        card_width = self.card.width()
        card_height = self.card.height()
        target = self._target_rect()
        if target and target.isValid():
            x = max(18, min(self.width() - card_width - 18, target.center().x() - card_width // 2))
            if target.bottom() + 18 + card_height <= self.height() - 15:
                y = target.bottom() + 18
            elif target.top() - 18 - card_height >= 15:
                y = target.top() - 18 - card_height
            else:
                y = max(18, (self.height() - card_height) // 2)
        else:
            x = max(18, (self.width() - card_width) // 2)
            y = max(18, (self.height() - card_height) // 2)
        self.card.move(x, y)
        self.card.raise_()
        self.update()

    def next_step(self):
        if self.step_index >= len(self.steps) - 1:
            self.finish(True)
        else:
            self.activate_step(self.step_index + 1)

    def previous_step(self):
        if self.step_index > 0:
            self.activate_step(self.step_index - 1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish(False)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Right):
            self.next_step()
            return
        if event.key() == Qt.Key.Key_Left:
            self.previous_step()
            return
        super().keyPressEvent(event)

    def finish(self, completed: bool):
        if self._closing:
            return
        self._closing = True
        self.tracking_timer.stop()
        self.host.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.finished_callback(bool(completed))
