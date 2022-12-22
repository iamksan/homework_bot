import os
import time
import logging
from http import HTTPStatus
import telegram
import requests

from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    filename="main.log",
    filemode="a",
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
)


def check_tokens():
    """Функция проверка токенов."""
    tokens = {
        "practicum_token": PRACTICUM_TOKEN,
        "telegram_token": TELEGRAM_TOKEN,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
    }

    for key, value in tokens.items():
        if value is None:
            logging.error(f"{key} отсутствует")
            return False
        return True


def send_message(bot, message):
    """Функция отправки сообщений."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f"Ошибка при обращении к API Telegram: {error}")


def get_api_answer(timestamp):
    """Функция запроса API."""
    timestamp = int(time.time())
    params = {"from_date": timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        raise exceptions.WrongHttpStatus(
            "Ошибка при обращении к API Яндекс.Практикума: ",
            f'Код ответа: {response.json().get("code")}',
            f'Сообщение сервера: {response.json().get("message")}',
        )


def check_response(response):
    """Функция проверки ответа API."""
    try:
        timestamp = response["current_date"]
    except KeyError:
        logging.error(
            "Ключ current_date в ответе API Яндекс.Практикум отсутствует"
        )
    try:
        homeworks = response["homeworks"]
    except KeyError:
        logging.error(
            "Ключ homeworks в ответе API Яндекс.Практикум отсутствует"
        )
    if isinstance(timestamp, int) and isinstance(homeworks, list):
        return homeworks
    else:
        raise TypeError


def parse_status(homework):
    """Функция проверки статуса домашнего задания."""
    homework_name = homework["homework_name"]
    homework_status = homework.get("status")
    if homework_status is None:
        raise exceptions.KeyHomeworkStatusIsUnavailable
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise exceptions.UnknownHomeworkStatus


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time())

    while True:
        try:
            respose = get_api_answer(timestamp)
            homework = check_response(respose)
            sum_homework = len(homework)
            while sum_homework > 0:
                message = parse_status(homework[sum_homework - 1])
                send_message(bot, message)
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
