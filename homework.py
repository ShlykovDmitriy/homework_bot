import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (KeyNotFound, RequestStatusError, VerdictNotFound)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
console_handler = logging.StreamHandler(stream=sys.stdout)
console_handler.setFormatter(formatter)
file_handler = logging.FileHandler('homework_bot.log', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN])


def send_message(bot: telegram.Bot, message: str) -> None:
    """
    Отправляет сообщение в Telegram чат, определяемый TELEGRAM_CHAT_ID.
    Принимает два параметра: экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение {message} отправлено')
        return True
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')
        return False


def get_api_answer(timestamp: int) -> dict:
    """
    Делает запрос к API-сервису Практикума.
    Принимает временную метку,
    при успешном запросе возвращает ответ в формате JSON.
    """
    try:
        logger.info('Запрос к API-сервису Практикума')
        homeworks = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise RequestStatusError(f'Ошибка при выполнении запроса:{error}')
    try:
        if homeworks.status_code != HTTPStatus.OK:
            raise RequestStatusError('Ошибка при выполнении запроса.'
                                     f'Статус:{homeworks.status_code}.')
        logger.info('Ответ от API получен.')
    except RequestStatusError as error:
        raise RequestStatusError(f'Ошибка при выполнении запроса:{error}')
    return homeworks.json()


def check_response(response: dict) -> list:
    """
    Проверяет ответ API на соответствие документации.
    Вкачестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    """
    if not isinstance(response, dict):
        error_message = 'Ответ от API не является словарем'
        logger.error(error_message)
        raise TypeError(error_message)
    response_keys = ['homeworks', 'current_date']
    for key in response_keys:
        if key not in response:
            error_message = 'В ответе от API отсутствуeт ключ: {key}.'
            logger.error(error_message)
            raise KeyNotFound(error_message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        error_message = 'Homeworks не является списком'
        logger.error(error_message)
        raise TypeError(error_message)
    return homeworks


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В функцию передается один элемент из списка домашних работ.
    В случае успеха, функция возвращает строку для отправки в Telegram,
    содержащую один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    homework_keys = ['status', 'homework_name']
    for key in homework_keys:
        if key not in homework:
            error_message = f'У списка homeworks отсутствуeт ключ: {key}.'
            logger.error(error_message)
            raise KeyNotFound(error_message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = 'Неожиданный статус домашней работы.'
        logger.error(error_message)
        raise VerdictNotFound(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    logger.info('Сообщение для отправки подготовлено.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    logger.info('Программа запущена')
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные бота')
        logger.info('Программа остановлена')
        sys.exit()
    logger.info('Проверка доступности токенов пройдена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = 'Обновление статуса работы отсутствует'
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                logger.info('Список домашних работ пуст')
            if message != last_message:
                if send_message(bot, message):
                    timestamp = response['current_date']
                    last_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_message != message:
                if send_message(bot, message):
                    last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('Работа бота завершена')
