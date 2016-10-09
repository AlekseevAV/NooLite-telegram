import os
import logging
import functools

import yaml
import requests
import telnetlib
from requests.exceptions import ConnectionError
from telegram import ReplyKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler, Job

from noolite_api import NooLiteApi, NooLiteConnectionTimeout, NooLiteConnectionError, NooLiteBadResponse


# Получаем конфигруационные данные из файла
config = yaml.load(open('conf.yaml'))

# Базовые настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


# Подключаемся к боту и NooLite
updater = Updater(config['telegtam']['token'])
noolite_api = NooLiteApi(config['noolite']['login'], config['noolite']['password'], config['noolite']['api_url'])
job_queue = updater.job_queue


def auth_required(func):
    """Декоратор аутентификации"""
    @functools.wraps(func)
    def wrapped(bot, update):
        if update.message.chat_id not in config['telegtam']['authenticated_users']:
            bot.sendMessage(chat_id=update.message.chat_id, text="Вы неавторизованы.\nДля"
                                                                 " авторизации отправьте /auth password.")
        else:
            return func(bot, update)
    return wrapped


def log(func):
    """Декоратор логирования"""
    @functools.wraps(func)
    def wrapped(bot, update):
        logger.info('Received message: {}'.format(update.message.text if update.message else update.callback_query.data))
        func(bot, update)
        logger.info('Response was sent')
    return wrapped


def start(bot, update):
    """Команда начала взаимодействия с ботом"""
    bot.sendMessage(chat_id=update.message.chat_id, text="Для начала работы нужно авторизоваться.\nДля"
                                                         " авторизации отправьте /auth password.")


def auth(bot, update):
    """Аутентификация

    Если пароль указан верно, то в ответ приходит калвиатура управления умным домом
    """
    if config['telegtam']['password'] in update.message.text:
        if update.message.chat_id not in config['telegtam']['authenticated_users']:
            config['telegtam']['authenticated_users'].append(update.message.chat_id)
        custom_keyboard = [
            ['/Включить_обогреватели', '/Выключить_обогреватели'],
            ['/Включить_прожектор', '/Выключить_прожектор'],
            ['/Температура']
        ]
        reply_markup = ReplyKeyboardMarkup(custom_keyboard)
        bot.sendMessage(chat_id=update.message.chat_id, text="Вы авторизованы.", reply_markup=reply_markup)
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="Неправильный пароль.")


def send_command_to_noolite(command):
    """Обработка запросов в NooLite. Если возращается ошибка, то посылаем пользователю ответ об этом"""
    try:
        logger.info('Send command to noolite: {}'.format(command))
        response = noolite_api.send_command_to_channel(command)

    except NooLiteConnectionTimeout as e:
        logger.info(e)
        return None, "*Дача недоступна!*\n`{}`".format(e)

    except NooLiteConnectionError as e:
        logger.info(e)
        return None, "*Ошибка!*\n`{}`".format(e)

    except NooLiteBadResponse as e:
        logger.info(e)
        return None, "*Не удалось сделать запрос!*\n`{}`".format(e)

    return response.text, None


# ========================== Commands ================================

@log
@auth_required
def outdoor_light_on(bot, update):
    """Включения уличного прожектора"""
    response, error = send_command_to_noolite({'ch': 2, 'cmd': 2})
    logger.info('Send message: {}'.format(response or error))
    bot.sendMessage(chat_id=update.message.chat_id, text="{}".format(response or error))


@log
@auth_required
def outdoor_light_off(bot, update):
    """Выключения уличного прожектора"""
    response, error = send_command_to_noolite({'ch': 2, 'cmd': 0})
    logger.info('Send message: {}'.format(response or error))
    bot.sendMessage(chat_id=update.message.chat_id, text="{}".format(response or error))


@log
@auth_required
def heaters_on(bot, update):
    """Включения обогревателей"""
    response, error = send_command_to_noolite({'ch': 0, 'cmd': 2})
    logger.info('Send message: {}'.format(response or error))
    bot.sendMessage(chat_id=update.message.chat_id, text="{}".format(response or error))


@log
@auth_required
def heaters_off(bot, update):
    """Выключения обогревателей"""
    response, error = send_command_to_noolite({'ch': 0, 'cmd': 0})
    logger.info('Send message: {}'.format(response or error))
    bot.sendMessage(chat_id=update.message.chat_id, text="{}".format(response or error))


