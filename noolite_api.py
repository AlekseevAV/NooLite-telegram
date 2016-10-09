"""
NooLite API wrapper
"""

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectTimeout, ConnectionError
import xml.etree.ElementTree as ET


class NooLiteSens:
    """Класс хранения и обработки информации, полученной с датчиков

    Пока как таковой обработки нет
    """
    def __init__(self, temperature, humidity, state):
        self.temperature = float(temperature.replace(',', '.')) if temperature != '-' else None
        self.humidity = int(humidity) if humidity != '-' else None
        self.state = state


class NooLiteApi:
    """Базовый враппер для общения с NooLite"""
    def __init__(self, login, password, base_api_url, request_timeout=10):
        self.login = login
        self.password = password
        self.base_api_url = base_api_url
        self.request_timeout = request_timeout

    def get_sens_data(self):
        """Получение и прасинг xml данных с датчиков

        :return: список NooLiteSens объектов для каждого датчика
        :rtype: list
        """
        response = self._send_request('{}/sens.xml'.format(self.base_api_url))
        sens_states = {
            0: 'Датчик привязан, ожидается обновление информации',
            1: 'Датчик не привязан',
            2: 'Нет сигнала с датчика',
            3: 'Необходимо заменить элемент питания в датчике'
        }
        response_xml_root = ET.fromstring(response.text)
        sens_list = []
        for sens_number in range(4):
            sens_list.append(NooLiteSens(
                response_xml_root.find('snst{}'.format(sens_number)).text,
                response_xml_root.find('snsh{}'.format(sens_number)).text,
                sens_states.get(int(response_xml_root.find('snt{}'.format(sens_number)).text))
            ))
        return sens_list

    def send_command_to_channel(self, data):
        """Отправка запроса к NooLite

        Отправляем запрос к NooLite с url параметрами из data
        :param data: url параметры
        :type data: dict
        :return: response
        """
        return self._send_request('{}/api.htm'.format(self.base_api_url), params=data)

    def _send_request(self, url, **kwargs):
        """Отправка запроса к NooLite и обработка возвращаемого ответа

        Отправка запроса к url с параметрами из kwargs
        :param url: url для запроса
        :type url: str
        :return: response от NooLite или исключение
        """

        try:
            response = requests.get(url, auth=HTTPBasicAuth(self.login, self.password),
                                    timeout=self.request_timeout, **kwargs)
        except ConnectTimeout as e:
            print(e)
            raise NooLiteConnectionTimeout('Connection timeout: {}'.format(self.request_timeout))
        except ConnectionError as e:
            print(e)
            raise NooLiteConnectionError('Connection timeout: {}'.format(self.request_timeout))

        if response.status_code != 200:
            raise NooLiteBadResponse('Bad response: {}'.format(response))
        else:
            return response

# Кастомные исключения
NooLiteConnectionTimeout = type('NooLiteConnectionTimeout', (Exception,), {})
NooLiteConnectionError = type('NooLiteConnectionError', (Exception,), {})
NooLiteBadResponse = type('NooLiteBadResponse', (Exception,), {})
NooLiteBadRequestMethod = type('NooLiteBadRequestMethod', (Exception,), {})
