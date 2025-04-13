# --- START OF FILE app.py ---

import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, g # Added session, g
import openai
import traceback
import logging

# --- Import RZD parser function ---
try:
    from RZD import get_sochi_schedule
    rzd_parser_available = True
    print("Модуль парсера RZD успешно импортирован.")
except ImportError:
    print("ПРЕДУПРЕЖДЕНИЕ: Не удалось импортировать модуль RZD.py. Функциональность расписания поездов будет недоступна.")
    rzd_parser_available = False
    def get_sochi_schedule():
        return [], [], "Модуль парсера RZD не найден."

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-me') # IMPORTANT: Set a proper secret key

# --- API Keys ---
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "1dd336f8ea20465fb15f85bdf78df7e6") # Use your key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", None)

# --- OpenAI Initialization ---
# ... (OpenAI initialization code remains the same) ...
openai_enabled = False
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-"):
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        openai_client.models.list()
        openai_enabled = True
        logger.info("OpenAI API ключ найден и клиент инициализирован.")
    except openai.AuthenticationError:
        logger.warning("Ошибка аутентификации OpenAI: Неверный API ключ.")
        logger.warning("Сервис персональных рекомендаций будет недоступен.")
    except Exception as e:
        logger.error(f"Ошибка инициализации OpenAI или проверки ключа: {e}")
        logger.warning("OpenAI будет отключен.")
else:
    logger.warning("!!! ВНИМАНИЕ: OpenAI API Ключ не установлен или недействителен !!!")
    logger.warning("Сервис персональных рекомендаций будет недоступен.")


# --- Constants ---
SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

# --- SUPPORTED LANGUAGES ---
SUPPORTED_LANGUAGES = ['ru', 'en', 'fa']
DEFAULT_LANGUAGE = 'ru'

# --- Translations ---
# Categories are now language-dependent
CATEGORIES = {
    "ru": {
        "Природа и парки": "natural,leisure.park",
        "Заведения": "catering.restaurant,catering.cafe,catering.fast_food",
        "Пляжи": "beach",
        "Отели": "accommodation.hotel,accommodation.guest_house",
        "Музеи": "entertainment.culture.theatre,entertainment.culture.gallery",
        "Океанариум и Дельфинарий": "entertainment.aquarium",
        "Сувениры": "commercial.gift_and_souvenir",
        "Туристические объекты": "tourism",
        "Железные дороги": "rzd_schedule", # Special key
    },
    "en": {
        "Nature and Parks": "natural,leisure.park",
        "Restaurants & Cafes": "catering.restaurant,catering.cafe,catering.fast_food",
        "Beaches": "beach",
        "Hotels & Guesthouses": "accommodation.hotel,accommodation.guest_house",
        "Theaters & Museums": "entertainment.culture.theatre,entertainment.culture.gallery",
        "Aquarium & Dolphinarium": "entertainment.aquarium",
        "Souvenirs": "commercial.gift_and_souvenir",
        "Tourist Attractions": "tourism",
        "Railways (Schedule)": "rzd_schedule", # Special key
    },
    "fa": {
        "طبیعت و پارک‌ها": "natural,leisure.park",
        "رستوران‌ها و کافه‌ها": "catering.restaurant,catering.cafe,catering.fast_food",
        "سواحل": "beach",
        "هتل‌ها و مهمان‌خانه‌ها": "accommodation.hotel,accommodation.guest_house",
        "تئاترها و موزه‌ها": "entertainment.culture.theatre,entertainment.culture.gallery",
        "آکواریوم و دلفیناریوم": "entertainment.aquarium",
        "سوغاتی‌ها": "commercial.gift_and_souvenir",
        "جاذبه‌های گردشگری": "tourism",
        "راه‌آهن (برنامه حرکت)": "rzd_schedule", # Special key
    },
}

