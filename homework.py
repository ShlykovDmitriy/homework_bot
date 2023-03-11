import requests
import telegram
import os
import time
import sys
import logging

from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import (
    RequestStatusError, KeyNotFound, SendMessageError, VerdictNotFound
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


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


def check_tokens() -> None:
    '''Проверяет доступность переменных окружения.'''
    if not all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN]):
        logging.critical('Отсутствуют обязательные переменные бота')
        logging.info('Программа остановлена')
        sys.exit()
    logging.info('Проверка доступности токенов пройдена')


def send_message(bot: telegram.Bot, message: str) -> None:
    '''
    Отправляет сообщение в Telegram чат, определяемый TELEGRAM_CHAT_ID.
    Принимает два параметра: экземпляр класса Bot и строку с текстом сообщения.
    '''
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение {message} отправлено')
    except Exception as error:
        error_message = f'Ошибка при отправке сообщения: {error}'
        logging.error(error_message)
        raise SendMessageError(error_message)


def get_api_answer(timestamp: int) -> dict:
    '''
    Делает запрос к API-сервису Практикума.
    Принимает временную метку,
    при успешном запросе возвращает ответ в формате JSON.
    '''
    try:
        homeworks = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        logging.info('Запрос к API-сервису Практикума')
        if homeworks.status_code != HTTPStatus.OK:
            error_message = ('Ошибка при выполнении запроса.'
                             f'Статус:{homeworks.status_code}.')
            logging.error(error_message)
            raise RequestStatusError(error_message)
        logging.info('Ответ от API получен.')
        return homeworks.json()
    except Exception as error:
        error_message = f'Ошибка при выполнении запроса:{error}'
        logging.error(error_message)
        raise RequestStatusError(error_message)


def check_response(response: dict) -> dict:
    '''
    Проверяет ответ API на соответствие документации.
    Вкачестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    '''
    if not isinstance(response, dict):
        error_message = 'Ответ от API не является словарем'
        logging.error(error_message)
        raise TypeError(error_message)
    response_keys = ['homeworks', 'current_date']
    for key in response_keys:
        if key not in response:
            error_message = 'В ответе от API отсутствуeт ключ: {key}.'
            logging.error(error_message)
            raise KeyNotFound(error_message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        error_message = 'Homeworks не является списком'
        logging.error(error_message)
        raise TypeError(error_message)
    return homeworks[0]


def parse_status(homework: dict) -> str:
    '''
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В функцию передается один элемент из списка домашних работ.
    В случае успеха, функция возвращает строку для отправки в Telegram,
    содержащую один из вердиктов словаря HOMEWORK_VERDICTS.
    '''
    homework_keys = ['status', 'homework_name']
    for key in homework_keys:
        if key not in homework:
            error_message = f'У списка homeworks отсутствуeт ключ: {key}.'
            logging.error(error_message)
            raise KeyNotFound(error_message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = 'Неожиданный статус домашней работы.'
        logging.error(error_message)
        raise VerdictNotFound(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info('Сообщение для отправки подготовлено.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    '''Основная логика работы бота.'''
    logging.info('Программа запущена')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Начинаю проверку домашних работ')
    timestamp = 0  # int(time.time())
    last_message = ''
    last_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response['current_date']
            homework = check_response(response)
            message = parse_status(homework)
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logging.info('Новый статус домашней работы не обнаружен')
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_error != message:
                send_message(bot, message)
                logging.error(message)
                last_error = message
                time.sleep(RETRY_PERIOD)
            else:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Работа бота завершена')
