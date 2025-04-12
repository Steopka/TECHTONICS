# -*- coding: utf-8 -*-
import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен вашего бота
TOKEN = "8071128622:AAFgeGieQRDNRxKTONRf52wm-RP4Z9aIvA4"

# --- КОНФИГУРАЦИЯ ---
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "da31de3622fc4ee2a0112ab2f28391aa")

# Координаты Сочи и параметры поиска
SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

# Категории для выбора
CATEGORIES = {
    "Природа и парки": "natural,leisure.park",
    "Заведения": "catering.restaurant,catering.cafe,catering.fast_food",
    "Пляжи": "beach",
    "Отели и гостиницы": "accommodation.hotel,accommodation.guest_house",
    "Театры и музеи": "entertainment.culture.theatre,entertainment.culture.gallery",
    "Океанариум и Дельфинарий": "entertainment.aquarium",
    "Сувениры": "commercial.gift_and_souvenir",
    "Туристические объекты": "tourism",
    "Билеты РЖД": "rzd_tickets",
}

# Станции для РЖД
STATIONS = {
    "Сочи": "2004000",
    "Москва": "2000000",
    "Санкт-Петербург": "2006000",
    "Краснодар": "2034000",
    "Ростов-на-Дону": "2024000",
}


# Функция для запроса билетов РЖД (заглушка)
def get_rzd_tickets(from_station, to_station, date):
    try:
        # Примерные данные билетов
        tickets = [
            {
                "train": "044С",
                "departure": f"{date} 08:30",
                "arrival": f"{date} 20:45",
                "duration": "12ч 15м",
                "classes": {
                    "Плацкарт": {"price": 2500, "seats": 15},
                    "Купе": {"price": 4500, "seats": 8}
                }
            },
            {
                "train": "104В",
                "departure": f"{date} 18:15",
                "arrival": f"{date} 06:30+1",
                "duration": "12ч 15м",
                "classes": {
                    "Плацкарт": {"price": 2700, "seats": 10},
                    "Купе": {"price": 4900, "seats": 5},
                    "СВ": {"price": 7500, "seats": 3}
                }
            }
        ]
        return tickets, None
    except Exception as e:
        logger.error(f"Ошибка при запросе билетов РЖД: {e}")
        return None, f"Ошибка при получении данных о билетах: {e}"


# Функция для поиска мест через Geoapify
def search_places(selected_keys):
    if "rzd_tickets" in selected_keys:
        return [], None

    geoapify_categories_set = set()
    for key in selected_keys:
        if key in CATEGORIES:
            codes = CATEGORIES[key].split(',')
            geoapify_categories_set.update(c.strip() for c in codes if c.strip())

    if not geoapify_categories_set:
        return None, "Не удалось найти коды Geoapify для выбранных категорий."

    api_params = {
        'categories': ",".join(geoapify_categories_set),
        'filter': f"circle:{SOCHI_LON},{SOCHI_LAT},{SEARCH_RADIUS_METERS}",
        'bias': f"proximity:{SOCHI_LON},{SOCHI_LAT}",
        'limit': RESULT_LIMIT,
        'apiKey': GEOAPIFY_API_KEY
    }

    api_url = "https://api.geoapify.com/v2/places"
    found_places = []
    error_message = None

    try:
        response = requests.get(api_url, params=api_params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if data.get('features'):
            for feature in data['features']:
                properties = feature.get('properties', {})
                name = properties.get('name')
                lon = properties.get('lon')
                lat = properties.get('lat')
                if name and lon is not None and lat is not None:
                    address = properties.get('formatted', 'Адрес не указан')
                    map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                    found_places.append({
                        'name': name,
                        'address': address,
                        'map_link': map_link,
                    })

        if not found_places:
            selected_names = ", ".join(selected_keys)
            error_message = f"По вашему запросу ({selected_names}) ничего не найдено."

    except requests.exceptions.Timeout:
        error_message = "Не удалось получить данные: сервер не ответил вовремя."
    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка подключения: {e}"
    except Exception as e:
        error_message = f"Произошла ошибка: {e}"

    return found_places, error_message


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(cat, callback_data=f"category_{cat}")]
        for cat in CATEGORIES.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! Я бот для поиска мест в Сочи и покупки билетов РЖД.\n"
        "Выбери интересующие категории:",
        reply_markup=reply_markup
    )


