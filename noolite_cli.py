#!/home/pi/Documents/Python/Telegram_bot/venv/bin/python
"""
OpenHab 2 CLI
"""
import os
import json
import logging
import argparse

import yaml

from noolite_api import NooLiteApi, NooLiteConnectionTimeout, NooLiteConnectionError, NooLiteBadResponse


# Logging config
logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))

config = yaml.load(open(os.path.join(SCRIPT_PATH, 'conf.yaml')))
noolite_api = NooLiteApi(config['noolite']['login'], config['noolite']['password'], config['noolite']['api_url'])


def send_command_to_noolite(command):
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


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-sns', type=int, help='Получить данные с указанного датчика')
    parser.add_argument('-ch',  type=int, help='Адрес канала')
    parser.add_argument('-cmd', type=int, help='Команда')
    parser.add_argument('-br',  type=int, help='Абсолютная яркость в, используется с командой=6')
    parser.add_argument('-fmt', type=int, help='Формат')
    parser.add_argument('-d0',  type=int, help='Байт данных 0')
    parser.add_argument('-d1',  type=int, help='Байт данных 1')
    parser.add_argument('-d2',  type=int, help='Байт данных 2')
    parser.add_argument('-d3',  type=int, help='Байт данных 3')
    return {key: value for key, value in vars(parser.parse_args()).items() if value is not None}


if __name__ == '__main__':
    args = get_args()
    logger.debug('Args: {}'.format(args))
    if 'sns' in args:
        try:
            sens_list = noolite_api.get_sens_data()
            send_data = sens_list[args['sns']]
            print(json.dumps({
                'temperature': send_data.temperature,
                'humidity': send_data.humidity,
                'state': send_data.state,
            }))
        except NooLiteConnectionTimeout as e:
            print(e)
        except NooLiteConnectionError as e:
            print(e)
        except NooLiteBadResponse as e:
            print(e)
    else:
        response, error = send_command_to_noolite(args)
        print(response, error)
