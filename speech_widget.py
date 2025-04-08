import sys
import queue
import threading
import vosk
import sounddevice as sd
import json
import pyperclip
from pynput import keyboard
import time
import numpy as np
import math
from PIL import Image, ImageDraw # Уберем позже, если не нужно
import winreg # Для работы с реестром Windows
import os # Для работы с путями
# --- Добавляем импорты для логирования ---
import logging
import tempfile
# --- < Добавляем импорты для логирования ---

# --- Настройка логирования --- >
# Лог будет писаться в %TEMP%\speech_widget_log.txt
log_file_path = os.path.join(tempfile.gettempdir(), "speech_widget_log.txt")
logging.basicConfig(level=logging.INFO,
                    filename=log_file_path,
                    filemode='a', # 'a' - добавлять в конец, 'w' - перезаписывать
                    format='%(asctime)s - %(levelname)s - %(message)s')
# --- < Настройка логирования ---

# --- Версия приложения --- >
__version__ = "1.0.0" # Задаем версию здесь
# --- < Версия приложения ---

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    try:
        # PyInstaller/Nuitka creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Not frozen, development mode
        # __file__ is the path to the current script
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

try:
    import win32gui, win32con, win32api, win32ui, ctypes
    from ctypes import wintypes
except ImportError:
    print("ОШИБКА: Не найдена библиотека pywin32.")
    print("Установите ее: pip install pywin32")
    # --- Используем logging перед выходом --- >
    logging.critical("ОШИБКА: Не найдена библиотека pywin32. Установите ее: pip install pywin32")
    # --- < Используем logging перед выходом ---
    sys.exit(1)

# Импорты PySide6
from PySide6.QtWidgets import (QApplication, QWidget, QSystemTrayIcon, QMenu,
                             QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox,
                             QKeySequenceEdit, QStyle, QCheckBox)
from PySide6.QtGui import (QPainter, QColor, QBrush, QPen, QScreen, QPaintEvent,
                         QMouseEvent, QKeyEvent, QIcon, QAction, QKeySequence)
from PySide6.QtCore import (Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve,
                          QPoint, Signal, Slot, QObject, Property, QEvent, QSettings)


# --- Конфигурация (переносим, цвета теперь кортежи RGBA 0-255) ---
MODEL_PATH = resource_path("model")
DEVICE = None
SAMPLE_RATE = 16000
BLOCK_SIZE = 2048
# SHORTCUT_KEYS = {keyboard.Key.ctrl_l, keyboard.Key.space} # Убираем хардкод

# Виджет - Базовые размеры и множитель
IDLE_WIDTH = 35
IDLE_HEIGHT = 8
IDLE_COLOR = (64, 64, 64, 255) # Темно-серый
ACTIVE_SCALE_FACTOR = 2.0 # Во сколько раз увеличивается при активации/наведении

# ACTIVE_WIDTH = 160 # Убираем
# ACTIVE_HEIGHT = 45 # Убираем
ACTIVE_COLOR = (0, 0, 0, 255) # Черный 

# Анимация виджета
ANIMATION_DURATION_MS = 150
ANIMATION_STEPS = 15 # Не используется напрямую с QPropertyAnimation

# Столбики (Бары)
NUM_BARS = 15
BAR_MIN_HEIGHT = 2
BAR_MAX_HEIGHT_FACTOR = 0.8
BAR_WIDTH_FACTOR = 0.6
BAR_IDLE_COLOR = (160, 160, 160, 255) # Серый
BAR_ACTIVE_COLOR = (255, 40, 40, 255) # Красный
ANIMATION_THRESHOLD = 150
MAX_RMS = 3000
BAR_HEIGHT_SMOOTHING = 0.6
CENTER_FOCUS_FACTOR = 2.5

# --- Глобальные переменные и объекты ---
q_vosk = queue.Queue()            # Очередь для данных Vosk
audio_level_queue = queue.Queue() # Очередь для уровня звука
keyboard_controller = keyboard.Controller() # Для вставки Ctrl+V
vosk_thread = None                # Поток для Vosk
vosk_active = threading.Event()   # Флаг для управления потоком Vosk
recognizer = None                 # Объект Vosk
model = None                      # Модель Vosk
APP_REGISTRY_KEY_NAME = "SpeechWidgetApp" # Уникальное имя для ключа в реестре Run

# --- Класс окна настроек ---
class SettingsDialog(QDialog):
    hotkey_changed_signal = Signal()
    startup_setting_changed_signal = Signal(bool) # Сигнал об изменении настройки автозапуска (передаем новое состояние)

    def __init__(self, parent=None):
        super().__init__(parent)
        # --- Используем __version__ в заголовке --- >
        self.setWindowTitle(f"Настройки Speech Widget (v.{__version__})")
        # --- < Используем __version__ в заголовке ---
        # --- Добавляем иконку окна --- >
        icon_path = resource_path("assets/icon.svg")
        dialog_icon = QIcon(icon_path)
        if not dialog_icon.isNull():
            self.setWindowIcon(dialog_icon)
        else:
            # print(f"Warning: Could not load settings dialog icon from '{icon_path}'.") # Заменяем print на logging
            logging.warning(f"Could not load settings dialog icon from '{icon_path}'.")
        # --- < Добавляем иконку окна ---
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # --- Горячая клавиша ---
        layout.addWidget(QLabel("Горячая клавиша активации:"))
        self.key_sequence_edit = QKeySequenceEdit(self)
        layout.addWidget(self.key_sequence_edit)

        # --- Галочка автозапуска ---
        self.startup_checkbox = QCheckBox("Запускать при старте Windows", self)
        layout.addWidget(self.startup_checkbox)

        # --- Кнопки ---
        button_layout = QVBoxLayout()
        self.save_button = QPushButton("Сохранить", self)
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Отмена", self)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.load_settings()

    def load_settings(self):
        settings = QSettings()
        # Горячая клавиша
        hotkey_str = settings.value("hotkey", "Ctrl+Space")
        self.key_sequence_edit.setKeySequence(QKeySequence(hotkey_str))
        # Автозапуск (значение по умолчанию False)
        # Используем bool() для преобразования из строки/int, если сохранен некорректно
        startup_enabled = settings.value("startup_enabled", False, type=bool)
        self.startup_checkbox.setChecked(startup_enabled)

    def save_settings(self):
        settings = QSettings()
        # Горячая клавиша
        new_hotkey = self.key_sequence_edit.keySequence()
        old_hotkey_str = settings.value("hotkey", "Ctrl+Space")
        if new_hotkey.toString() != old_hotkey_str:
            settings.setValue("hotkey", new_hotkey.toString())
            # print(f"Settings saved. New hotkey: {new_hotkey.toString()}") # Закомментировано
            logging.info(f"Settings saved. New hotkey: {new_hotkey.toString()}")
            self.hotkey_changed_signal.emit()

        # Автозапуск
        new_startup_state = self.startup_checkbox.isChecked()
        old_startup_state = settings.value("startup_enabled", False, type=bool)
        if new_startup_state != old_startup_state:
            settings.setValue("startup_enabled", new_startup_state)
            # print(f"Settings saved. Startup enabled: {new_startup_state}") # Закомментировано
            logging.info(f"Settings saved. Startup enabled: {new_startup_state}")
            self.startup_setting_changed_signal.emit(new_startup_state) # Посылаем сигнал

        self.accept()


