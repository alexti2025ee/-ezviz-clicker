import time
import os
import ctypes
import traceback
import cv2
import numpy as np
import pyautogui
import win32gui
import win32ui
import win32con
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

# -------------------------------
# Опциональные библиотеки (mss, dxcam)
# -------------------------------
try:
    import mss
    MSS_AVAILABLE = True
except Exception:
    MSS_AVAILABLE = False

try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

try:
    import dxcam
    DXCAM_AVAILABLE = True
except Exception:
    DXCAM_AVAILABLE = False


# -------------------------------
# Настройки
# -------------------------------

IMAGE_PATH = r"C:\signature\Continue.png"
CHECK_TIME = 600   # 10 минут
SEARCH_THRESHOLD = 0.75
LOG_FILE = r"C:\signature\EZVIZ_Clicker.log"
DEBUG_DIR = r"C:\signature\debug"

os.makedirs(DEBUG_DIR, exist_ok=True)

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
        cls = win32gui.GetClassName(hwnd)
        if "Ezviz" in title or "EZVIZ" in title:
            result.append(hwnd)

    win32gui.EnumWindows(callback, None)

    if result:
        return result[0]

    return None


# -------------------------------
# Метод 1: BitBlt
# -------------------------------

def capture_bitblt(hwnd):
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return None

        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(bmp)

        saveDC.BitBlt(
            (0, 0), (width, height),
            mfcDC, (0, 0),
            win32con.SRCCOPY
        )

        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)

        img = np.frombuffer(bmpstr, dtype=np.uint8)
        img.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)

        win32gui.DeleteObject(bmp.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    except Exception as e:
        logging.error(f"[BitBlt] Error: {e}")
        return None


# -------------------------------
# Метод 2: PrintWindow (PW_RENDERFULLCONTENT)
# -------------------------------

def capture_printwindow(hwnd):
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return None

        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(bmp)

        PW_RENDERFULLCONTENT = 0x00000002
        result = ctypes.windll.user32.PrintWindow(
            hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT
        )

        bmpinfo = bmp.GetInfo()
        bmpstr = bmp.GetBitmapBits(True)

        img = np.frombuffer(bmpstr, dtype=np.uint8)
        img.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)

        win32gui.DeleteObject(bmp.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        if not result:
            logging.info("[PrintWindow] result=0 (возможно не сработал)")

        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    except Exception as e:
        logging.error(f"[PrintWindow] Error: {e}")
        return None


# -------------------------------
# Метод 3: MSS (снимок региона экрана)
# -------------------------------

def capture_mss(hwnd):
    if not MSS_AVAILABLE:
        return None
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return None

        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(monitor)
            img = np.array(shot)  # BGRA
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    except Exception as e:
        logging.error(f"[MSS] Error: {e}")
        return None


# -------------------------------
# Метод 4: PIL ImageGrab
# -------------------------------

def capture_pil(hwnd):
    if not PIL_AVAILABLE:
        return None
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)

        if right - left <= 0 or bottom - top <= 0:
            return None

        img = ImageGrab.grab(bbox=(left, top, right, bottom))
        arr = np.array(img)  # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    except Exception as e:
        logging.error(f"[PIL] Error: {e}")
        return None


# -------------------------------
# Метод 5: DXcam (для DirectX/OpenGL окон)
# -------------------------------

_dxcam_instance = None

def capture_dxcam(hwnd):
    global _dxcam_instance
    if not DXCAM_AVAILABLE:
        return None
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return None

        if _dxcam_instance is None:
            _dxcam_instance = dxcam.create()

        region = (left, top, right, bottom)
        frame = _dxcam_instance.grab(region=region)

        if frame is None:
            return None

        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    except Exception as e:
        logging.error(f"[DXcam] Error: {e}")
        return None


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
# Клик
# -------------------------------

def click_points(points, offset_x, offset_y, method_name):
    for x, y in points:
        sx = offset_x + x
        sy = offset_y + y
        logging.info(f"[{method_name}] Click Continue X={sx} Y={sy}")
        pyautogui.click(sx, sy)
        time.sleep(1)


# -------------------------------
# Основной цикл
# -------------------------------

logging.info("EZVIZ Clicker (multi-method debug) started")
logging.info(f"mss available: {MSS_AVAILABLE}, PIL available: {PIL_AVAILABLE}, dxcam available: {DXCAM_AVAILABLE}")

template = cv2.imread(IMAGE_PATH)
if template is None:
    logging.error(f"Continue.png не найден по пути: {IMAGE_PATH}")

while True:
    try:
        hwnd = find_ezviz()

        if hwnd:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)

            methods = [
                ("bitblt", capture_bitblt, "capture_bitblt.png"),
                ("printwindow", capture_printwindow, "capture_printwindow.png"),
                ("mss", capture_mss, "capture_mss.png"),
                ("pil", capture_pil, "capture_pil.png"),
                ("dxcam", capture_dxcam, "capture_dxcam.png"),
            ]

            best_points = []
            best_method = None

            for name, func, filename in methods:
                img = func(hwnd)

                if img is None:
                    logging.info(f"[{name}] Снимок не получен (метод недоступен или ошибка)")
                    continue

                debug_path = os.path.join(DEBUG_DIR, filename)
                try:
                    cv2.imwrite(debug_path, img)
                except Exception as e:
                    logging.error(f"[{name}] Не удалось сохранить debug-файл: {e}")

                points = find_buttons(img, template)
                logging.info(f"[{name}] Найдено совпадений: {len(points)}")

                if points and not best_points:
                    best_points = points
                    best_method = name

            if best_points:
                logging.info(f"Клик будет выполнен методом: {best_method}, найдено кнопок: {len(best_points)}")
                click_points(best_points, left, top, best_method)
            else:
                logging.info("Continue button not found ни одним из методов")

        else:
            logging.info("EZVIZ not running")

    except Exception as e:
        logging.error(traceback.format_exc())

    time.sleep(CHECK_TIME)
