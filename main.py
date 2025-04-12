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
import openai

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен вашего бота
TOKEN = "8071128622:AAFgeGieQRDNRxKTONRf52wm-RP4Z9aIvA4"

# --- КОНФИГУРАЦИЯ ---
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "da31de3622fc4ee2a0112ab2f28391aa")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY",
                                "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")

# --- Инициализация OpenAI ---
openai_enabled = False
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        openai_enabled = True
        logger.info("OpenAI API ключ найден и клиент инициализирован.")
    except Exception as e:
        logger.error(f"Ошибка инициализации OpenAI: {e}")
else:
    logger.warning("\n!!! ВНИМАНИЕ: OpenAI API Ключ не установлен или недействителен !!!\n")

# Координаты Сочи и параметры поиска
SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

# Категории для выбора (обновлены в соответствии с Flask-приложением)
CATEGORIES = {
    "Природа и парки": "natural,leisure.park",
    "Заведения": "catering.restaurant,catering.cafe,catering.fast_food",
    "Пляжи": "beach",
    "Отели и гостиницы": "accommodation.hotel,accommodation.guest_house",
    "Театры и музеи": "entertainment.culture.theatre,entertainment.culture.gallery",
    "Океанариум и Дельфинарий": "entertainment.aquarium",
    "Сувениры": "commercial.gift_and_souvenir",
    "Туристические объекты": "tourism",
}


