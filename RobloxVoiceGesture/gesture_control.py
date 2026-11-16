
import cv2
import os
import mediapipe as mp
import ctypes
import time
import json
import queue
import threading
import re
import traceback
import sounddevice as sd

from vosk import Model, KaldiRecognizer


# ============================================================
# НАСТРОЙКИ
# ============================================================

CAMERA_ID = 0
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "vosk-model-small-ru-0.22"
)
SAMPLE_RATE = 16000

CENTER_X = 0.5
CENTER_Y = 0.5

MOVE_THRESHOLD = 0.12

FIST_ZONE_X = 0.18
FIST_ZONE_Y = 0.18

INTERACTION_COOLDOWN = 0.8
PEACE_COOLDOWN = 1.5

FIRE_KEY = "G"

# Удержание кнопки двери
DOOR_HOLD_DURATION = 1.2


# ============================================================
# КОДЫ КЛАВИШ
# ============================================================

KEY_CODES = {
    "W": 0x57,
    "A": 0x41,
    "S": 0x53,
    "D": 0x44,
    "E": 0x45,
    "G": 0x47,
    "H": 0x48,
    "R": 0x52,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39
}

KEYEVENTF_KEYUP = 0x0002


# ============================================================
# СОСТОЯНИЕ КЛАВИАТУРЫ
# ============================================================

held_keys = set()
keyboard_lock = threading.Lock()


# ============================================================
# УПРАВЛЕНИЕ КЛАВИАТУРОЙ WINDOWS
# ============================================================

def press_key(key):

    key = key.upper()

    if key not in KEY_CODES:
        return

    with keyboard_lock:

        if key in held_keys:
            return

        ctypes.windll.user32.keybd_event(
            KEY_CODES[key], 0, 0, 0
        )

        held_keys.add(key)


def release_key(key):

    key = key.upper()

    if key not in KEY_CODES:
        return

    with keyboard_lock:

        ctypes.windll.user32.keybd_event(
            KEY_CODES[key], 0, KEYEVENTF_KEYUP, 0
        )

        held_keys.discard(key)


def tap_key(key, duration=0.08):

    key = key.upper()

    if key not in KEY_CODES:
        print("Неизвестная клавиша:", key)
        return

    press_key(key)

    try:
        time.sleep(duration)

    finally:
        release_key(key)

    print("Нажатие клавиши:", key)


# ============================================================
# НОВАЯ ФУНКЦИЯ: ПОЛНОЕ УДЕРЖАНИЕ КЛАВИШИ
# ============================================================

def hold_key(key, duration=1.2):

    key = key.upper()

    if key not in KEY_CODES:
        print("Неизвестная клавиша:", key)
        return

    vk = KEY_CODES[key]

    print(
        f"НАЧАЛО УДЕРЖАНИЯ {key}: "
        f"{duration} секунд"
    )

    # Нажимаем клавишу
    press_key(key)

    try:

        # Держим клавишу нажатой
        time.sleep(duration)

    finally:

        # Обязательно отпускаем клавишу
        release_key(key)

        print("КЛАВИША ОТПУЩЕНА:", key)


def release_all():

    for key in list(held_keys):
        release_key(key)


# ============================================================
# ГОЛОСОВОЕ УПРАВЛЕНИЕ
# ============================================================

audio_queue = queue.Queue()
voice_queue = queue.Queue()

FIRE_PHRASES = [
    "зажги свечу",
    "зажечь свечу",
    "подожги свечу",
    "зажги",
    "подожги"
]

READ_NOTE_PHRASES = [
    "прочитать",
    "прочитай",
    "прочитать записку",
    "прочитай записку"
]

NUMBER_WORDS = {
    "один": "1",
    "одна": "1",
    "первый": "1",
    "первая": "1",
    "два": "2",
    "две": "2",
    "второй": "2",
    "вторая": "2",
    "три": "3",
    "третий": "3",
    "третья": "3",
    "четыре": "4",
    "четвертый": "4",
    "четвертая": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9"
}