# Text translations
LANGUAGES = {
    "ru": {
        "page_title_index": "Достопримечательности Сочи - Выбор категорий",
        "page_title_results": "Результаты поиска достопримечательностей",
        "h1_index": "Выберите интересующие вас категории в Сочи",
        "h1_results": "Результаты поиска в Сочи",
        "your_choice": "Ваш выбор",
        "find_places": "Найти места",
        "back_link": "← Вернуться к выбору категорий",
        "found_places_count": "Найденные места ({count}):",
        "error_prefix": "Ошибка",
        "info_prefix": "Информация",
        "warning_prefix": "Внимание",
        "search_error": "Ошибка поиска мест", # Generic search error for display
        "rzd_schedule_title": "Расписание поездов (Сочи) на сегодня",
        "rzd_arrivals_title": "Прибытие",
        "rzd_departures_title": "Отправление",
        "rzd_arrivals_count": "Прибытие ({count})",
        "rzd_departures_count": "Отправление ({count})",
        "rzd_train_label": "Поезд",
        "rzd_route_label": "Маршрут",
        "rzd_no_arrivals": "Нет данных о прибытии на сегодня.",
        "rzd_no_departures": "Нет данных об отправлении на сегодня.",
        "rzd_fetch_error": "Не удалось получить расписание поездов",
        "rzd_module_error": "Функциональность расписания поездов недоступна (модуль RZD.py не найден).",
        "rzd_more_trains": "... и еще {count}",
        "llm_recommendations_title": "Персональные рекомендации", # Title made generic
        "llm_recommendations_title_iran": "Персональные рекомендации для туриста из Ирана:", # Specific example
        "llm_result_error_text": "Не удалось получить персональные рекомендации в этот раз.",
        "no_selection_warning": "Пожалуйста, выберите хотя бы одну категорию.",
        "no_geoapify_codes_error": "Не удалось найти коды Geoapify для выбранных категорий.",
        "no_results_info": "К сожалению, по вашему запросу ({categories}) в указанном районе ничего не найдено.",
        "geoapify_timeout_error": "Не удалось получить данные от сервиса поиска мест: превышено время ожидания.",
        "geoapify_http_error": "Ошибка при обращении к сервису поиска мест (код: {status_code}).",
        "geoapify_http_error_400": "Ошибка в параметрах запроса к сервису поиска мест ({status_code}). Проверьте выбранные категории.",
        "geoapify_http_error_401": "Ошибка авторизации при доступе к сервису поиска мест. Проверьте API ключ Geoapify.",
        "geoapify_http_error_429": "Превышен лимит запросов к сервису поиска мест. Попробуйте позже.",
        "geoapify_connection_error": "Не удалось подключиться к сервису поиска мест Geoapify.",
        "geoapify_generic_error": "Произошла внутренняя ошибка сервера при обработке данных поиска.",
        "address_not_specified": "Адрес не указан",
        "show_on_map": "Показать на карте (OpenStreetMap)",
        "place_type": "Тип",
        "llm_unavailable_no_client": "Сервис персональных рекомендаций недоступен (OpenAI не настроен).",
        "llm_openai_auth_error": "Сервис персональных рекомендаций временно недоступен из-за проблемы с доступом к AI.",
        "llm_openai_rate_limit_error": "Сервис персональных рекомендаций временно недоступен из-за высокой нагрузки.",
        "llm_openai_timeout_error": "Сервис персональных рекомендаций не ответил вовремя.",
        "llm_openai_generic_error": "Не удалось сгенерировать рекомендации из-за внутренней ошибки сервиса.",
        "llm_empty_response_error": "Не удалось получить конкретные рекомендации от AI.",
        "page_not_found_title": "Страница не найдена (404)",
        "page_not_found_message": "Страница не найдена (404)",
        "back_to_main": "Вернуться на главную",
        "internal_server_error_message": "Произошла внутренняя ошибка сервера. Пожалуйста, попробуйте позже.",
    },
    "en": {
        "page_title_index": "Sochi Attractions - Select Categories",
        "page_title_results": "Attraction Search Results",
        "h1_index": "Select categories you are interested in in Sochi",
        "h1_results": "Search Results in Sochi",
        "your_choice": "Your choice",
        "find_places": "Find Places",
        "back_link": "← Back to Category Selection",
        "found_places_count": "Places found ({count}):",
        "error_prefix": "Error",
        "info_prefix": "Info",
        "warning_prefix": "Warning",
        "search_error": "Place Search Error",
        "rzd_schedule_title": "Train Schedule (Sochi) for Today",
        "rzd_arrivals_title": "Arrivals",
        "rzd_departures_title": "Departures",
        "rzd_arrivals_count": "Arrivals ({count})",
        "rzd_departures_count": "Departures ({count})",
        "rzd_train_label": "Train",
        "rzd_route_label": "Route",
        "rzd_no_arrivals": "No arrival data for today.",
        "rzd_no_departures": "No departure data for today.",
        "rzd_fetch_error": "Failed to retrieve train schedule",
        "rzd_module_error": "Train schedule functionality is unavailable (RZD.py module not found).",
        "rzd_more_trains": "... and {count} more",
        "llm_recommendations_title": "Personal Recommendations",
        "llm_recommendations_title_iran": "Personal Recommendations for a Tourist from Iran:",
        "llm_result_error_text": "Could not get personal recommendations this time.",
        "no_selection_warning": "Please select at least one category.",
        "no_geoapify_codes_error": "Could not find Geoapify codes for the selected categories.",
        "no_results_info": "Unfortunately, nothing was found for your request ({categories}) in the specified area.",
        "geoapify_timeout_error": "Failed to retrieve data from the place search service: request timed out.",
        "geoapify_http_error": "Error accessing the place search service (code: {status_code}).",
        "geoapify_http_error_400": "Error in request parameters to the place search service ({status_code}). Check the selected categories.",
        "geoapify_http_error_401": "Authorization error accessing the place search service. Check your Geoapify API key.",
        "geoapify_http_error_429": "Request limit exceeded for the place search service. Try again later.",
        "geoapify_connection_error": "Could not connect to the Geoapify place search service.",
        "geoapify_generic_error": "An internal server error occurred while processing search data.",
        "address_not_specified": "Address not specified",
        "show_on_map": "Show on map (OpenStreetMap)",
        "place_type": "Type",
        "llm_unavailable_no_client": "Personal recommendation service unavailable (OpenAI not configured).",
        "llm_openai_auth_error": "Personal recommendation service temporarily unavailable due to an AI access issue.",
        "llm_openai_rate_limit_error": "Personal recommendation service temporarily unavailable due to high load.",
        "llm_openai_timeout_error": "Personal recommendation service did not respond in time.",
        "llm_openai_generic_error": "Could not generate recommendations due to an internal service error.",
        "llm_empty_response_error": "Could not get specific recommendations from AI.",
        "page_not_found_title": "Page Not Found (404)",
        "page_not_found_message": "Page Not Found (404)",
        "back_to_main": "Back to Main Page",
        "internal_server_error_message": "An internal server error occurred. Please try again later.",
    },
    "fa": {
        # --- Farsi Translations (Right-to-Left) ---
        "page_title_index": "جاذبه‌های سوچی - انتخاب دسته‌بندی‌ها",
        "page_title_results": "نتایج جستجوی جاذبه‌ها",
        "h1_index": "دسته‌بندی‌های مورد علاقه خود در سوچی را انتخاب کنید",
        "h1_results": "نتایج جستجو در سوچی",
        "your_choice": "انتخاب شما",
        "find_places": "یافتن مکان‌ها",
        "back_link": "بازگشت به انتخاب دسته‌بندی →", # RTL arrow
        "found_places_count": "مکان‌های یافت شده ({count}):",
        "error_prefix": "خطا",
        "info_prefix": "اطلاعات",
        "warning_prefix": "هشدار",
        "search_error": "خطای جستجوی مکان",
        "rzd_schedule_title": "برنامه حرکت قطارها (سوچی) برای امروز",
        "rzd_arrivals_title": "ورود",
        "rzd_departures_title": "خروج",
        "rzd_arrivals_count": "ورود ({count})",
        "rzd_departures_count": "خروج ({count})",
        "rzd_train_label": "قطار",
        "rzd_route_label": "مسیر",
        "rzd_no_arrivals": "داده‌ای برای ورود امروز موجود نیست.",
        "rzd_no_departures": "داده‌ای برای خروج امروز موجود نیست.",
        "rzd_fetch_error": "دریافت برنامه حرکت قطارها ناموفق بود",
        "rzd_module_error": "عملکرد برنامه حرکت قطارها در دسترس نیست (ماژول RZD.py یافت نشد).",
        "rzd_more_trains": "... و {count} تای دیگر",
        "llm_recommendations_title": "توصیه‌های شخصی",
        "llm_recommendations_title_iran": "توصیه‌های شخصی برای گردشگر از ایران:",
        "llm_result_error_text": "این بار دریافت توصیه‌های شخصی ممکن نبود.",
        "no_selection_warning": "لطفاً حداقل یک دسته‌بندی انتخاب کنید.",
        "no_geoapify_codes_error": "کدهای Geoapify برای دسته‌بندی‌های انتخاب شده یافت نشد.",
        "no_results_info": "متأسفانه، موردی برای درخواست شما ({categories}) در منطقه مشخص شده یافت نشد.",
        "geoapify_timeout_error": "دریافت داده از سرویس جستجوی مکان ناموفق بود: درخواست منقضی شد.",
        "geoapify_http_error": "خطا در دسترسی به سرویس جستجوی مکان (کد: {status_code}).",
        "geoapify_http_error_400": "خطا در پارامترهای درخواست به سرویس جستجوی مکان ({status_code}). دسته‌بندی‌های انتخاب شده را بررسی کنید.",
        "geoapify_http_error_401": "خطای احراز هویت در دسترسی به سرویس جستجوی مکان. کلید API Geoapify خود را بررسی کنید.",
        "geoapify_http_error_429": "تعداد درخواست‌ها به سرویس جستجوی مکان بیش از حد مجاز است. بعداً تلاش کنید.",
        "geoapify_connection_error": "اتصال به سرویس جستجوی مکان Geoapify امکان‌پذیر نیست.",
        "geoapify_generic_error": "یک خطای داخلی سرور هنگام پردازش داده‌های جستجو رخ داد.",
        "address_not_specified": "آدرس مشخص نشده است",
        "show_on_map": "نمایش روی نقشه (OpenStreetMap)",
        "place_type": "نوع",
        "llm_unavailable_no_client": "سرویس توصیه‌های شخصی در دسترس نیست (OpenAI پیکربندی نشده است).",
        "llm_openai_auth_error": "سرویس توصیه‌های شخصی به دلیل مشکل دسترسی به هوش مصنوعی موقتاً در دسترس نیست.",
        "llm_openai_rate_limit_error": "سرویس توصیه‌های شخصی به دلیل بار زیاد موقتاً در دسترس نیست.",
        "llm_openai_timeout_error": "سرویس توصیه‌های شخصی به موقع پاسخ نداد.",
        "llm_openai_generic_error": "به دلیل خطای داخلی سرویس، تولید توصیه‌ها ناموفق بود.",
        "llm_empty_response_error": "دریافت توصیه‌های مشخص از هوش مصنوعی ناموفق بود.",
        "page_not_found_title": "صفحه یافت نشد (۴۰۴)",
        "page_not_found_message": "صفحه یافت نشد (۴۰۴)",
        "back_to_main": "بازگشت به صفحه اصلی",
        "internal_server_error_message": "یک خطای داخلی سرور رخ داد. لطفاً بعداً دوباره تلاش کنید.",
    },
}

