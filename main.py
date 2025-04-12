import logging
import os
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
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
GEOAPIFY_API_KEY = "8259951e9fb5448fb2a04a11629d1085"
OPENAI_API_KEY = "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"

# --- Инициализация OpenAI ---
openai_enabled = False
if OPENAI_API_KEY and OPENAI_API_KEY != "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":
    try:
        openai.api_key = OPENAI_API_KEY
        openai_enabled = True
        logger.info("OpenAI API ключ найден и установлен.")
    except Exception as e:
        logger.error(f"Ошибка инициализации OpenAI: {e}")
else:
    logger.warning("\n!!! ВНИМАНИЕ: OpenAI API Ключ не установлен !!!\n")

# Координаты Сочи и параметры поиска
SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

# Категории для выбора
CATEGORIES = {
    "Природа и парки": "natural,leisure.park",
    "Гастрономия (Кафе, Рестораны)": "catering.restaurant,catering.cafe,catering.fast_food",
    "Пляжи": "beach",
    "Горы и треккинг": "natural.mountain_peak,tourism.attraction",
    "Спорт и фитнес": "sport,leisure.fitness_centre",
    "Культура и история": "tourism.attraction,historic,entertainment.museum,building.historic",
    "Развлечения и ночная жизнь": "entertainment,nightlife",
    "Туристические объекты": "tourism",
}

# Функция для получения персональных рекомендаций от LLM
def get_llm_recommendations(interests_list):
    if not openai_enabled:
        return "Сервис персональных рекомендаций недоступен (API ключ OpenAI не настроен или недействителен)."
    try:
        interests_str = ", ".join(interests_list)
        prompt = (
            f"Я планирую поездку в Сочи, Россия, и мои интересы включают: {interests_str}. "
            f"Предложи, какие места мне стоит посетить, и дай краткое описание (2-3 предложения на место). "
            f"Укажи не более 3 мест, чтобы ответ был лаконичным."
        )
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Ты эксперт по путешествиям, знающий Сочи."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {e}")
        return "Не удалось получить рекомендации из-за ошибки сервиса."

# Функция для запроса мест к Geoapify
def search_places(selected_keys):
    geoapify_categories = set()
    for key in selected_keys:
        if key in CATEGORIES:
            codes = CATEGORIES[key].split(',')
            geoapify_categories.update(c.strip() for c in codes)

    if not geoapify_categories:
        return None, "Не удалось найти коды Geoapify для выбранных категорий."

    api_params = {
        'categories': ",".join(geoapify_categories),
        'filter': f"circle:{SOCHI_LON},{SOCHI_LAT},{SEARCH_RADIUS_METERS}",
        'bias': f"proximity:{SOCHI_LON},{SOCHI_LAT}",
        'limit': RESULT_LIMIT,
        'apiKey': GEOAPIFY_API_KEY
    }
    api_url = "https://api.geoapify.com/v2/places"
    found_places = []
    error_message = None

    try:
        response = requests.get(api_url, params=api_params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('features'):
            for feature in data['features']:
                properties = feature.get('properties', {})
                name = properties.get('name')
                lon = properties.get('lon')
                lat = properties.get('lat')
                address = properties.get('formatted', '')
                place_categories = properties.get('categories', [])

                if name and lon and lat:
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
            error_message = f"По вашему запросу ({', '.join(selected_keys)}) ничего не найдено в районе Сочи."

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Geoapify API: {e}")
        error_message = f"Не удалось получить данные от Geoapify. Ошибка: {e}"
        found_places = []
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        error_message = f"Произошла внутренняя ошибка: {e}"
        found_places = []

    return found_places, error_message

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categories_list = "\n".join([f"- {cat}" for cat in CATEGORIES.keys()])
    await update.message.reply_text(
        f"Привет! Я бот, который поможет найти интересные места в Сочи. "
        f"Напиши категории, которые тебя интересуют, через запятую (например: Природа и парки, Пляжи, Гастрономия). "
        f"Доступные категории:\n{categories_list}"
    )

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    logger.info(f"Получено сообщение: '{text}'")
    user_id = update.message.from_user.id

    try:
        # Ожидаем категории, разделённые запятыми
        selected_categories = [cat.strip() for cat in text.split(',')]
        valid_categories = [cat for cat in selected_categories if cat in CATEGORIES]

        if not valid_categories:
            categories_list = "\n".join([f"- {cat}" for cat in CATEGORIES.keys()])
            await update.message.reply_text(
                f"Пожалуйста, выбери хотя бы одну правильную категорию. Доступные категории:\n{categories_list}"
            )
            return

        # Поиск мест через Geoapify
        places, error_message = search_places(valid_categories)
        response = f"Результаты для категорий: {', '.join(valid_categories)}\n\n"

        if error_message and not places:
            await update.message.reply_text(error_message)
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
        llm_recommendations = get_llm_recommendations(valid_categories)
        response += f"\nПерсональные рекомендации:\n{llm_recommendations}"

        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Убедись, что категории указаны правильно, например: Природа и парки, Пляжи."
        )

# Главная функция
def main():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    if not GEOAPIFY_API_KEY or GEOAPIFY_API_KEY == "YOUR_API_KEY":
        logger.error("\n!!! ВНИМАНИЕ: Geoapify API Ключ не установлен !!!\n")
    else:
        main()