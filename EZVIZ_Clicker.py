import time
import os
import ctypes
import traceback
import datetime
import cv2
import numpy as np
import pyautogui
import win32gui
import logging

# -------------------------------
# DPI awareness (важно для точных координат клика)
# -------------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import mss
from PIL import ImageGrab
import tkinter as tk

# -------------------------------
# Настройки
# -------------------------------

IMAGE_PATH = r"C:\signature\Continue.png"
CHECK_INTERVAL = 600        # проверка кнопки каждые 10 минут
SEARCH_THRESHOLD = 0.75
LOG_FILE = r"C:\signature\EZVIZ_Clicker.log"

SHUTDOWN_WINDOW_START_HOUR = 17
SHUTDOWN_WINDOW_START_MINUTE = 45
SHUTDOWN_WINDOW_END_HOUR = 18
SHUTDOWN_WINDOW_END_MINUTE = 0

NOTIFY_TEXT = "Кнопка на камерах будет нажата"
NOTIFY_DURATION_MS = 5000   # 5 секунд


# -------------------------------
# Лог
# -------------------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)


# -------------------------------
# Найти окно EZVIZ
# -------------------------------

def find_ezviz():
    result = []

    def callback(hwnd, extra):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if "Ezviz" in title or "EZVIZ" in title:
            result.append(hwnd)

    win32gui.EnumWindows(callback, None)

    if result:
        return result[0]

    return None


# -------------------------------
# Захват окна: mss (основной), PIL (запасной)
# -------------------------------

def capture_mss(left, top, width, height):
    try:
        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(monitor)
            img = np.array(shot)  # BGRA
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except Exception as e:
        logging.error(f"[mss] Error: {e}")
        return None


def capture_pil(left, top, right, bottom):
    try:
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
        arr = np.array(img)  # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logging.error(f"[pil] Error: {e}")
        return None


def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        return None, left, top

    img = capture_mss(left, top, width, height)
    if img is not None:
        return img, left, top

    img = capture_pil(left, top, right, bottom)
    if img is not None:
        return img, left, top

    return None, left, top


# -------------------------------
# Поиск Continue.png на снимке
# -------------------------------

def find_buttons(screen, template):
    if screen is None or template is None:
        return []

    if screen.shape[0] < template.shape[0] or screen.shape[1] < template.shape[1]:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= SEARCH_THRESHOLD)

    points = []
    w = template.shape[1]
    h = template.shape[0]

    for x, y in zip(locations[1], locations[0]):
        center = (x + w // 2, y + h // 2)
        if not any(
            abs(center[0] - p[0]) < 30 and abs(center[1] - p[1]) < 30
            for p in points
        ):
            points.append(center)

    return points


# -------------------------------
# Окно-предупреждение перед кликом
# -------------------------------

def show_notification(text, duration_ms):
    try:
        root = tk.Tk()
        root.title("EZVIZ Clicker")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        width, height = 360, 100
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        root.geometry(f"{width}x{height}+{x}+{y}")

        label = tk.Label(
            root,
            text=text,
            font=("Segoe UI", 12),
            wraplength=320,
            justify="center"
        )
        label.pack(expand=True, fill="both", padx=10, pady=10)

        root.after(duration_ms, root.destroy)
        root.mainloop()

    except Exception as e:
        logging.error(f"[notify] Error: {e}")


# -------------------------------
# Клик
# -------------------------------

def click_points(points, offset_x, offset_y):
    for x, y in points:
        sx = offset_x + x
        sy = offset_y + y
        logging.info(f"Click Continue X={sx} Y={sy}")
        pyautogui.click(sx, sy)
        time.sleep(1)


# -------------------------------
# Проверка времени выключения
# -------------------------------

def is_in_shutdown_window():
    now = datetime.datetime.now().time()
    window_start = datetime.time(SHUTDOWN_WINDOW_START_HOUR, SHUTDOWN_WINDOW_START_MINUTE)
    window_end = datetime.time(SHUTDOWN_WINDOW_END_HOUR, SHUTDOWN_WINDOW_END_MINUTE)
    return window_start <= now <= window_end


# -------------------------------
# Одна проверка кнопки
# -------------------------------

def run_check(template):
    try:
        hwnd = find_ezviz()

        if not hwnd:
            logging.info("EZVIZ not running")
            return

        img, left, top = capture_window(hwnd)

        if img is None:
            logging.info("Не удалось сделать снимок окна EZVIZ")
            return

        points = find_buttons(img, template)

        if points:
            logging.info(f"Найдено кнопок: {len(points)}")
            show_notification(NOTIFY_TEXT, NOTIFY_DURATION_MS)
            click_points(points, left, top)
        else:
            logging.info("Continue button not found")

    except Exception:
        logging.error(traceback.format_exc())


# -------------------------------
# Основной цикл
# -------------------------------

logging.info("EZVIZ Clicker started")

template = cv2.imread(IMAGE_PATH)
if template is None:
    logging.error(f"Continue.png не найден по пути: {IMAGE_PATH}")

while True:

    if is_in_shutdown_window():
        logging.info(
            f"Текущее время попало в окно {SHUTDOWN_WINDOW_START_HOUR:02d}:{SHUTDOWN_WINDOW_START_MINUTE:02d}"
            f"-{SHUTDOWN_WINDOW_END_HOUR:02d}:{SHUTDOWN_WINDOW_END_MINUTE:02d} — завершение работы"
        )
        break

    run_check(template)

    time.sleep(CHECK_INTERVAL)

logging.info("EZVIZ Clicker stopped")
