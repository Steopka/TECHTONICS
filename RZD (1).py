# --- START OF FILE RZD.py ---

# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import traceback # Import traceback for detailed error logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Константы ---
SOCHI_STATION_CODE = "9623103"
BASE_URL = "https://rasp.yandex.ru/station/{}/"
LAST_FLIGHTS_COUNT = 4 # Keep this, might be useful for display later

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
}

def get_today_date_string():
  """Возвращает сегодняшнюю дату в формате YYYY-MM-DD."""
  return datetime.now().strftime("%Y-%m-%d")

def fetch_schedule_html(station_code, event_type):
  """Загружает HTML-страницу с расписанием."""
  today_date = get_today_date_string()
  url = BASE_URL.format(station_code) + f"?date={today_date}&event={event_type}"
  logging.info(f"RZD Parser: Запрос расписания по URL: {url}")
  try:
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    logging.info(f"RZD Parser: Страница для {event_type} успешно загружена.")
    return response.text
  except requests.exceptions.Timeout:
    logging.error(f"RZD Parser: Ошибка таймаута при запросе к {url}")
    return None
  except requests.exceptions.RequestException as e:
    logging.error(f"RZD Parser: Ошибка при запросе к {url}: {e}")
    return None
  except Exception as e:
      logging.error(f"RZD Parser: Неожиданная ошибка при загрузке {url}: {e}")
      return None

def parse_schedule_data(html_content, event_type):
  """Парсит HTML и извлекает информацию о рейсах."""
  if not html_content:
    return []

  schedule = []
  try:
    soup = BeautifulSoup(html_content, 'html.parser')
    segments = soup.select('article.SearchSegment')
    logging.info(f"RZD Parser: Найдено {len(segments)} сегментов ({event_type}) для парсинга.")

    if not segments:
        logging.warning(f"RZD Parser: Не найдено сегментов расписания на странице для {event_type}.")
        no_schedule_message = soup.select_one('.ScheduleEmpty')
        if no_schedule_message:
            logging.info(f"RZD Parser: Найдено сообщение об отсутствии рейсов: {no_schedule_message.text.strip()}")
        return []

    for segment in segments:
      time_element = None
      if event_type == 'arrival':
        time_element = segment.select_one('.SearchSegment__arrival .SegmentTime__time')
      elif event_type == 'departure':
        time_element = segment.select_one('.SearchSegment__departure .SegmentTime__time')

      train_num_element = segment.select_one('.TransportIcon__number')
      if not train_num_element:
          train_num_element = segment.select_one('.SearchSegment__transport .TransportIcon')
      train_name_element = segment.select_one('.SearchSegment__headerTitle')
      route_element = segment.select_one('.SearchSegment__headerSubtitle')

      if time_element and route_element:
        time_str = time_element.text.strip()
        train_info = ""
        if train_num_element:
            train_info += train_num_element.text.strip()
        if train_name_element:
            name_text = train_name_element.text.strip()
            if name_text not in train_info:
                train_info += f" '{name_text}'"
        if not train_info: train_info = "Не указан"
        route_str = route_element.text.strip().replace('\n', ' ').replace('\xa0', ' ').strip()

        schedule.append({
            'time': time_str,
            'train': train_info.strip(),
            'route': route_str
        })
      else:
          logging.warning(f"RZD Parser: Не удалось полностью распарсить сегмент ({event_type}).")
          # logging.debug(f"RZD Parser: Содержимое проблемного сегмента: {segment}")

  except Exception as e:
    logging.error(f"RZD Parser: Ошибка при парсинге HTML для {event_type}: {e}", exc_info=True)
    return [] # Return empty list on parsing error

  return schedule

def get_sochi_schedule():
    """
    Основная функция для получения расписания прибытия и отправления для Сочи.

    Returns:
        tuple: Кортеж (arrivals_schedule, departures_schedule, error_message).
               arrivals_schedule: list - список словарей прибывающих поездов.
               departures_schedule: list - список словарей отправляющихся поездов.
               error_message: str or None - сообщение об ошибке, если не удалось получить данные.
    """
    logging.info("RZD Parser: Запрос полного расписания для Сочи...")
    error_message = None
    arrivals_schedule = []
    departures_schedule = []

    # Получаем и парсим прибытия
    arrivals_html = fetch_schedule_html(SOCHI_STATION_CODE, 'arrival')
    if arrivals_html:
        arrivals_schedule = parse_schedule_data(arrivals_html, 'arrival')
    else:
        error_message = "Не удалось загрузить данные о прибытии."
        logging.error(error_message)
        # Можно продолжить и попробовать получить отправления

    # Получаем и парсим отправления
    departures_html = fetch_schedule_html(SOCHI_STATION_CODE, 'departure')
    if departures_html:
        departures_schedule = parse_schedule_data(departures_html, 'departure')
    else:
        # Дополняем сообщение об ошибке, если оно уже есть, или создаем новое
        dep_error = "Не удалось загрузить данные об отправлении."
        logging.error(dep_error)
        if error_message:
            error_message += " " + dep_error
        else:
            error_message = dep_error

    # Если нет ни прибытий, ни отправлений, и была ошибка загрузки - возвращаем ошибку
    if not arrivals_schedule and not departures_schedule and error_message:
         # error_message уже содержит детали
         pass
    elif not error_message and not arrivals_schedule and not departures_schedule:
        # Если ошибок загрузки не было, но парсинг не дал результатов
        error_message = "Не найдено рейсов прибытия или отправления на сегодня."
        logging.warning(error_message)
    else:
        # Если хотя бы что-то загрузилось/распарсилось, не считаем это полной ошибкой
        error_message = None # Сбрасываем ошибку, если есть хоть какие-то данные

    logging.info(f"RZD Parser: Получено {len(arrivals_schedule)} прибытий, {len(departures_schedule)} отправлений.")
    return arrivals_schedule, departures_schedule, error_message


# --- Блок для самостоятельного тестирования парсера ---
if __name__ == "__main__":
    print("-" * 30)
    print(f"Тест парсера расписания РЖД для станции Сочи ({SOCHI_STATION_CODE})")
    print(f"Дата: {get_today_date_string()}")
    print("-" * 30)

    arrivals, departures, error = get_sochi_schedule()

    if error:
        print(f"\nОШИБКА: {error}")

    print(f"\n--- Найдено прибытий: {len(arrivals)} ---")
    if arrivals:
        # Выводим только последние N для краткости в тесте
        for flight in arrivals[-LAST_FLIGHTS_COUNT:]:
             print(f"  Время: {flight['time']}, Поезд: {flight['train']}, Маршрут: {flight['route']}")
        if len(arrivals) > LAST_FLIGHTS_COUNT:
            print("  ...") # Показываем, что есть еще рейсы
    else:
        print("  (Нет данных о прибытии)")


    print(f"\n--- Найдено отправлений: {len(departures)} ---")
    if departures:
        # Выводим только последние N для краткости в тесте
        for flight in departures[-LAST_FLIGHTS_COUNT:]:
             print(f"  Время: {flight['time']}, Поезд: {flight['train']}, Маршрут: {flight['route']}")
        if len(departures) > LAST_FLIGHTS_COUNT:
            print("  ...") # Показываем, что есть еще рейсы
    else:
        print("  (Нет данных об отправлении)")

    print("\n" + "-" * 30)
    print("Тест парсера завершен.")
    print("-" * 30)

# --- END OF FILE RZD.py ---