# Функция для получения персональных рекомендаций от LLM (перенесена из Flask с адаптацией)
def get_llm_recommendations(interests_list):
    if not openai_client:
        return "Сервис персональных рекомендаций недоступен (клиент OpenAI не инициализирован)."

    interests_str = ", ".join(interests_list)
    prompt = (
        f"Сгенерируй краткие и полезные туристические рекомендации для туриста из Ирана, "
        f"посещающего Сочи и интересующегося следующими категориями: {interests_str}. "
        f"Учти возможные культурные особенности (например, халяльная еда, если релевантно категории 'Гастрономия', "
        f"места для семейного отдыха). Дай 3-5 конкретных советов или предложений по активностям/местам, "
        f"связанным с выбранными интересами. Ответ должен быть на русском языке."
        f"Не включай в ответ приветствия или завершающие фразы, только сами рекомендации списком или абзацами."
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  # Используем gpt-3.5-turbo, как в Flask
            messages=[
                {"role": "system", "content": "Ты - полезный туристический ассистент."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        recommendation = response.choices[0].message.content.strip()
        if not recommendation:
            logger.warning("OpenAI вернул пустой ответ.")
            return "Не удалось получить конкретные рекомендации от AI."
        return recommendation
    except openai.AuthenticationError as e:
        logger.error(f"Ошибка аутентификации OpenAI: {e}")
        return "Сервис персональных рекомендаций временно недоступен из-за проблемы с API ключом OpenAI."
    except openai.RateLimitError as e:
        logger.error(f"Ошибка лимита запросов OpenAI: {e}")
        return "Сервис персональных рекомендаций временно недоступен из-за превышения лимита запросов к OpenAI."
    except openai.APITimeoutError as e:
        logger.error(f"Таймаут запроса к OpenAI: {e}")
        return "Сервис персональных рекомендаций не ответил вовремя."
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе к OpenAI API: {e}")
        return f"Не удалось сгенерировать рекомендации из-за ошибки OpenAI: {e}"


# Функция для запроса мест к Geoapify (перенесена из Flask с улучшенной обработкой ошибок)
def search_places(selected_keys):
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
        logger.info(f"Запрос к Geoapify с параметрами: {api_params}")
        response = requests.get(api_url, params=api_params, timeout=20)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Ответ от Geoapify получен. Количество 'features': {len(data.get('features', []))}")

        if data.get('features'):
            for feature in data['features']:
                properties = feature.get('properties', {})
                name = properties.get('name')
                lon = properties.get('lon')
                lat = properties.get('lat')
                if name and lon is not None and lat is not None:
                    address = properties.get('formatted', 'Адрес не указан')
                    place_categories = properties.get('categories', [])
                    map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                    found_places.append({
                        'name': name,
                        'lat': lat,
                        'lon': lon,
                        'map_link': map_link,
                        'address': address,
                        'place_categories': place_categories,
                    })
                else:
                    logger.warning(f"Пропущено место без имени или координат: {properties}")

        if not found_places:
            selected_names = ", ".join(selected_keys)
            error_message = f"По вашему запросу ({selected_names}) ничего не найдено в окрестностях Сочи в радиусе {SEARCH_RADIUS_METERS / 1000} км."

    except requests.exceptions.Timeout:
        logger.error("Ошибка: Запрос к Geoapify API превысил таймаут.")
        error_message = "Не удалось получить данные от Geoapify: сервер не ответил вовремя."
    except requests.exceptions.HTTPError as e:
        logger.error(f"Ошибка HTTP при запросе к Geoapify API: {e.response.status_code} {e.response.text}")
        error_message = f"Ошибка при обращении к сервису поиска мест ({e.response.status_code}). Возможно, проблема с API ключом Geoapify или параметрами запроса."
        if e.response.status_code == 401:
            error_message += " Пожалуйста, проверьте ваш Geoapify API ключ."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Geoapify API: {e}")
        error_message = f"Не удалось подключиться к сервису поиска мест Geoapify. Проверьте интернет-соединение. Ошибка: {e}"
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке данных Geoapify: {e}")
        error_message = f"Произошла внутренняя ошибка сервера при обработке данных: {e}"

    return found_places, error_message


# Команда /start (с добавлением кнопок для выбора категорий)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаём интерактивные кнопки для категорий
    keyboard = []
    for category in CATEGORIES.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f"category_{category}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот, который поможет найти интересные места в Сочи.\n"
        "Выбери категории, которые тебя интересуют, нажав на кнопки ниже.\n"
        "После выбора всех категорий нажми 'Готово'.",
        reply_markup=reply_markup
    )


# Обработчик нажатий на кнопки категорий
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    if "selected_categories" not in user_data:
        user_data["selected_categories"] = []

    callback_data = query.data
    if callback_data.startswith("category_"):
        category = callback_data[len("category_"):]
        if category in user_data["selected_categories"]:
            user_data["selected_categories"].remove(category)
            await query.message.reply_text(f"Категория '{category}' удалена из выбора.")
        else:
            user_data["selected_categories"].append(category)
            await query.message.reply_text(f"Категория '{category}' добавлена в выбор.")

        # Обновляем клавиатуру с кнопками
        keyboard = []
        for cat in CATEGORIES.keys():
            prefix = "✅ " if cat in user_data["selected_categories"] else ""
            keyboard.append([InlineKeyboardButton(f"{prefix}{cat}", callback_data=f"category_{cat}")])
        keyboard.append([InlineKeyboardButton("Готово", callback_data="done")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_reply_markup(reply_markup=reply_markup)

    elif callback_data == "done":
        selected_categories = user_data.get("selected_categories", [])
        if not selected_categories:
            await query.message.reply_text("Пожалуйста, выбери хотя бы одну категорию.")
            return

        # Поиск мест через Geoapify
        places, error_message = search_places(selected_categories)
        response = f"Результаты для категорий: {', '.join(selected_categories)}\n\n"

        if error_message and not places:
            await query.message.reply_text(error_message)
            return

        if places:
            for place in places[:5]:  # Ограничиваем до 5 мест для лаконичности
                response += (
                    f"📍 {place['name']}\n"
                    f"Адрес: {place['address']}\n"
                    f"Карта: {place['map_link']}\n"
                    f"---\n"
                )
        else:
            response += "Места не найдены.\n"

        # Получение рекомендаций от LLM
        llm_recommendations = get_llm_recommendations(selected_categories)
        response += f"\nПерсональные рекомендации:\n{llm_recommendations}"

        await query.message.reply_text(response)
        # Очищаем выбор пользователя
        user_data["selected_categories"] = []


# Обработка текстовых сообщений (для обратной совместимости)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    logger.info(f"Получено сообщение: '{text}'")

    selected_categories = [cat.strip() for cat in text.split(',')]
    valid_categories = [cat for cat in selected_categories if cat in CATEGORIES]

    if not valid_categories:
        categories_list = "\n".join([f"- {cat}" for cat in CATEGORIES.keys()])
        await update.message.reply_text(
            f"Пожалуйста, выбери хотя бы одну правильную категорию. Доступные категории:\n{categories_list}\n"
            "Или используй команду /start для выбора категорий через кнопки."
        )
        return

    # Поиск мест через Geoapify
    places, error_message = search_places(valid_categories)
    response = f"Результаты для категорий: {', '.join(valid_categories)}\n\n"

    if error_message and not places:
        await update.message.reply_text(error_message)
        return

    if places:
        for place in places[:5]:
            response += (
                f"📍 {place['name']}\n"
                f"Адрес: {place['address']}\n"
                f"Карта: {place['map_link']}\n"
                f"---\n"
            )
    else:
        response += "Места не найдены.\n"

    # Получение рекомендаций от LLM
    llm_recommendations = get_llm_recommendations(valid_categories)
    response += f"\nПерсональные рекомендации:\n{llm_recommendations}"

    await update.message.reply_text(response)


# Главная функция
def main():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    valid_geoapify = GEOAPIFY_API_KEY and GEOAPIFY_API_KEY != "YOUR_API_KEY" and len(GEOAPIFY_API_KEY) > 10
    valid_openai = openai_client is not None

    if not valid_geoapify:
        logger.error("\n!!! ВНИМАНИЕ: Geoapify API Ключ не установлен или недействителен !!!\n")
    if not valid_openai:
        logger.error("\n!!! ВНИМАНИЕ: Клиент OpenAI не был успешно инициализирован !!!\n")

    if valid_geoapify:
        main()
    else:
        logger.error("\nБот не может быть запущен без действительного Geoapify API ключа.\n")