def normalize_text(text):

    text = text.lower()

    text = re.sub(
        r"[^а-яё0-9 ]",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def recognize_command(text):

    text = normalize_text(text)

    if not text:
        return None

    print("Распознано:", text)

    for phrase in READ_NOTE_PHRASES:

        if phrase in text:
            return ("KEY", "R")

    for phrase in FIRE_PHRASES:

        if phrase in text:
            return ("KEY", FIRE_KEY)

    for word, number in NUMBER_WORDS.items():

        if word in text:
            return ("KEY", number)

    return None


def audio_callback(
    indata,
    frames,
    callback_time,
    status
):

    if status:
        print("Аудио:", status)

    audio_queue.put(bytes(indata))


def voice_recognition():

    try:

        print("Загрузка голосовой модели...")

        model = Model(MODEL_PATH)

        grammar = [
            "зажги свечу",
            "зажечь свечу",
            "подожги свечу",
            "зажги",
            "подожги",
            "прочитать",
            "прочитай",
            "прочитать записку",
            "прочитай записку",
            "свеча один",
            "свеча два",
            "свеча три",
            "свеча четыре",
            "один",
            "два",
            "три",
            "четыре",
            "пять",
            "шесть",
            "семь",
            "восемь",
            "девять",
            "[unk]"
        ]

        recognizer = KaldiRecognizer(
            model,
            SAMPLE_RATE,
            json.dumps(
                grammar,
                ensure_ascii=False
            )
        )

        print("Голосовое управление запущено.")

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=audio_callback
        ):

            while True:

                data = audio_queue.get()

                if recognizer.AcceptWaveform(data):

                    result = json.loads(
                        recognizer.Result()
                    )

                    recognized_text = result.get(
                        "text",
                        ""
                    )

                    command = recognize_command(
                        recognized_text
                    )

                    if command:
                        voice_queue.put(command)

    except Exception:

        print(
            "\nОШИБКА ГОЛОСОВОГО УПРАВЛЕНИЯ:"
        )

        traceback.print_exc()


def process_voice_commands():

    while not voice_queue.empty():

        command = voice_queue.get()

        command_type, key = command

        if command_type == "KEY":

            print(
                "Голосовая команда. "
                "Нажатие:",
                key
            )

            tap_key(key)


# ============================================================
# РАСПОЗНАВАНИЕ КУЛАКА
# ============================================================

def is_fist(hand):

    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]

    folded = 0

    for tip, pip in zip(tips, pips):

        if (
            hand.landmark[tip].y
            > hand.landmark[pip].y
        ):

            folded += 1

    return folded >= 3


# ============================================================
# РАСПОЗНАВАНИЕ ЖЕСТА V
# ============================================================

def is_peace_sign(hand):

    landmarks = hand.landmark

    index_up = (
        landmarks[8].y
        < landmarks[6].y
    )

    middle_up = (
        landmarks[12].y
        < landmarks[10].y
    )

    ring_folded = (
        landmarks[16].y
        > landmarks[14].y
    )

    pinky_folded = (
        landmarks[20].y
        > landmarks[18].y
    )

    fingers_separated = abs(
        landmarks[8].x
        - landmarks[12].x
    ) > 0.035

    return (
        index_up
        and middle_up
        and ring_folded
        and pinky_folded
        and fingers_separated
    )


def get_hand_position(hand):

    landmark = hand.landmark[9]

    return landmark.x, landmark.y


# ============================================================
# ДВИЖЕНИЕ WASD
# ============================================================

current_keys = set()


def stop_movement():

    global current_keys

    for key in current_keys.copy():

        release_key(key)

    current_keys.clear()


def control_movement(x, y):

    global current_keys

    new_keys = set()

    dx = x - CENTER_X
    dy = y - CENTER_Y

    if abs(dx) > MOVE_THRESHOLD:

        if dx < 0:
            new_keys.add("A")

        else:
            new_keys.add("D")

    if abs(dy) > MOVE_THRESHOLD:

        if dy < 0:
            new_keys.add("W")

        else:
            new_keys.add("S")

    for key in current_keys - new_keys:

        release_key(key)

    for key in new_keys - current_keys:

        press_key(key)

    current_keys = new_keys


# ============================================================
# ЗАПУСК
# ============================================================

