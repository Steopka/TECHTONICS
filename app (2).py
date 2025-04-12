import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
import openai
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "37ed2aaf4267415eae06a898624632f7")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
openai_enabled = False
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        openai_client.models.list()
        openai_enabled = True
        print("OpenAI API ключ найден и клиент инициализирован.")
    except Exception as e:
        print(f"Ошибка инициализации OpenAI или проверки ключа: {e}")
        print("OpenAI будет отключен.")
else:
    print("\n!!! ВНИМАНИЕ: OpenAI API Ключ не установлен или недействителен !!!\n")
    print("Сервис персональных рекомендаций будет недоступен.")

SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

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

def get_llm_recommendations(interests_list):
    """Генерирует персональные рекомендации с помощью OpenAI."""
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
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - полезный туристический ассистент."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        recommendation = response.choices[0].message.content.strip()
        if not recommendation:
            print("OpenAI вернул пустой ответ.")
            return "Не удалось получить конкретные рекомендации от AI."
        return recommendation
    except openai.AuthenticationError as e:
         print(f"Ошибка аутентификации OpenAI: {e}. Проверьте API ключ.")
         return "Сервис персональных рекомендаций временно недоступен из-за проблемы с API ключом OpenAI."
    except openai.RateLimitError as e:
         print(f"Ошибка лимита запросов OpenAI: {e}")
         return "Сервис персональных рекомендаций временно недоступен из-за превышения лимита запросов к OpenAI."
    except openai.APITimeoutError as e:
         print(f"Таймаут запроса к OpenAI: {e}")
         return "Сервис персональных рекомендаций не ответил вовремя."
    except Exception as e:
        print(f"Неожиданная ошибка при запросе к OpenAI API: {e}")
        return f"Не удалось сгенерировать рекомендации из-за ошибки OpenAI: {e}"

@app.route('/')
def index():
    """Экран 1: Отображение формы выбора категорий."""
    return render_template('index.html', categories=CATEGORIES)
@app.route('/search')
def search_places():
    """
    Экран 2 (обработка): Запрос к Geoapify, запрос к LLM.
    Экран 3 (отображение): Показ результатов и рекомендаций.
    """
    selected_keys = request.args.getlist('category')
    if not selected_keys:
        flash("Пожалуйста, выберите хотя бы одну категорию.", "warning")
        return redirect(url_for('index'))
    geoapify_categories_set = set()
    for key in selected_keys:
        if key in CATEGORIES:
            codes = CATEGORIES[key].split(',')
            geoapify_categories_set.update(c.strip() for c in codes if c.strip())
    if not geoapify_categories_set:
        flash("Не удалось найти коды Geoapify для выбранных категорий.", "danger")
        return redirect(url_for('index'))
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
        print(f"Запрос к Geoapify с параметрами: {api_params}")
        response = requests.get(api_url, params=api_params, timeout=20)
        response.raise_for_status()
        data = response.json()
        print(f"Ответ от Geoapify получен. Количество 'features': {len(data.get('features', []))}")

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
                    print(f"Пропущено место без имени или координат: {properties}")
        if not found_places:
             selected_names = ", ".join(selected_keys)
             flash(f"По вашему запросу ({selected_names}) ничего не найдено в окрестностях Сочи в радиусе {SEARCH_RADIUS_METERS/1000} км.", "info")
    except requests.exceptions.Timeout:
        print("Ошибка: Запрос к Geoapify API превысил таймаут.")
        error_message = "Не удалось получить данные от Geoapify: сервер не ответил вовремя."
    except requests.exceptions.HTTPError as e:
        print(f"Ошибка HTTP при запросе к Geoapify API: {e.response.status_code} {e.response.text}")
        error_message = f"Ошибка при обращении к сервису поиска мест ({e.response.status_code}). Возможно, проблема с API ключом Geoapify или параметрами запроса."
        if e.response.status_code == 401:
             error_message += " Пожалуйста, проверьте ваш Geoapify API ключ."
    except requests.exceptions.RequestException as e:
        print(f"Ошибка запроса к Geoapify API: {e}")
        error_message = f"Не удалось подключиться к сервису поиска мест Geoapify. Проверьте интернет-соединение. Ошибка: {e}"
    except Exception as e:
        import traceback
        print(f"Неожиданная ошибка при обработке данных Geoapify: {e}")
        print(traceback.format_exc())
        error_message = f"Произошла внутренняя ошибка сервера при обработке данных: {e}"

    llm_recommendations = ""
    if not error_message:
        try:
            llm_recommendations = get_llm_recommendations(selected_keys)
        except Exception as e:
            print(f"Ошибка при вызове get_llm_recommendations: {e}")
            flash("Не удалось сгенерировать персональные рекомендации.", "warning")

    return render_template('results.html',
                           places=found_places,
                           error=error_message,
                           selected_categories=selected_keys,
                           llm_recommendations=llm_recommendations)
@app.errorhandler(404)
def page_not_found(e):
    """Отображает 404 страницу."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Обработка внутренних ошибок сервера."""
    print(f"Internal Server Error: {e}")
    return "Произошла внутренняя ошибка сервера.", 500

if __name__ == '__main__':
    valid_geoapify = GEOAPIFY_API_KEY and GEOAPIFY_API_KEY != "YOUR_API_KEY" and len(GEOAPIFY_API_KEY) > 10
    valid_openai = openai_client is not None

    if not valid_geoapify:
         print("\n!!! ВНИМАНИЕ: Geoapify API Ключ не установлен или недействителен...")

    if not valid_openai:
         print("\n!!! ВНИМАНИЕ: Клиент OpenAI не был успешно инициализирован.")
         print("Это может быть связано с отсутствующим/неверным ключом API или ошибкой при инициализации.")
         print("Функция персональных рекомендаций будет недоступна.")

    if valid_geoapify:
        print("Geoapify ключ найден. Запуск Flask приложения...")
        app.run(host='127.0.0.1', port=5000, debug=True)
    else:
        print("\nПриложение не может быть запущено без действительного Geoapify API ключа.")
        print("Пожалуйста, исправьте конфигурацию и перезапустите.")