LLM_ERROR_MESSAGE_FRAGMENTS = [ # Keep these base fragments for checking
    "Сервис персональных рекомендаций недоступен", "Personal recommendation service unavailable", "سرویس توصیه‌های شخصی در دسترس نیست",
    "Не удалось получить конкретные рекомендации", "Could not get specific recommendations", "دریافت توصیه‌های مشخص از هوش مصنوعی ناموفق بود",
    "проблемы с доступом к AI", "AI access issue", "مشکل دسترسی به هوش مصنوعی",
    "высокой нагрузки", "high load", "بار زیاد",
    "не ответил вовремя", "did not respond in time", "به موقع پاسخ نداد",
    "внутренней ошибки сервиса", "internal service error", "خطای داخلی سرویس",
    "Не удалось сгенерировать рекомендации", "Could not generate recommendations", "تولید توصیه‌ها ناموفق بود"
]


# --- Helper Functions ---

def get_current_language():
    """Gets the current language from request args or session, defaults to DEFAULT_LANGUAGE."""
    lang = request.args.get('lang', session.get('language', DEFAULT_LANGUAGE))
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    session['language'] = lang # Store in session for persistence
    return lang

def _(text_key, **kwargs):
    """Translation helper using the LANGUAGES dictionary."""
    lang = g.get('language', DEFAULT_LANGUAGE)
    # Fallback chain: current lang -> default lang -> key itself
    return LANGUAGES.get(lang, {}).get(text_key, LANGUAGES.get(DEFAULT_LANGUAGE, {}).get(text_key, text_key)).format(**kwargs)

