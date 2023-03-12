class RequestStatusError(Exception):
    '''Обрабатывает исключение, возникающее при ошибке выполнения запроса.'''
    ...


class KeyNotFound(Exception):
    '''Обрабатывает исключение, при отсутствии ключа в ответе от API'''
    ...


class VerdictNotFound(Exception):
    '''Обрабатывает исключение, при неожиданном статусе домашней работы'''
    ...