@log
@auth_required
def send_temperature(bot, update):
    """Получаем информацию с датчиков"""
    try:
        sens_list = noolite_api.get_sens_data()
    except NooLiteConnectionTimeout as e:
        logger.info(e)
        bot.sendMessage(chat_id=update.message.chat_id, text="*Дача недоступна!*\n`{}`".format(e),
                        parse_mode=ParseMode.MARKDOWN)
        return
    except NooLiteBadResponse as e:
        logger.info(e)
        bot.sendMessage(chat_id=update.message.chat_id, text="*Не удалось получить данные!*\n`{}`".format(e),
                        parse_mode=ParseMode.MARKDOWN)
        return
    except NooLiteConnectionError as e:
        logger.info(e)
        bot.sendMessage(chat_id=update.message.chat_id, text="*Ошибка подключения к noolite!*\n`{}`".format(e),
                        parse_mode=ParseMode.MARKDOWN)
        return

    if sens_list[0].temperature and sens_list[0].humidity:
        message = "Температура: *{}C*\nВлажность: *{}%*".format(sens_list[0].temperature, sens_list[0].humidity)
    else:
        message = "Ну удалось получить данные: {}".format(sens_list[0].state)

    logger.info('Send message: {}'.format(message))
    bot.sendMessage(chat_id=update.message.chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN)


@log
@auth_required
def send_log(bot, update):
    """Получение лога для отладки"""
    bot.sendDocument(chat_id=update.message.chat_id, document=open('/var/log/telegram_bot/err.log', 'rb'))


@log
def unknown(bot, update):
    """Неизвестная команда"""
    bot.sendMessage(chat_id=update.message.chat_id, text="Я не знаю такой команды")


def power_restore(bot, job):
    """Выполняется один раз при запуске бота"""
    for user_chat in config['telegtam']['authenticated_users']:
        bot.sendMessage(user_chat, 'Включение после перезагрузки')


def check_temperature(bot, job):
    """Переодическая проверка температуры с датчиков

    Eсли температура ниже, чем установленный минимум - посылаем уведомление зарегистрированным пользователям
    """
    try:
        sens_list = noolite_api.get_sens_data()
    except NooLiteConnectionTimeout as e:
        print(e)
        return
    except NooLiteConnectionError as e:
        print(e)
        return
    except NooLiteBadResponse as e:
        print(e)
        return
    if sens_list[0].temperature and sens_list[0].temperature < config['noolite']['temperature_alert']:
        for user_chat in config['telegtam']['authenticated_users']:
            bot.sendMessage(chat_id=user_chat,
                            text='*Температура ниже {} градусов: {}!*'.format(config['noolite']['temperature_alert'],
                                                                              sens_list[0].temperature),
                            parse_mode=ParseMode.MARKDOWN)


def check_internet_connection(bot, job):
    """Переодическая проверка доступа в интернет

    Если доступа в интрнет нет и попытки его проверки исчерпаны - то посылаем по telnet команду роутеру
    для его перезапуска.
    Если доступ в интернет после этого не появился - перезагружаем Raspberry Pi
    """
    try:
        requests.get('http://ya.ru')
        config['noolite']['internet_connection_counter'] = 0
    except ConnectionError:
        if config['noolite']['internet_connection_counter'] == 2:
            tn = telnetlib.Telnet(config['router']['ip'])

            tn.read_until(b"login: ")
            tn.write(config['router']['login'].encode('ascii') + b"\n")

            tn.read_until(b"Password: ")
            tn.write(config['router']['password'].encode('ascii') + b"\n")

            tn.write(b"reboot\n")

        elif config['noolite']['internet_connection_counter'] == 4:
            os.system("sudo reboot")
        else:
            config['noolite']['internet_connection_counter'] += 1


dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('auth', auth))
dispatcher.add_handler(CommandHandler('Температура', send_temperature))

dispatcher.add_handler(CommandHandler('Включить_обогреватели', heaters_on))
dispatcher.add_handler(CommandHandler('Выключить_обогреватели', heaters_off))
dispatcher.add_handler(CommandHandler('Включить_прожектор', outdoor_light_on))
dispatcher.add_handler(CommandHandler('Выключить_прожектор', outdoor_light_off))

dispatcher.add_handler(CommandHandler('log', send_log))
dispatcher.add_handler(MessageHandler([Filters.command], unknown))

job_queue.put(Job(check_internet_connection, 60*5), next_t=60*5)
job_queue.put(Job(check_temperature, 60*30), next_t=60*6)
job_queue.put(Job(power_restore, 60, repeat=False))

updater.start_polling(bootstrap_retries=-1)