@app.before_request
def before_request():
    """Set language globally for the request using Flask's 'g' object."""
    g.language = get_current_language()
    # Make translation helper available globally in templates via 'g'
    g.translate = _
    # Pass supported languages and current language to g for templates
    g.supported_languages = SUPPORTED_LANGUAGES
    # Determine text direction
    g.text_dir = 'rtl' if g.language == 'fa' else 'ltr'

# --- LLM Recommendation Function ---
def get_llm_recommendations(interests_list, lang_code):
    if not openai_enabled or not openai_client:
         # Use the translation helper now
         return _("llm_unavailable_no_client")

    interests_str = ", ".join(interests_list)
    # Adjust prompt based on language if needed, or specify output language
    # Keeping the main prompt in Russian might be better for model consistency
    # Specify target audience and desired output language
    target_audience = "туриста из Ирана" # Keep this specific for the example prompt
    output_language = "русском"
    if lang_code == 'en':
        output_language = "английском"
        target_audience = "a tourist from Iran" # Or make this dynamic too
    elif lang_code == 'fa':
        output_language = "персидском (фарси)"
        # Target audience translation isn't strictly necessary if prompt is Russian
        # but helps clarify intent
        target_audience = "یک گردشگر از ایران"


    prompt = (
        # The core instructions remain in Russian for potentially better model handling
        f"Сгенерируй краткие и полезные туристические рекомендации для {target_audience}, "
        f"посещающего Сочи и интересующегося следующими категориями: {interests_str}. "
        f"Учти возможные культурные особенности (например, халяльная еда, если релевантно категории 'Заведения' или 'Халяльные рестораны', "
        f"места для семейного отдыха). Дай 3-5 конкретных советов или предложений по активностям/местам, "
        f"связанным с выбранными интересами. "
        # Explicitly state the desired output language
        f"Ответ должен быть на {output_language} языке. "
        f"Не включай в ответ приветствия или завершающие фразы, только сами рекомендации списком или абзацами."
        f"Если выбраны 'Железные дороги (Расписание)', можешь упомянуть удобство поездов."
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - полезный туристический ассистент."}, # Keep system prompt generic maybe
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400 # Slightly increase for potentially longer translated text
        )
        recommendation = response.choices[0].message.content.strip()
        if not recommendation:
            logger.warning("OpenAI вернул пустой ответ.")
            return _("llm_empty_response_error")
        return recommendation
    except openai.AuthenticationError:
         logger.error("Ошибка аутентификации OpenAI.", exc_info=True)
         return _("llm_openai_auth_error")
    except openai.RateLimitError:
         logger.error("Ошибка лимита запросов OpenAI.", exc_info=True)
         return _("llm_openai_rate_limit_error")
    except openai.APITimeoutError:
         logger.error("Таймаут запроса к OpenAI.", exc_info=True)
         return _("llm_openai_timeout_error")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе к OpenAI API: {e}", exc_info=True)
        return _("llm_openai_generic_error") # Don't expose raw error details


