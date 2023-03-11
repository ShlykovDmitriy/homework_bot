class RequestStatusError(Exception):
    '''Обрабатывает исключение, возникающее при ошибке выполнения запроса.'''
    ...


class KeyNotFound(Exception):
    '''Обрабатывает исключение, при отсутствии ключа в ответе от API'''
    ...


class SendMessageError(Exception):
    '''Обрабатывает исключение, при неудачной отправке сообщения'''
    ...


class VerdictNotFound(Exception):
    '''Обрабатывает исключение, при неожиданном статусе домашней работы'''
    ...
