import os
import time
import logging
from http import HTTPStatus
import telegram
import requests

import exceptions

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename="main.log",
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка токенов."""
    tokens = {
        "practicum_token": PRACTICUM_TOKEN,
        "telegram_token": TELEGRAM_TOKEN,
        "telegram_chat_id": TELEGRAM_CHAT_ID,
    }

    for key, value in tokens.items():
        if value is None:
            exceptions.NoToken(f"{key} отсутствует")
            return False
        return True


def send_message(bot, message):
    """Отправляет сообщение с статусом обработки дз."""
    try:
        logger.debug('Начало отправки сообщений.')
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message
        )
    except Exception as error:
        logger.error(f'Ошибка отправки {message} : {error}')


def get_api_answer(timestamp):
    """Получить ответ от сервера практикума по API."""
    timestamp = int(time.time())
    params = {'from_date': timestamp}
    try:
        homework = requests.get(
            ENDPOINT,
            HEADERS,
            params
        )
    except requests.RequestException as error:
        message = f'Ошибка запроса к ENDPOINT: {error}.'
        logger.error(message)
        raise exceptions.EndPointError(message)
    status_code = homework.status_code
    if status_code != HTTPStatus.OK:
        message = f'Ошибка API: {status_code}'
        logger.error(message)
        raise exceptions.HTTPStatusCodeError(message)
    try:
        homework_json = homework.json()
    except Exception as error:
        message = f'Сбой при переводе в формат json: {error}'
        logger.error(message)
        raise exceptions.InvalidJSONTransform(message)
    return homework_json


def check_response(response):
    """Проверка ответа."""
    try:
        timestamp = response["current_date"]
    except KeyError:
        logger.error(
            "Ключ current_date в ответе API Яндекс.Практикум отсутствует"
        )
    try:
        homeworks = response["homeworks"]
    except KeyError:
        logger.error(
            "Ключ homeworks в ответе API Яндекс.Практикум отсутствует"
        )
    if not isinstance(homeworks, list) and isinstance(timestamp, int):
        raise TypeError
    return homeworks


def parse_status(homework):
    """Проверка статуса."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        message = 'Нет названия!'
        logger.error(message)
        raise KeyError(message)

    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'нет статуса.'
        logger.error(message)
        raise exceptions.Nostatus(message)

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Нет токена.'
        logger.critical(message)
        raise exceptions.VariableNotExists(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            homework = get_api_answer(timestamp)
            timestamp = homework.get('current_date')
            homeworks = check_response(homework)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Нет новых статусов.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