# --- Worker для Pynput ---
class KeyboardListenerWorker(QObject):
    activate_signal = Signal()
    deactivate_signal = Signal()

    def __init__(self):
        super().__init__()
        self._listener = None
        self._target_key = None         # Основная целевая клавиша pynput
        self._required_modifiers = set() # Набор СТРОК: {'ctrl', 'alt', 'shift', 'cmd'}
        self._pressed_modifiers = set()  # Набор СТРОК активных модификаторов
        self._main_key_pressed = False   # Нажата ли основная клавиша
        self._hotkey_active_state = False # Активна ли комбинация (для деактивации)
        self._active = True
        self.update_hotkey()

    @Slot()
    def update_hotkey(self):
        self._target_key, self._required_modifiers = self._load_and_parse_hotkey()
        # print(f"Hotkey updated. Target Key: {repr(self._target_key)}, Required Mods: {self._required_modifiers}") # Закомментировано
        self._pressed_modifiers.clear()
        self._main_key_pressed = False
        self._hotkey_active_state = False

    def _load_and_parse_hotkey(self):
        settings = QSettings()
        hotkey_str = settings.value("hotkey", "Ctrl+Space")
        sequence = QKeySequence(hotkey_str)
        # print(f"--- Parsing hotkey string: '{hotkey_str}' ---") # Закомментировано

        required_mods = set()
        target_k = None

        if not sequence.isEmpty():
            key_combination = sequence[0]
            qt_mods = key_combination.keyboardModifiers()
            qt_key = key_combination.key()
            # print(f"  Qt Full Sequence String: {sequence.toString()}") # Закомментировано
            # print(f"  Qt Mods: {qt_mods}, Qt Key: {qt_key}") # Закомментировано

            # --- Маппинг модификаторов Qt -> Строки ---
            if qt_mods & Qt.ControlModifier: required_mods.add('ctrl')#; print("  Required Mod: ctrl")
            if qt_mods & Qt.ShiftModifier: required_mods.add('shift')#; print("  Required Mod: shift")
            if qt_mods & Qt.AltModifier: required_mods.add('alt')#; print("  Required Mod: alt")
            if qt_mods & Qt.MetaModifier: required_mods.add('cmd')#; print("  Required Mod: cmd")

            # --- Маппинг основной клавиши Qt -> Pynput ---
            if qt_key == Qt.Key_Space:
                target_k = keyboard.Key.space
                # print(f"  Mapped Key: {repr(target_k)}") # Закомментировано
            else:
                 vk = self._qt_key_to_vk(qt_key)
                 if vk:
                      # print(f"  Mapped VK: {vk:#04x}") # Закомментировано
                      if Qt.Key_0 <= qt_key <= Qt.Key_9 or Qt.Key_A <= qt_key <= Qt.Key_Z:
                           target_k = keyboard.KeyCode(vk=vk)
                           # print(f"  Mapped Key (VK): {repr(target_k)}") # Закомментировано
                      else:
                           pynput_key_name = None; key_obj = None
                           try:
                              for attr in dir(keyboard.Key):
                                  key_obj = getattr(keyboard.Key, attr)
                                  if isinstance(key_obj, keyboard.Key) and hasattr(key_obj, 'value') and hasattr(key_obj.value, 'vk') and key_obj.value.vk == vk:
                                      pynput_key_name = attr; break
                           except AttributeError: pass
                           if pynput_key_name:
                                target_k = getattr(keyboard.Key, pynput_key_name)
                                # print(f"  Mapped Key (Special Name): {repr(target_k)}") # Закомментировано
                           else:
                                target_k = keyboard.KeyCode(vk=vk)
                                # print(f"  Mapped Key (VK Fallback): {repr(target_k)}") # Закомментировано
                 else:
                     try:
                         seq_str = sequence.toString(QKeySequence.NativeText)
                         char = seq_str.split('+')[-1].strip().lower()
                         if len(char) == 1:
                              target_k = keyboard.KeyCode.from_char(char)
                              # print(f"  Mapped Key (Char): {repr(target_k)}") # Закомментировано
                     except Exception as e:
                          # print(f"   Error parsing char from sequence string '{seq_str}': {e}") # Закомментировано
                          pass

        if not target_k:
             # print("Warning: No target key mapped for hotkey sequence.") # Закомментировано
             required_mods.clear()

        # print(f"  -> Parsed: Target Key: {repr(target_k)}, Required Mods: {required_mods}") # Закомментировано
        return target_k, required_mods

    def _qt_key_to_vk(self, qt_key):
        """Преобразует Qt.Key в Virtual Key Code (VK). Неполный маппинг."""
        # Источник: https://doc.qt.io/qt-6/qt.html#Key-enum и Windows VK codes
        # Это неполный маппинг, нужно добавлять по мере необходимости
        mapping = {
            Qt.Key_Space: 0x20,
            Qt.Key_Return: 0x0D, Qt.Key_Enter: 0x0D,
            Qt.Key_Escape: 0x1B,
            Qt.Key_Tab: 0x09,
            Qt.Key_Backspace: 0x08,
            Qt.Key_Delete: 0x2E,
            Qt.Key_Insert: 0x2D,
            Qt.Key_Home: 0x24,
            Qt.Key_End: 0x23,
            Qt.Key_PageUp: 0x21,
            Qt.Key_PageDown: 0x22,
            Qt.Key_Left: 0x25, Qt.Key_Right: 0x27, Qt.Key_Up: 0x26, Qt.Key_Down: 0x28,
            # F-клавиши
            **{Qt.Key_F1 + i: 0x70 + i for i in range(12)},
            # Цифры
            **{getattr(Qt, f"Key_{i}"): ord(str(i)) for i in range(10)},
            # Латинские буквы
            **{getattr(Qt, f"Key_{chr(c)}"): c for c in range(ord('A'), ord('Z') + 1)},
        }
        return mapping.get(qt_key)

    def run(self):
        # print("Keyboard listener thread started.") # Закомментировано
        try:
            with keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as self._listener:
                self._listener.join()
        except Exception as e: # print(f"Error in keyboard listener: {e}") # Заменяем print на logging
            logging.error(f"Error in keyboard listener: {e}", exc_info=True)
        finally: # print("Keyboard listener thread finished.") # Заменяем print на logging
            logging.info("Keyboard listener thread finished.")

    def _get_modifier_type(self, key):
        """Определяет тип модификатора по объекту pynput.Key."""
        if isinstance(key, keyboard.Key):
            name = key.name.lower()
            if 'ctrl' in name: return 'ctrl'
            if 'alt' in name: return 'alt'
            if 'shift' in name: return 'shift'
            if 'cmd' in name or 'win' in name: return 'cmd'
        return None

    def _check_activation(self):
        """Проверяет, выполнены ли условия активации."""
        all_required_mods_pressed = self._required_modifiers.issubset(self._pressed_modifiers)
        # print(f"  Check Activation: TargetKey={repr(self._target_key)} Pressed={self._main_key_pressed} | RequiredMods={self._required_modifiers} PressedMods={self._pressed_modifiers} -> AllModsOK={all_required_mods_pressed}") # Закомментировано

        if self._main_key_pressed and all_required_mods_pressed:
            if not self._hotkey_active_state:
                 # print("  Activation condition MET.") # Закомментировано
                 self._hotkey_active_state = True
                 self.activate_signal.emit()
        elif self._hotkey_active_state:
             # print("  Activation condition NO LONGER MET (in check).") # Закомментировано
             self._hotkey_active_state = False
             self.deactivate_signal.emit()

    def _on_press(self, key):
        if not self._active or not self._target_key: return
        # print(f"Press Event: Key={repr(key)}") # Закомментировано

        mod_type = self._get_modifier_type(key)
        target_key_pressed = False

        if isinstance(self._target_key, keyboard.KeyCode) and isinstance(key, keyboard.KeyCode):
             if key.vk == self._target_key.vk: target_key_pressed = True
        elif isinstance(self._target_key, keyboard.Key) and isinstance(key, keyboard.Key):
             if key == self._target_key: target_key_pressed = True

        if mod_type:
            # print(f"  -> Modifier '{mod_type}' pressed.") # Закомментировано
            self._pressed_modifiers.add(mod_type)
        elif target_key_pressed:
            # print(f"  -> Target key pressed.") # Закомментировано
            self._main_key_pressed = True
        # else:
            # print(f"  -> Other/Mismatch key pressed. Target type: {type(self._target_key)}, Key type: {type(key)}") # Закомментировано

        self._check_activation()

    def _on_release(self, key):
         if not self._active or not self._target_key: return
         # print(f"Release Event: Key={repr(key)}") # Закомментировано

         mod_type = self._get_modifier_type(key)
         # print(f"  Before release check: _main_key_pressed = {self._main_key_pressed}") # Закомментировано
         key_was_target = False
         if isinstance(self._target_key, keyboard.KeyCode) and isinstance(key, keyboard.KeyCode):
             if key.vk == self._target_key.vk: key_was_target = True
         elif isinstance(self._target_key, keyboard.Key) and isinstance(key, keyboard.Key):
             if key == self._target_key: key_was_target = True

         if mod_type:
             # print(f"  -> Modifier '{mod_type}' released.") # Закомментировано
             self._pressed_modifiers.discard(mod_type)
         if key_was_target:
             # print(f"  -> Target key released.") # Закомментировано
             self._main_key_pressed = False
         # print(f"  After release check: _main_key_pressed = {self._main_key_pressed}, PressedMods = {self._pressed_modifiers}") # Закомментировано

         if self._hotkey_active_state and (key_was_target or (mod_type and mod_type in self._required_modifiers)):
             # print(f"  Deactivation condition MET (key released: {repr(key)})") # Закомментировано
             self._hotkey_active_state = False
             self.deactivate_signal.emit()

    def stop(self):
        # print("Stopping keyboard listener...") # Закомментировано
        self._active = False
        if self._listener: self._listener.stop()


