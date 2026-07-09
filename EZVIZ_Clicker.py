import time
import os
import cv2
import numpy as np
import pyautogui
import win32gui
import win32ui
import win32con
import logging

# -------------------------------
# Настройки
# -------------------------------

IMAGE_PATH = r"C:\signature\Continue.png"

CHECK_TIME = 600   # 10 минут
SEARCH_THRESHOLD = 0.75

LOG_FILE = r"C:\signature\EZVIZ_Clicker.log"


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
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)

        if "Ezviz" in title or cls == "QTool":
            result.append(hwnd)

    win32gui.EnumWindows(callback, None)

    if result:
        return result[0]

    return None


# -------------------------------
# Скрин окна EZVIZ
# -------------------------------

def screenshot_window(hwnd):

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    width = right - left
    height = bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)

    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, width, height)

    saveDC.SelectObject(bmp)

    saveDC.BitBlt(
        (0,0),
        (width,height),
        mfcDC,
        (0,0),
        win32con.SRCCOPY
    )

    bmpinfo = bmp.GetInfo()
    bmpstr = bmp.GetBitmapBits(True)

    img = np.frombuffer(
        bmpstr,
        dtype=np.uint8
    )

    img.shape = (
        bmpinfo["bmHeight"],
        bmpinfo["bmWidth"],
        4
    )

    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    return cv2.cvtColor(
        img,
        cv2.COLOR_BGRA2BGR
    ), left, top


# -------------------------------
# Поиск Continue
# -------------------------------

def find_buttons(screen):

    template = cv2.imread(
        IMAGE_PATH
    )

    if template is None:
        logging.error("Continue.png not found")
        return []

    result = cv2.matchTemplate(
        screen,
        template,
        cv2.TM_CCOEFF_NORMED
    )

    locations = np.where(
        result >= SEARCH_THRESHOLD
    )

    points = []

    w = template.shape[1]
    h = template.shape[0]

    for x, y in zip(
        locations[1],
        locations[0]
    ):

        center = (
            x + w // 2,
            y + h // 2
        )

        # убираем дубли
        if not any(
            abs(center[0]-p[0]) < 30 and
            abs(center[1]-p[1]) < 30
            for p in points
        ):
            points.append(center)

    return points


# -------------------------------
# Клик
# -------------------------------

def click_points(points, offset_x, offset_y):

    for x,y in points:

        sx = offset_x + x
        sy = offset_y + y

        logging.info(
            f"Click Continue X={sx} Y={sy}"
        )

        pyautogui.click(
            sx,
            sy
        )

        time.sleep(1)



# -------------------------------
# Основной цикл
# -------------------------------

logging.info("EZVIZ Clicker started")


while True:

    try:

        hwnd = find_ezviz()

        if hwnd:

            img, ox, oy = screenshot_window(hwnd)

            buttons = find_buttons(img)


            if buttons:

                logging.info(
                    f"Found buttons: {len(buttons)}"
                )

                click_points(
                    buttons,
                    ox,
                    oy
                )

            else:

                logging.info(
                    "Continue button not found"
                )

        else:

            logging.info(
                "EZVIZ not running"
            )


    except Exception as e:

        logging.error(
            str(e)
        )


    time.sleep(CHECK_TIME)