# --- Routes ---
@app.route('/')
def index():
    """Screen 1: Display category selection form."""
    # Language is set in g via before_request
    lang_categories = CATEGORIES.get(g.language, CATEGORIES[DEFAULT_LANGUAGE])
    return render_template('index.html', categories=lang_categories)
                           # g is automatically available in templates

@app.route('/search')
def search_places():
    """
    Screen 2 (processing): Get RZD, Geoapify, LLM data.
    Screen 3 (display): Show results.
    """
    # g.language is set by before_request
    lang = g.language
    # Get category display names from the form (will be in current language)
    selected_display_names = request.args.getlist('category')

    if not selected_display_names:
        flash(_("no_selection_warning"), "warning")
        return redirect(url_for('index', lang=lang)) # Keep lang parameter

    # --- Process Selected Categories ---
    geoapify_categories_set = set()
    rzd_selected = False
    current_lang_categories = CATEGORIES.get(lang, CATEGORIES[DEFAULT_LANGUAGE])
    # Map selected display names back to their codes/special values
    selected_internal_values = []

    for display_name in selected_display_names:
        if display_name in current_lang_categories:
            internal_value = current_lang_categories[display_name]
            selected_internal_values.append(internal_value) # Store code or 'rzd_schedule'
            if internal_value == "rzd_schedule":
                rzd_selected = True
            elif internal_value: # Ensure it's not empty
                codes = internal_value.split(',')
                geoapify_categories_set.update(c.strip() for c in codes if c.strip())
        else:
            logger.warning(f"Выбранное имя категории '{display_name}' не найдено для языка '{lang}'.")


    # --- Initialize result variables ---
    found_places = []
    geoapify_error_key = None # Store the translation key for the error
    geoapify_error_details = None
    llm_recommendations = ""
    is_llm_error = False
    rzd_arrivals = []
    rzd_departures = []
    rzd_error_message = None # Store the actual RZD error message string

    # --- Call RZD Parser if selected ---
    if rzd_selected:
        if rzd_parser_available:
            logger.info("Вызов парсера РЖД...")
            rzd_arrivals, rzd_departures, rzd_error_message = get_sochi_schedule()
            if rzd_error_message:
                # Use the already generated error message from the parser
                flash(f"{_('rzd_fetch_error')}: {rzd_error_message}", "warning")
        else:
            flash(_("rzd_module_error"), "danger")

    # --- Call Geoapify API if other categories are selected ---
    if geoapify_categories_set:
        # (Geoapify API call logic - adapted to store error key)
        api_params = {
            'categories': ",".join(sorted(list(geoapify_categories_set))),
            'filter': f"circle:{SOCHI_LON},{SOCHI_LAT},{SEARCH_RADIUS_METERS}",
            'bias': f"proximity:{SOCHI_LON},{SOCHI_LAT}",
            'limit': RESULT_LIMIT,
            'apiKey': GEOAPIFY_API_KEY,
            'lang': lang # Pass current language to Geoapify if supported
        }
        api_url = "https://api.geoapify.com/v2/places"
        try:
            logger.info(f"Запрос к Geoapify: categories={api_params['categories']}, filter={api_params['filter']}, lang={lang}")
            response = requests.get(api_url, params=api_params, timeout=20)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Ответ Geoapify: {len(data.get('features', []))} features.")

            # Process Geoapify results
            if data.get('features'):
                for feature in data['features']:
                    properties = feature.get('properties', {})
                    name = properties.get('name')
                    if not name: name = properties.get('datasource', {}).get('raw', {}).get('name')
                    lon = properties.get('lon')
                    lat = properties.get('lat')
                    if name and lon is not None and lat is not None:
                        address = properties.get('address_line2', properties.get('formatted', _("address_not_specified")))
                        place_categories = properties.get('categories', [])
                        map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                        cleaned_categories = [cat.split('.')[-1].replace('_', ' ') for cat in place_categories]
                        found_places.append({
                            'name': name, 'lat': lat, 'lon': lon, 'map_link': map_link,
                            'address': address, 'place_categories': cleaned_categories,
                        })
                    else:
                        logger.warning(f"Пропущено место Geoapify: name={name}, lon={lon}, lat={lat}")

            if not found_places and not geoapify_error_key:
                 other_selected = [k for k in selected_display_names if CATEGORIES.get(lang, {}).get(k) != "rzd_schedule"]
                 if other_selected:
                    flash(_("no_results_info", categories=", ".join(other_selected)), "info")

        except requests.exceptions.Timeout:
            geoapify_error_key = "geoapify_timeout_error"
            logger.error(f"Ошибка Geoapify: Таймаут")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error(f"Ошибка Geoapify HTTP: {status_code} {e.response.text}")
            geoapify_error_details = {'status_code': status_code}
            if status_code == 401: geoapify_error_key = "geoapify_http_error_401"
            elif status_code == 400: geoapify_error_key = "geoapify_http_error_400"
            elif status_code == 429: geoapify_error_key = "geoapify_http_error_429"
            else: geoapify_error_key = "geoapify_http_error"
        except requests.exceptions.RequestException as e:
            geoapify_error_key = "geoapify_connection_error"
            logger.error(f"Ошибка Geoapify Request: {e}")
        except Exception as e:
            geoapify_error_key = "geoapify_generic_error"
            logger.error(f"Неожиданная ошибка Geoapify: {e}", exc_info=True)

        # Flash critical Geoapify error if one occurred
        if geoapify_error_key:
             flash(f"{_('error_prefix')}: {_('search_error')} - {_(geoapify_error_key, **(geoapify_error_details or {}))}", "danger")


    # --- Get LLM Recommendations ---
    if openai_enabled:
        try:
            # Pass selected display names and current language code
            llm_recommendations = get_llm_recommendations(selected_display_names, lang)
            # Check if the result is an error message based on known fragments
            # (This check relies on the fragments being present in the translated error messages)
            if llm_recommendations and any(error_frag in llm_recommendations for error_frag in LLM_ERROR_MESSAGE_FRAGMENTS):
                is_llm_error = True
                logger.warning(f"LLM вернул сообщение об ошибке: {llm_recommendations}")
                # Flash the LLM status/error message
                flash(llm_recommendations, "warning")
            else:
                is_llm_error = False # Normal recommendation
        except Exception as e:
            logger.error(f"Ошибка при вызове get_llm_recommendations: {e}", exc_info=True)
            llm_recommendations = _("llm_result_error_text") # Use translated fallback
            is_llm_error = True
            flash(llm_recommendations, "warning") # Flash the fallback message
    elif selected_display_names: # Only show if relevant
         llm_recommendations = _("llm_unavailable_no_client")
         is_llm_error = True
         # flash(llm_recommendations, "info") # Optional: Flash this status


    # --- Render Results Page ---
    return render_template('results.html',
                           places=found_places,
                           # Don't pass geoapify_error_key, use flash messages instead
                           # error=_(geoapify_error_key, **(geoapify_error_details or {})) if geoapify_error_key else None,
                           selected_categories=selected_display_names, # Show translated names
                           llm_recommendations=llm_recommendations,
                           is_llm_error=is_llm_error,
                           rzd_arrivals=rzd_arrivals,
                           rzd_departures=rzd_departures,
                           # rzd_error is flashed now
                           # rzd_error=rzd_error_message,
                           rzd_selected=rzd_selected
                           )

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    # Ensure language context is available
    g.language = get_current_language()
    g.translate = _
    g.text_dir = 'rtl' if g.language == 'fa' else 'ltr'
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal Server Error: {e}", exc_info=True)
    # Ensure language context is available
    g.language = get_current_language()
    g.translate = _
    g.text_dir = 'rtl' if g.language == 'fa' else 'ltr'
    # You could render a 500.html template here
    return _("internal_server_error_message"), 500

# --- Main Execution ---
if __name__ == '__main__':
    # ... (Startup checks remain the same) ...
    valid_geoapify = GEOAPIFY_API_KEY and len(GEOAPIFY_API_KEY) > 20
    print("-" * 30)
    if not valid_geoapify:
         logger.critical("!!! ВНИМАНИЕ: Geoapify API Ключ не установлен или выглядит недействительным !!!")
    else:
         logger.info("Geoapify ключ найден.")

    if not openai_enabled:
         logger.warning("!!! ВНИМАНИЕ: Сервис персональных рекомендаций OpenAI неактивен.")
    else:
         logger.info("OpenAI клиент инициализирован.")

    if not rzd_parser_available:
        logger.warning("!!! ВНИМАНИЕ: Парсер РЖД (RZD.py) не импортирован.")

    if valid_geoapify:
        logger.info("Запуск Flask приложения...")
        app.run(host='127.0.0.1', port=5000, debug=True) # Set debug=False in production
    else:
        logger.critical("Приложение не может быть запущено без действительного Geoapify API ключа.")
    print("-" * 30)
# --- END OF FILE app.py ---