# --- Основной виджет (QWidget) ---
class SpeechWidget(QWidget):
    # Сигнал для обновления уровня баров из таймера
    _bars_need_update = Signal(float)

    def __init__(self):
        super().__init__()
        # print("Widget __init__ started") # Закомментировано
        self.settings_dialog = None
        self.tray_icon = None
        self.setupUI()
        self.setupState()
        self.setupAnimation()
        self.setupAudioProcessing()
        self.setupTrayIcon()
        self._load_initial_position() # <-- ЗАГРУЖАЕМ ПОЗИЦИЮ
        # print("Widget __init__ finished") # Закомментировано

    def setupUI(self):
        # Настройка окна: без рамки, поверх всех, прозрачный фон
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_Hover, True) # Включаем события hover
        # Установка геометрии в начальное (idle) состояние
        self.setGeometry(100, 100, IDLE_WIDTH, IDLE_HEIGHT) # Устанавливаем начальный размер/позицию

    def setupState(self):
        # Состояние виджета
        self._state = 'idle' # 'idle' или 'active'
        self._is_hovering = False # Флаг наведения мыши
        self._bar_heights = [BAR_MIN_HEIGHT] * NUM_BARS
        self._current_level = 0.0
        self._drag_pos = None
         # Сохраняем геометрию состояний как QRectF для анимации
        self._target_geo = QRectF(self.geometry()) # Целевая геометрия для анимации

    def setupAnimation(self):
        # Анимация геометрии (размера и позиции)
        self.geometry_animation = QPropertyAnimation(self, b"geometry")
        self.geometry_animation.setDuration(ANIMATION_DURATION_MS)
        self.geometry_animation.setEasingCurve(QEasingCurve.OutCubic)
        # Добавим анимацию для цвета фона (через пользовательское свойство)
        self._current_bg_color = QColor(*IDLE_COLOR)
        self.color_animation = QPropertyAnimation(self, b"_animated_bg_color")
        self.color_animation.setDuration(ANIMATION_DURATION_MS)
        self.color_animation.setEasingCurve(QEasingCurve.OutCubic) # Можно другую кривую
        # --- ОТЛАДКА: Соединяем сигнал stateChanged ---
        # self.geometry_animation.stateChanged.connect(self._on_geom_anim_state_changed)
        # self.color_animation.stateChanged.connect(self._on_color_anim_state_changed)

    def setupAudioProcessing(self):
        # Таймер для проверки очереди аудиоуровней
        self.bar_update_timer = QTimer(self)
        self.bar_update_timer.timeout.connect(self._check_audio_queue)
        self.bar_update_timer.start(30) # ~33 FPS для обновления баров
        # Подключение сигнала к слоту обновления баров
        self._bars_need_update.connect(self._update_bar_heights_and_repaint)

    # --- ОТЛАДКА: Слоты для отслеживания состояния анимации ---
    @Slot(QPropertyAnimation.State, QPropertyAnimation.State)
    def _on_geom_anim_state_changed(self, newState, oldState):
        print(f"Geometry Animation State: {oldState} -> {newState}")

    @Slot(QPropertyAnimation.State, QPropertyAnimation.State)
    def _on_color_anim_state_changed(self, newState, oldState):
        print(f"Color Animation State: {oldState} -> {newState}")

    # --- Управление состоянием ---
    @Slot()
    def activate_widget(self):
        if self._state == 'idle':
            print("GUI: State -> Active (Recognition ON)")
            self._state = 'active'
            self._update_visual_state() # Обновляем визуал (если нужно)
            start_recognition_thread()

    @Slot()
    def deactivate_widget(self):
        if self._state == 'active':
            print("GUI: State -> Idle (Recognition OFF)")
            self._state = 'idle'
            self._update_visual_state() # Обновляем визуал (если нужно)
            stop_recognition_thread()

    # --- Обновление визуального состояния (анимация) ---
    def _update_visual_state(self):
        is_visually_active = self._state == 'active' or self._is_hovering
        target_width = IDLE_WIDTH * ACTIVE_SCALE_FACTOR if is_visually_active else IDLE_WIDTH
        target_height = IDLE_HEIGHT * ACTIVE_SCALE_FACTOR if is_visually_active else IDLE_HEIGHT
        target_color = QColor(*(ACTIVE_COLOR if is_visually_active else IDLE_COLOR))

        # Рассчитываем целевую геометрию с центровкой
        current_geo = QRectF(self.geometry())
        target_rect = QRectF(0, 0, target_width, target_height)
        # Центруем относительно текущего центра
        target_rect.moveCenter(current_geo.center())
        target_geometry = target_rect.toRect() # Конечная цель

        # Запускаем анимацию, только если цель отличается от текущей (или от конечной цели текущей анимации)
        is_animating_geom = self.geometry_animation.state() == QPropertyAnimation.Running
        current_target_geom = self.geometry_animation.endValue() if is_animating_geom else self.geometry()

        if target_geometry != current_target_geom:
            # print(f"GUI: Animating geometry to {target_geometry}") # Заменяем print на logging.debug
            logging.debug(f"GUI: Animating geometry to {target_geometry}")
            self.geometry_animation.stop() # Останавливаем текущую, если есть
            self.geometry_animation.setStartValue(self.geometry()) # Начинаем с текущей
            self.geometry_animation.setEndValue(target_geometry)
            self.geometry_animation.start()

        is_animating_color = self.color_animation.state() == QPropertyAnimation.Running
        current_target_color = self.color_animation.endValue() if is_animating_color else self._current_bg_color

        if target_color != current_target_color:
            # print(f"GUI: Animating color to {target_color.getRgb()}") # Заменяем print на logging.debug
            logging.debug(f"GUI: Animating color to {target_color.getRgb()}")
            self.color_animation.stop()
            self.color_animation.setStartValue(self._current_bg_color)
            self.color_animation.setEndValue(target_color)
            self.color_animation.start()

        # Если переходим в неактивное состояние, обнуляем бары
        if not is_visually_active:
             self._bars_need_update.emit(0.0)

    # --- Пользовательское свойство для анимации цвета ---
    @Property(QColor, user=True) # user=True важно для анимации
    def _animated_bg_color(self):
        return self._current_bg_color

    @_animated_bg_color.setter
    def _animated_bg_color(self, color):
        self._current_bg_color = color
        self.update() # Перерисовываем при смене цвета

    # --- Обработка аудиоданных ---
    @Slot()
    def _check_audio_queue(self):
        level_to_use = 0.0 # Уровень, который будем использовать дальше
        level_read = None
        try:
            # Читаем все из очереди, запоминаем последнее значение
            while True:
                level_read = audio_level_queue.get_nowait()
        except queue.Empty:
            pass # Очередь пуста, level_read будет None или последним значением

        # --- Решаем, какой уровень использовать ---
        if level_read is not None:
            # Мы успешно прочитали новый уровень
            level_to_use = level_read
            # print(f"AudioQ Check: Read={level_read:.3f} | Prev Current={self._current_level:.3f} | State={self._state}") # Отладка
        else:
            # Очередь была пуста, используем предыдущее значение, если активны
            level_to_use = self._current_level if self._state == 'active' else 0.0
            # print(f"AudioQ Check: Queue empty, using current level={level_to_use:.3f} | State={self._state}") # Отладка

        # Оптимизация: сравниваем выбранный уровень с сохраненным
        delta = abs(level_to_use - self._current_level)
        # Пропускаем, только если активны, дельта мала, И уровень не нулевой (чтобы 0 для сброса проходил)
        if self._state == 'active' and delta < 0.01 and level_to_use != 0.0:
            # print(f"  Optimization Skip: level_to_use={level_to_use:.3f}, current={self._current_level:.3f}, delta={delta:.3f}") # Отладка
            return

        # print(f"  Optimization Passed: level={level_to_use:.3f}, current={self._current_level:.3f}, delta={delta:.3f}") # Отладка

        # Обновляем сохраненный уровень
        if abs(self._current_level - level_to_use) > 1e-5: # Обновляем если реально изменился
             # old_current_level = self._current_level # Отладка
             self._current_level = level_to_use
             # print(f"  Current level updated from {old_current_level:.3f} to {self._current_level:.3f}") # Отладка

        # Вызываем обновление баров с выбранным уровнем
        if self._state == 'active':
             # print(f"  --> Emitting level={level_to_use:.3f}") # Отладка
             self._bars_need_update.emit(level_to_use)
        elif any(h > BAR_MIN_HEIGHT for h in self._bar_heights): # Сброс в idle
             # print(f"  --> Idle state, bars need reset. Emitting 0.0") # Отладка
             self._bars_need_update.emit(0.0)

    @Slot(float)
    def _update_bar_heights_and_repaint(self, level):
        # print(f"Update Bars Slot: Received level={level:.3f}") # Отладка
        # Рассчитываем целевые высоты с учетом текущей высоты виджета
        current_height = self.height()
        if current_height < 1: return # Защита
        max_bar_h = current_height * BAR_MAX_HEIGHT_FACTOR
        center_index = (NUM_BARS - 1) / 2.0

        needs_repaint = False
        for i in range(NUM_BARS):
            dist_from_center = abs(i - center_index) / center_index if center_index > 0 else 0
            scale = math.exp(-(dist_from_center**2) * CENTER_FOCUS_FACTOR)
            target_h = BAR_MIN_HEIGHT + (max_bar_h - BAR_MIN_HEIGHT) * level * scale
            # Сглаживание
            current_h = self._bar_heights[i]
            new_h = current_h * BAR_HEIGHT_SMOOTHING + target_h * (1.0 - BAR_HEIGHT_SMOOTHING)
            # --- ОТЛАДКА --- >
            # if i == NUM_BARS // 2: # Печатаем для центрального бара
            #     print(f"  Center Bar (i={i}): level={level:.3f}, target_h={target_h:.2f}, current_h={current_h:.2f}, new_h={new_h:.2f}")
            # --- < ОТЛАДКА ---
            # Проверяем, изменилась ли высота значительно
            if abs(new_h - current_h) > 0.1:
                needs_repaint = True
            self._bar_heights[i] = new_h

        if needs_repaint or level == 0.0: # Перерисовываем если что-то изменилось или обнуляем
             # --- ОТЛАДКА --- >
             # print("  Needs repaint = True. Calling self.update()")
             # --- < ОТЛАДКА ---
             self.update()
        # else: # --- ОТЛАДКА --- >
            # print("  No significant change in bar heights. Repaint skipped.")
            # pass # --- < ОТЛАДКА ---

    # --- Отрисовка ---
    def paintEvent(self, event: QPaintEvent):
        # --- ОТЛАДКА ---
        # print(f"Paint event triggered. Geometry: {self.geometry()}")
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        painter.setPen(Qt.NoPen)

        # Фон (пилюля) - используем анимированный цвет
        painter.setBrush(QBrush(self._current_bg_color))
        rect = QRectF(self.rect()) # Прямоугольник текущей геометрии виджета
        radius = rect.height() / 2.0
        painter.drawRoundedRect(rect, radius, radius)

        # Бары (только если виджет достаточно широкий - т.е. в active состоянии или анимации к нему)
        if rect.width() > IDLE_WIDTH + 10:
             bar_color_active = QColor(*BAR_ACTIVE_COLOR)
             bar_color_idle = QColor(*BAR_IDLE_COLOR)
             total_bar_space = rect.width() * 0.8
             if NUM_BARS > 0:
                 bar_spacing = total_bar_space / NUM_BARS
                 bar_width = bar_spacing * BAR_WIDTH_FACTOR
                 start_x = rect.x() + (rect.width() - total_bar_space) / 2 + (bar_spacing - bar_width) / 2
                 center_y = rect.height() / 2.0 # Вертикальный центр
                 for i, h in enumerate(self._bar_heights):
                     bar_h = max(BAR_MIN_HEIGHT, h)
                     painter.setBrush(bar_color_active if bar_h > BAR_MIN_HEIGHT + 1 else bar_color_idle)
                     # Координаты относительно центра Y
                     y1 = center_y - bar_h / 2.0
                     y2 = center_y + bar_h / 2.0
                     bar_rect = QRectF(start_x + i * bar_spacing, y1, bar_width, bar_h) # x, y, width, height
                     painter.drawRect(bar_rect)

    # --- События мыши ---
    def enterEvent(self, event: QEvent):
        # print("Mouse Enter") # Отладка
        self._is_hovering = True
        self._update_visual_state()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        # print("Mouse Leave") # Отладка
        self._is_hovering = False
        self._update_visual_state()
        super().leaveEvent(event)

    # --- Перетаскивание ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Запоминаем смещение клика относительно левого верхнего угла окна
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        # Двигаем окно, только если зажата левая кнопка и есть сохраненная позиция
        if event.buttons() == Qt.LeftButton and self._drag_pos:
             # Новая позиция = глобальная позиция мыши - сохраненное смещение
             new_pos = event.globalPosition().toPoint() - self._drag_pos
             self.move(new_pos)
             event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self._drag_pos is not None: # Если был drag-and-drop
                # --- СОХРАНЯЕМ ПОЗИЦИЮ ---
                settings = QSettings()
                current_pos = self.pos()
                settings.setValue("window_pos_x", current_pos.x())
                settings.setValue("window_pos_y", current_pos.y())
                # print(f"Saved position: x={current_pos.x()}, y={current_pos.y()}") # Закомментировано
                # --------------------------
            self._drag_pos = None # Сбрасываем позицию в любом случае
            event.accept()

    # --- Центровка окна ---
    def _center_window(self):
        if self.screen():
            center_point = self.screen().availableGeometry().center() # Используем availableGeometry
            current_geo = self.geometry()
            current_geo.moveCenter(center_point)
            self.setGeometry(current_geo)
            # Обновляем базовые геометрии после центровки
            self._target_geo = QRectF(self.geometry())

    # --- Обработка нажатий клавиш в виджете (для закрытия) ---
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            # Скрываем окно вместо закрытия приложения
            self.setVisible(False)
            self.toggle_action.setText("Показать виджет")
            # QApplication.instance().quit() # Не выходим по Esc
        else:
            super().keyPressEvent(event) # Передаем другие нажатия дальше

    # --- Закрытие окна ---
    def closeEvent(self, event: QEvent):
        # При попытке закрыть окно (если бы оно имело рамку) - просто скрываем
        if self.tray_icon.isVisible():
            self.hide()
            self.toggle_action.setText("Показать виджет")
            event.ignore() # Игнорируем событие закрытия
        else:
            super().closeEvent(event) # Если трея нет, закрываем

    def setupTrayIcon(self):
        icon_path = resource_path("assets/icon.svg")
        icon = QIcon(icon_path) # Пробуем загрузить SVG

        # Проверяем, загрузилась ли иконка
        if icon.isNull():
             print(f"Warning: Failed to load icon from '{icon_path}'. Using fallback standard icon.")
             # Используем надежную стандартную иконку
             standard_icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOkButton) # Эта должна быть почти везде
             if standard_icon.isNull(): # На совсем крайний случай
                  print("ERROR: Failed to load even the standard fallback icon!")
                  icon = QIcon() # Создаем пустую иконку, чтобы избежать краха
             else:
                  icon = standard_icon
        else:
             print(f"Successfully loaded icon from '{icon_path}'")


        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Speech Widget")

        # Создаем меню
        menu = QMenu(self)

        # Изначально виджет виден, поэтому текст - "Скрыть"
        self.toggle_action = QAction("Скрыть виджет", self)
        self.toggle_action.triggered.connect(self.toggle_visibility)
        menu.addAction(self.toggle_action)

        # Действие Настройки
        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Действие Выход
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        # Реакция на клик по иконке (можно сделать показ/скрытие)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)


    @Slot()
    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
        self.toggle_action.setText("Скрыть виджет" if self.isVisible() else "Показать виджет")

    @Slot(QSystemTrayIcon.ActivationReason)
    def on_tray_icon_activated(self, reason):
        # Показываем/скрываем по двойному клику, например
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_visibility()

    @Slot()
    def show_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
            # Подключаем сигналы из настроек к нужным слотам
            self.settings_dialog.hotkey_changed_signal.connect(keyboard_listener_worker.update_hotkey)
            self.settings_dialog.startup_setting_changed_signal.connect(self.handle_startup_setting_change)
        self.settings_dialog.load_settings()
        self.settings_dialog.exec()

    # Слот для обработки изменения настройки автозапуска
    @Slot(bool)
    def handle_startup_setting_change(self, enabled):
        # --- Используем logging --- >
        logging.info(f"Handling startup setting change. Enabled: {enabled}")
        if is_frozen(): # Модифицируем реестр ТОЛЬКО если запущено из .exe
            exe_path = get_executable_path() # get_executable_path теперь тоже логирует
            logging.info(f"Handling startup change ({enabled}) for executable: {exe_path}")
            if not exe_path:
                logging.error("Could not determine executable path.")
                QMessageBox.warning(self, "Ошибка", "Не удалось определить путь к исполняемому файлу для добавления в автозагрузку.")
                return

            if enabled:
                success = add_to_startup(exe_path) # add_to_startup теперь тоже логирует
                if not success:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось добавить приложение в автозагрузку. Проверьте лог-файл: {log_file_path}")
            else:
                success = remove_from_startup() # remove_from_startup теперь тоже логирует
                if not success:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось удалить приложение из автозагрузки. Проверьте лог-файл: {log_file_path}")
        else:
            logging.warning("Running as script, registry modification skipped.")
            QMessageBox.information(self, "Информация",
                                    "Настройка автозапуска применится только для установленной версии приложения (запущенной из .exe файла).")
        # --- < Используем logging ---

    def _load_initial_position(self):
        """Загружает и применяет сохраненную позицию окна."""
        settings = QSettings()
        # Загружаем x и y, предоставляя None как маркер отсутствия значения
        saved_x = settings.value("window_pos_x", None)
        saved_y = settings.value("window_pos_y", None)

        if saved_x is not None and saved_y is not None:
            try:
                # Преобразуем в int и перемещаем окно
                pos_x = int(saved_x)
                pos_y = int(saved_y)
                # print(f"Loading saved position: x={pos_x}, y={pos_y}") # Закомментировано
                logging.info(f"Loading saved position: x={pos_x}, y={pos_y}")
                # Проверим, чтобы координаты были в пределах видимости экранов
                screen_geometry = QApplication.primaryScreen().availableGeometry() # Геометрия основного экрана
                # Простая проверка, можно улучшить для мультимониторных систем
                if screen_geometry.contains(pos_x, pos_y):
                     self.move(pos_x, pos_y)
                else:
                     # print("Saved position is outside screen bounds, centering instead.")
                     logging.warning("Saved position is outside screen bounds, centering instead.")
                     self._center_window() # Центрируем, если позиция некорректна
            except (ValueError, TypeError):
                # print("Error loading saved position, centering instead.")
                logging.error("Error loading saved position, centering instead.")
                self._center_window() # Центрируем при ошибке
        else:
            # print("No saved position found, centering window.") # Закомментировано
            logging.info("No saved position found, centering window.")
            self._center_window() # Центрируем, если настроек нет