def main():

    print("\n===================================")
    print("ROBLOX GESTURE + VOICE CONTROL")
    print("===================================")

    print("Модель:", MODEL_PATH)

    print("\nГолосовые команды:")
    print("- Зажги свечу")
    print("- Свеча один")
    print("- Свеча два")
    print("- Свеча три")
    print("- Свеча четыре")
    print("- Цифры от одного до девяти")
    print("- Прочитай записку")

    print("\nУправление жестами:")
    print("- Открытая ладонь — WASD")
    print("- Кулак в центре — E (камни)")
    print("- Жест V — удержание H (дверь подвала)")
    print("- Голос — управление свечами")
    print("- Q — выход")

    print("\nЗапуск камеры...")

    camera = cv2.VideoCapture(CAMERA_ID)

    if not camera.isOpened():

        print(
            "ОШИБКА: Не удалось открыть камеру."
        )

        return

    print("Камера успешно запущена.")

    voice_thread = threading.Thread(
        target=voice_recognition,
        daemon=True
    )

    voice_thread.start()

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils

    last_stone_interaction = 0
    last_peace_interaction = 0

    fist_was_detected = False
    peace_was_detected = False

    print("\nMAIN LOOP STARTED")
    print(
        "Программа ожидает жесты "
        "и голосовые команды.\n"
    )

    try:

        with mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        ) as hands:

            while True:

                # Голосовые команды
                process_voice_commands()

                # Камера
                success, frame = camera.read()

                if not success:

                    print(
                        "ОШИБКА: Не удалось получить кадр камеры."
                    )

                    break

                frame = cv2.flip(
                    frame,
                    1
                )

                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                results = hands.process(
                    rgb_frame
                )

                if results.multi_hand_landmarks:

                    for hand in results.multi_hand_landmarks:

                        mp_drawing.draw_landmarks(
                            frame,
                            hand,
                            mp_hands.HAND_CONNECTIONS
                        )

                        x, y = get_hand_position(hand)

                        current_time = time.time()

                        # ====================================
                        # ЖЕСТ V — ДВЕРЬ ПОДВАЛА
                        # ====================================

                        peace = is_peace_sign(hand)

                        if peace:

                            stop_movement()

                            fist_was_detected = False

                            if (
                                not peace_was_detected
                                and
                                current_time
                                - last_peace_interaction
                                > PEACE_COOLDOWN
                            ):

                                print(
                                    "\nЖЕСТ V РАСПОЗНАН!"
                                )

                                print(
                                    "Начинаю удерживать H..."
                                )

                                # ИСПРАВЛЕНИЕ:
                                # полноценное удержание H
                                hold_key(
                                    "H",
                                    DOOR_HOLD_DURATION
                                )

                                last_peace_interaction = (
                                    time.time()
                                )

                                print(
                                    "Удержание H завершено."
                                )

                            peace_was_detected = True

                            cv2.putText(
                                frame,
                                "V SIGN - HOLD H",
                                (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 255),
                                2
                            )

                        else:

                            peace_was_detected = False

                            # ====================================
                            # КУЛАК — СБОР КАМНЕЙ
                            # ====================================

                            fist = is_fist(hand)

                            in_center = (
                                abs(x - CENTER_X)
                                < FIST_ZONE_X
                                and
                                abs(y - CENTER_Y)
                                < FIST_ZONE_Y
                            )

                            if fist and in_center:

                                stop_movement()

                                if (
                                    not fist_was_detected
                                    and
                                    current_time
                                    - last_stone_interaction
                                    > INTERACTION_COOLDOWN
                                ):

                                    print(
                                        "Жест: кулак."
                                        " Нажатие E."
                                    )

                                    tap_key("E")

                                    last_stone_interaction = (
                                        time.time()
                                    )

                                fist_was_detected = True

                                cv2.putText(
                                    frame,
                                    "FIST - COLLECT STONE (E)",
                                    (10, 70),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7,
                                    (255, 200, 0),
                                    2
                                )

                            else:

                                fist_was_detected = False

                                # ====================================
                                # ОТКРЫТАЯ ЛАДОНЬ — WASD
                                # ====================================

                                control_movement(
                                    x,
                                    y
                                )

                else:

                    # Рука пропала из кадра
                    stop_movement()

                    fist_was_detected = False
                    peace_was_detected = False

                # ====================================
                # ОТОБРАЖЕНИЕ КАМЕРЫ
                # ====================================

                cv2.putText(
                    frame,
                    "Roblox Gesture + Voice Control",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.imshow(
                    "Roblox Gesture Control",
                    frame
                )

                # ====================================
                # ВЫХОД ПО Q
                # ====================================

                key = cv2.waitKey(1) & 0xFF

                if key == ord("q") or key == ord("Q"):

                    print(
                        "\nВЫХОД: нажата клавиша Q."
                    )

                    break

    except Exception:

        print(
            "\nОШИБКА В ОСНОВНОМ ЦИКЛЕ:"
        )

        traceback.print_exc()

    finally:

        print(
            "\nЗавершение программы..."
        )

        release_all()

        camera.release()

        cv2.destroyAllWindows()

        print(
            "Программа остановлена."
        )


if __name__ == "__main__":

    main()