# Обработчик кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    if "selected_categories" not in user_data:
        user_data["selected_categories"] = []

    callback_data = query.data

    if callback_data.startswith("category_"):
        category = callback_data[9:]
        if category in user_data["selected_categories"]:
            user_data["selected_categories"].remove(category)
            await query.edit_message_text(f"Категория '{category}' удалена.")
        else:
            user_data["selected_categories"].append(category)
            await query.edit_message_text(f"Категория '{category}' добавлена.")

        # Обновляем клавиатуру
        keyboard = [
            [InlineKeyboardButton(
                f"{'✅ ' if cat in user_data['selected_categories'] else ''}{cat}",
                callback_data=f"category_{cat}"
            )]
            for cat in CATEGORIES.keys()
        ]
        keyboard.append([InlineKeyboardButton("Готово", callback_data="done")])

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif callback_data == "done":
        selected = user_data.get("selected_categories", [])
        if not selected:
            await query.message.reply_text("Пожалуйста, выберите категории.")
            return

        if "Билеты РЖД" in selected:
            keyboard = [
                [InlineKeyboardButton("Сочи - Москва", callback_data="route_sochi_moscow")],
                [InlineKeyboardButton("Сочи - СПб", callback_data="route_sochi_spb")],
                [InlineKeyboardButton("Сочи - Краснодар", callback_data="route_sochi_krasnodar")],
                [InlineKeyboardButton("Другой маршрут", callback_data="route_custom")],
            ]
            await query.message.reply_text(
                "Выберите маршрут:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            places, error = search_places(selected)
            response = f"Результаты по категориям: {', '.join(selected)}\n\n"

            if error:
                response += error
            elif places:
                for place in places[:5]:
                    response += (
                        f"📍 {place['name']}\n"
                        f"Адрес: {place['address']}\n"
                        f"Карта: {place['map_link']}\n\n"
                    )
            else:
                response += "Ничего не найдено."

            await query.message.reply_text(response)
            user_data["selected_categories"] = []

    elif callback_data.startswith("route_"):
        route = callback_data[6:]

        if route == "sochi_moscow":
            from_st, to_st = "Сочи", "Москва"
        elif route == "sochi_spb":
            from_st, to_st = "Сочи", "Санкт-Петербург"
        elif route == "sochi_krasnodar":
            from_st, to_st = "Сочи", "Краснодар"
        else:
            await query.message.reply_text("Введите маршрут в формате: Город - Город")
            return

        date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
        tickets, error = get_rzd_tickets(from_st, to_st, date)

        if error:
            await query.message.reply_text(error)
            return

        if not tickets:
            await query.message.reply_text(f"На {date} нет поездов {from_st} - {to_st}.")
            return

        response = f"🚂 Поезда {from_st} - {to_st} на {date}:\n\n"
        for ticket in tickets:
            response += (
                f"Поезд {ticket['train']}\n"
                f"Отправление: {ticket['departure']}\n"
                f"Прибытие: {ticket['arrival']}\n"
                f"В пути: {ticket['duration']}\n"
            )
            for cls, info in ticket['classes'].items():
                response += f"- {cls}: {info['price']} руб. (мест: {info['seats']})\n"
            response += "\n"

        response += "🔗 Купить билеты: https://pass.rzd.ru"
        await query.message.reply_text(response)


# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Обработка запроса билетов РЖД
    if " - " in text and any(word in text.lower() for word in ["билет", "поезд", "ржд"]):
        parts = [p.strip() for p in text.split(" - ") if p.strip()]
        if len(parts) == 2:
            from_st, to_st = parts
            date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
            tickets, error = get_rzd_tickets(from_st, to_st, date)

            if error:
                await update.message.reply_text(error)
                return

            if not tickets:
                await update.message.reply_text(f"На {date} нет поездов {from_st} - {to_st}.")
                return

            response = f"🚂 Поезда {from_st} - {to_st} на {date}:\n\n"
            for ticket in tickets:
                response += (
                    f"Поезд {ticket['train']}\n"
                    f"Отправление: {ticket['departure']}\n"
                    f"Прибытие: {ticket['arrival']}\n"
                    f"В пути: {ticket['duration']}\n"
                )
                for cls, info in ticket['classes'].items():
                    response += f"- {cls}: {info['price']} руб. (мест: {info['seats']})\n"
                response += "\n"

            response += "🔗 Купить билеты: https://pass.rzd.ru"
            await update.message.reply_text(response)
            return

    # Обработка обычных категорий
    selected = [cat.strip() for cat in text.split(',') if cat.strip() in CATEGORIES]
    if not selected:
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES.keys())
        await update.message.reply_text(
            f"Доступные категории:\n{categories_list}\n"
            "Или используйте /start для выбора."
        )
        return

    places, error = search_places(selected)
    response = f"Результаты по категориям: {', '.join(selected)}\n\n"

    if error:
        response += error
    elif places:
        for place in places[:5]:
            response += (
                f"📍 {place['name']}\n"
                f"Адрес: {place['address']}\n"
                f"Карта: {place['map_link']}\n\n"
            )
    else:
        response += "Ничего не найдено."

    await update.message.reply_text(response)


# Главная функция
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    if GEOAPIFY_API_KEY and GEOAPIFY_API_KEY != "YOUR_API_KEY":
        main()
    else:
        logger.error("Ошибка: Неверный Geoapify API ключ!")