# --- Функции управления потоком Vosk ---
def recognition_thread_func_pyside():
    global recognizer, model, vosk_active
    if not recognizer: return
    stream = None
    try:
        stream = sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, device=DEVICE,
                               dtype='int16', channels=1, callback=audio_callback_vosk) # Отдельный callback для vosk
        stream.start()
        recognizer.Reset()
        print("Vosk thread: Recognition started")
        while vosk_active.is_set():
            try: data = q_vosk.get(timeout=0.1)
            except queue.Empty: continue
            if recognizer.AcceptWaveform(data): pass
        print("Vosk thread: Recording stopped")
        stream.stop(); stream.close()
        final_result = json.loads(recognizer.FinalResult())
        recognized_text = final_result.get('text', '')
        print(f"Vosk thread: Result: '{recognized_text}'")
        if recognized_text:
            pyperclip.copy(recognized_text)
            time.sleep(0.3) # Даем время буферу обмена обновиться и окну получить фокус
            try:
                keyboard_controller.press(keyboard.Key.ctrl)
                # Используем VK код для 'V' вместо символа
                v_key_code = keyboard.KeyCode(vk=0x56)
                keyboard_controller.press(v_key_code)
                keyboard_controller.release(v_key_code)
                keyboard_controller.release(keyboard.Key.ctrl)
                print("Vosk thread: Pasted.")
            except Exception as paste_err: # print(f"Vosk thread: Paste error: {paste_err}") # Заменяем на logging
                logging.error(f"Vosk thread: Paste error: {paste_err}", exc_info=True)
    except sd.PortAudioError as pae: # print(f"Vosk thread: PortAudioError: {pae}") # Заменяем на logging
        logging.error(f"Vosk thread: PortAudioError: {pae}")
    except Exception as e: # print(f"Vosk thread: Error: {e}") # Заменяем на logging
        logging.error(f"Vosk thread: Error: {e}", exc_info=True)
    finally:
        if stream and stream.active: stream.stop(); stream.close()
        # Исправляем очистку очереди
        while not q_vosk.empty():
            try:
                q_vosk.get_nowait()
            except queue.Empty:
                break
        print("Vosk thread: Finished")

# Callback для аудио: один кладет в обе очереди
def audio_callback_vosk(indata, frames, time, status):
    if status: print(status, file=sys.stderr) # Ошибки аудио выводим
    data_bytes = bytes(indata)
    q_vosk.put(data_bytes) # Для распознавания

    # Анализ громкости для GUI (если активно)
    if vosk_active.is_set(): # Используем флаг vosk_active как индикатор активности
        try:
            audio_data = np.frombuffer(indata, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
            level = 0
            if rms > ANIMATION_THRESHOLD:
                level = min(1.0, (rms - ANIMATION_THRESHOLD) / (MAX_RMS - ANIMATION_THRESHOLD))
            audio_level_queue.put(level) # Для обновления баров
        except Exception as e: pass # Игнорируем ошибки анализа


def start_recognition_thread():
    global vosk_thread
    if vosk_thread is None or not vosk_thread.is_alive():
        vosk_active.set()
        # Исправляем очистку очереди
        while not q_vosk.empty():
            try:
                q_vosk.get_nowait()
            except queue.Empty:
                break
        # Исправляем очистку очереди
        while not audio_level_queue.empty():
            try:
                audio_level_queue.get_nowait()
            except queue.Empty:
                break
        vosk_thread = threading.Thread(target=recognition_thread_func_pyside, daemon=True)
        vosk_thread.start()

def stop_recognition_thread():
    vosk_active.clear() # Сигнал потоку Vosk на остановку


# --- Функции для работы с автозапуском ---
def is_frozen():
    """ Проверяет, запущено ли приложение как 'замороженное' .exe """
    # Для Nuitka one-file sys.frozen и sys._MEIPASS могут быть не установлены.
    # Надежный способ определить .exe - проверить sys.argv[0].
    return hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS') or sys.argv[0].lower().endswith('.exe')

def get_executable_path():
    """ Возвращает путь к исполняемому файлу (.exe) или скрипту (.py) """
    if is_frozen():
        # Для Nuitka one-file sys.executable указывает на временный python.exe,
        # а sys.argv[0] - на оригинальный .exe файл.
        path = os.path.abspath(sys.argv[0])
        logging.info(f"Running frozen. Determined executable path (from sys.argv[0]): {path}")
        return path
    else:
        # Если запущен как скрипт, возвращаем путь к скрипту
        path = os.path.abspath(sys.argv[0])
        logging.info(f"Running as script. Path: {path}")
        return path

def add_to_startup(executable_path):
    """ Добавляет приложение в автозагрузку Windows """
    # Путь к ключу реестра автозагрузки для текущего пользователя
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key_name = APP_REGISTRY_KEY_NAME # Имя нашего ключа

    # Путь к исполняемому файлу должен быть в кавычках, если содержит пробелы
    path_value = f'"{executable_path}"'
    # --- Логируем попытку --- >
    logging.info(f"Attempting to add to startup. Key: {key_path}\{key_name}, Value: {path_value}")
    # --- < Логируем попытку ---

    try:
        # Открываем ключ реестра с правами на запись
        # Используем HKEY_CURRENT_USER, не требует прав администратора
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        # Устанавливаем значение (имя ключа, значение - путь, тип - REG_SZ строка)
        winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, path_value)
        winreg.CloseKey(key)
        # print(f"Successfully added to startup: {path_value}") # Заменяем на logging
        logging.info(f"Successfully added to startup.")
        return True
    except OSError as e:
        # print(f"Error adding to startup: {e}", file=sys.stderr) # Заменяем на logging
        logging.error(f"OSError adding to startup: {e}")
        return False
    except Exception as e:
        # print(f"Unexpected error adding to startup: {e}", file=sys.stderr) # Заменяем на logging
        logging.exception(f"Unexpected error adding to startup") # Логируем с traceback
        return False


def remove_from_startup():
    """ Удаляет приложение из автозагрузки Windows """
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    key_name = APP_REGISTRY_KEY_NAME
    # --- Логируем попытку --- >
    logging.info(f"Attempting to remove from startup. Key: {key_path}\{key_name}")
    # --- < Логируем попытку ---

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, key_name)
        winreg.CloseKey(key)
        # print(f"Successfully removed from startup.") # Заменяем на logging
        logging.info(f"Successfully removed from startup.")
        return True
    except FileNotFoundError:
        # Ключа и так не было, это нормально
        # print(f"Startup key not found, nothing to remove.") # Заменяем на logging
        logging.warning(f"Startup key not found, nothing to remove.")
        return True
    except OSError as e:
        # print(f"Error removing from startup: {e}", file=sys.stderr) # Заменяем на logging
        logging.error(f"OSError removing from startup: {e}")
        return False
    except Exception as e:
        # print(f"Unexpected error removing from startup: {e}", file=sys.stderr) # Заменяем на logging
        logging.exception(f"Unexpected error removing from startup") # Логируем с traceback
        return False


# --- Основной блок запуска ---
if __name__ == "__main__":
    # --- Добавляем стартовое логирование --- >
    logging.info("-----------------------------------------")
    logging.info("Application starting...")
    logging.info(f"Frozen: {is_frozen()}")
    logging.info(f"sys.argv: {sys.argv}")
    logging.info(f"sys.executable: {sys.executable}")
    logging.info(f"os.getcwd(): {os.getcwd()}")
    logging.info(f"Attempting to set Org/App Name for QSettings...")
    # --- < Добавляем стартовое логирование ---

    # 0. Настройка QSettings (чтобы сохранялись в предсказуемое место)
    QApplication.setOrganizationName("MyCompany") # Замени на свое имя/название
    QApplication.setApplicationName("SpeechWidget")
    logging.info(f"QSettings Org: {QApplication.organizationName()}, App: {QApplication.applicationName()}")

    # 1. Загрузка модели Vosk
    try:
        vosk.SetLogLevel(-1)
        # print(f"Loading Vosk model from: {MODEL_PATH}...") # Заменяем на logging
        logging.info(f"Loading Vosk model from: {MODEL_PATH}...")
        model = vosk.Model(MODEL_PATH)
        recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(False)
        # print("Model loaded.") # Заменяем на logging
        logging.info("Model loaded.")
    except FileNotFoundError:
        # print(f"ERROR: Vosk model folder not found at '{MODEL_PATH}'") # Заменяем на logging
        logging.critical(f"ERROR: Vosk model folder not found at '{MODEL_PATH}'")
        sys.exit(1)
    except Exception as e:
        # print(f"ERROR: Failed to load Vosk model: {e}") # Заменяем на logging
        logging.critical(f"ERROR: Failed to load Vosk model: {e}", exc_info=True)
        sys.exit(1)

    # 2. Создание QApplication
    app = QApplication(sys.argv)
    # Важно: Запрещаем выход из приложения, когда последнее окно закрыто
    app.setQuitOnLastWindowClosed(False)

    # Инициализация QSettings (делаем глобально доступным)
    settings = QSettings()

    # 3. Создание виджета
    widget = SpeechWidget()

    # 4. Запуск слушателя клавиатуры в потоке
    keyboard_listener_worker = KeyboardListenerWorker()
    keyboard_listener_thread = threading.Thread(target=keyboard_listener_worker.run, daemon=True)
    keyboard_listener_worker.activate_signal.connect(widget.activate_widget)
    keyboard_listener_worker.deactivate_signal.connect(widget.deactivate_widget)
    keyboard_listener_thread.start()

    # 5. Отображение виджета и запуск цикла событий
    # Не показываем виджет сразу, он в трее
    widget.show()
    # print("Application started. Icon added to tray. Widget shown.") # Заменяем на logging
    logging.info("Application started. Icon added to tray. Widget shown.")

    # --- Проверка и синхронизация реестра при старте (опционально, но полезно) ---
    if is_frozen():
        startup_enabled_setting = settings.value("startup_enabled", False, type=bool)
        # Проверяем реальное состояние в реестре (можно реализовать функцию check_startup_status)
        # Если настройка и реестр расходятся, можно синхронизировать или вывести сообщение
        # Пример: if check_startup_status() != startup_enabled_setting: sync_startup_registry()
        # print("Running as executable.") # Заменяем на logging
        logging.info("Running as executable.")
    else:
        # print("Running as script.") # Заменяем на logging
        logging.info("Running as script.")
    # --- Конец проверки при старте ---

    exit_code = app.exec()
    try:
        # 6. Гарантированное завершение работы
        # print("Executing finally block...") # Заменяем на logging
        logging.info("Attempting shutdown sequence...")
        if keyboard_listener_worker: keyboard_listener_worker.stop()
        stop_recognition_thread() # Посылаем сигнал потоку Vosk

        # Явный вызов quit для приложения, если оно еще работает
        if app and QApplication.instance(): # Проверяем, существует ли еще экземпляр
             # print("Calling app.quit()...") # Заменяем на logging
             logging.info("Calling app.quit()...")
             QApplication.quit()

        # Опционально: дождаться завершения потоков
        # if keyboard_listener_thread and keyboard_listener_thread.is_alive(): keyboard_listener_thread.join(timeout=0.5)
        # if vosk_thread and vosk_thread.is_alive(): vosk_thread.join(timeout=0.5)
        # print("Finished.") # Заменяем на logging
        logging.info(f"Exiting with code {exit_code}.")
        sys.exit(exit_code) # Выход с соответствующим кодом

    except KeyboardInterrupt:
        # print("KeyboardInterrupt received, shutting down.") # Заменяем на logging
        logging.warning("KeyboardInterrupt received, shutting down.")
        exit_code = 1 # Указываем код ошибки
    except FileNotFoundError:
        # print(f"ERROR: Vosk model folder not found at '{MODEL_PATH}'") # Заменяем на logging
        logging.critical(f"ERROR: Vosk model folder not found at '{MODEL_PATH}'")
        exit_code = 1
    except ImportError as e:
         # ... (обработка ImportError как раньше) ...
         logging.critical(f"ImportError during shutdown or earlier: {e}", exc_info=True)
         exit_code = 1
    except Exception as e:
        # print(f"Unhandled exception in main: {e}") # Заменяем на logging
        logging.critical(f"Unhandled exception in main: {e}", exc_info=True)
        import traceback
        # traceback.print_exc() # Убираем, т.к. logging.exception сделает это
        exit_code = 1
    finally:
        # 6. Гарантированное завершение работы (повторный блок на всякий случай, если исключение было до первого finally)
        # print("Executing final finally block...") # Заменяем на logging
        logging.info("Executing final finally block...")
        # Стараемся остановить потоки еще раз, если возможно
        try:
            if 'keyboard_listener_worker' in locals() and keyboard_listener_worker: keyboard_listener_worker.stop()
        except Exception as e_stop: logging.error(f"Error stopping kbd listener in final finally: {e_stop}")
        try:
            if 'stop_recognition_thread' in locals(): stop_recognition_thread()
        except Exception as e_stop: logging.error(f"Error stopping vosk thread in final finally: {e_stop}")

        # Явный вызов quit для приложения, если оно еще работает
        try:
            if 'app' in locals() and app and QApplication.instance(): # Проверяем, существует ли еще экземпляр
                 logging.info("Calling app.quit() in final finally...")
                 QApplication.quit()
        except Exception as e_quit: logging.error(f"Error quitting app in final finally: {e_quit}")

        logging.info(f"Final exit with code {exit_code}.")
        sys.exit(exit_code) # Выход с соответствующим кодом
