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
TOKEN = "ВАШ ТОКЕН"

# --- КОНФИГУРАЦИЯ ---
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "ВАШ ТОКЕН")

# Координаты Сочи и параметры поиска
SOCHI_LAT = 43.5855
SOCHI_LON = 39.7303
SEARCH_RADIUS_METERS = 15000
RESULT_LIMIT = 50

# --- Многоязычные категории ---
CATEGORIES = {
    "ru": {
        "Природа и парки": "natural,leisure.park",
        "Заведения": "catering.restaurant,catering.cafe,catering.fast_food",
        "Пляжи": "beach",
        "Отели и гостиницы": "accommodation.hotel,accommodation.guest_house",
        "Театры и музеи": "entertainment.culture.theatre,entertainment.culture.gallery",
        "Океанариум и Дельфинарий": "entertainment.aquarium",
        "Сувениры": "commercial.gift_and_souvenir",
        "Туристические объекты": "tourism",
        "Поезда РЖД": "rzd_tickets",
    },
    "en": {
        "Nature and Parks": "natural,leisure.park",
        "Restaurants and Cafes": "catering.restaurant,catering.cafe,catering.fast_food",
        "Beaches": "beach",
        "Hotels and Guesthouses": "accommodation.hotel,accommodation.guest_house",
        "Theaters and Museums": "entertainment.culture.theatre,entertainment.culture.gallery",
        "Aquarium and Dolphinarium": "entertainment.aquarium",
        "Souvenirs": "commercial.gift_and_souvenir",
        "Tourist Attractions": "tourism",
        "RZD Trains": "rzd_tickets",
    },
    "zh": {
        "自然与公园": "natural,leisure.park",
        "餐厅与咖啡馆": "catering.restaurant,catering.cafe,catering.fast_food",
        "海滩": "beach",
        "酒店与宾馆": "accommodation.hotel,accommodation.guest_house",
        "剧院与博物馆": "entertainment.culture.theatre,entertainment.culture.gallery",
        "水族馆与海豚馆": "entertainment.aquarium",
        "纪念品": "commercial.gift_and_souvenir",
        "旅游景点": "tourism",
        "俄罗斯铁路": "rzd_tickets",
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
        "قطارهای RZD": "rzd_tickets",
        "رستوران‌های حلال": "catering.restaurant.halal",
    },
    "tr": {
        "Doğa ve Parklar": "natural,leisure.park",
        "Restoranlar ve Kafeler": "catering.restaurant,catering.cafe,catering.fast_food",
        "Plajlar": "beach",
        "Oteller ve Misafirhaneler": "accommodation.hotel,accommodation.guest_house",
        "Tiyatrolar ve Müzeler": "entertainment.culture.theatre,entertainment.culture.gallery",
        "Akvaryum ve Yunus Gösteri Merkezi": "entertainment.aquarium",
        "Hediyelik Eşyalar": "commercial.gift_and_souvenir",
        "Turistik Yerler": "tourism",
        "RZD Trenleri": "rzd_tickets",
    },
}

# --- Словарь переводов ---
LANGUAGES = {
    "ru": {
        "welcome": "Привет! Я бот для поиска мест в Сочи и покупки билетов.\nВыбери интересующие категории:",
        "categories": "Доступные категории:",
        "done": "Готово",
        "error_no_selection": "Пожалуйста, выберите категории.",
        "no_results": "По вашему запросу ({categories}) ничего не найдено.",
        "no_address": "Адрес не указан",
        "timeout_error": "Не удалось получить данные: сервер не ответил вовремя.",
        "connection_error": "Ошибка подключения: {error}",
        "general_error": "Произошла ошибка: {error}",
        "select_transport": "Выберите маршрут:",
        "rzd_tickets": "Поезда РЖД",
        "flights": "Авиабилеты",
        "buses": "Автобусы",
        "address": "Адрес",
        "map": "Карта",
        "choose_language": "Выберите язык:",
        "language_set": "Язык установлен: {lang}",
        "detected_language": "Обнаружен ваш язык: Русский. Использовать его?",
        "rzd_sochi_moscow": "Сочи - Москва",
        "rzd_sochi_spb": "Сочи - СПб",
        "rzd_sochi_krasnodar": "Сочи - Краснодар",
        "rzd_other_route": "Другой маршрут",
        "rzd_enter_route": "Введите маршрут: Город - Город",
        "rzd_train": "Поезд",
        "rzd_departure": "Отправление",
        "rzd_arrival": "Прибытие",
        "rzd_duration": "В пути",
        "rzd_price_rub": "руб.",
        "rzd_seats_available": "мест",
        "rzd_buy_tickets": "🔗 Купить билеты:",
    },
    "en": {
        "welcome": "Hello! I'm a bot for finding places in Sochi and buying tickets.\nChoose categories:",
        "categories": "Available categories:",
        "done": "Done",
        "error_no_selection": "Please select categories.",
        "no_results": "No results found for your request ({categories}).",
        "no_address": "Address not specified",
        "timeout_error": "Failed to retrieve data: server timed out.",
        "connection_error": "Connection error: {error}",
        "general_error": "An error occurred: {error}",
        "select_transport": "Select route:",
        "rzd_tickets": "RZD Trains",
        "flights": "Flights",
        "buses": "Buses",
        "address": "Address",
        "map": "Map",
        "choose_language": "Choose language:",
        "language_set": "Language set: {lang}",
        "detected_language": "Detected your language: English. Use it?",
        "rzd_sochi_moscow": "Sochi - Moscow",
        "rzd_sochi_spb": "Sochi - Saint Petersburg",
        "rzd_sochi_krasnodar": "Sochi - Krasnodar",
        "rzd_other_route": "Other route",
        "rzd_enter_route": "Enter route: City - City",
        "rzd_train": "Train",
        "rzd_departure": "Departure",
        "rzd_arrival": "Arrival",
        "rzd_duration": "Duration",
        "rzd_price_rub": "RUB",
        "rzd_seats_available": "seats",
        "rzd_buy_tickets": "🔗 Buy tickets:",
    },
    "zh": {
        "welcome": "你好！我是索契景点搜索和购票机器人。\n选择类别：",
        "categories": "可用类别：",
        "done": "完成",
        "error_no_selection": "请选择类别。",
        "no_results": "未找到符合您请求（{categories}）的结果。",
        "no_address": "未提供地址",
        "timeout_error": "无法获取数据：服务器超时。",
        "connection_error": "连接错误：{error}",
        "general_error": "发生错误：{error}",
        "select_transport": "选择路线：",
        "rzd_tickets": "俄罗斯铁路",
        "flights": "机票",
        "buses": "巴士",
        "address": "地址",
        "map": "地图",
        "choose_language": "选择语言：",
        "language_set": "语言设置为：{lang}",
        "detected_language": "检测到您的语言：中文。使用它吗？",
        "rzd_sochi_moscow": "索契 - 莫斯科",
        "rzd_sochi_spb": "索契 - 圣彼得堡",
        "rzd_sochi_krasnodar": "索契 - 克拉斯诺达尔",
        "rzd_other_route": "其他路线",
        "rzd_enter_route": "输入路线：城市 - 城市",
        "rzd_train": "列车",
        "rzd_departure": "出发",
        "rzd_arrival": "到达",
        "rzd_duration": "时长",
        "rzd_price_rub": "卢布",
        "rzd_seats_available": "座位",
        "rzd_buy_tickets": "🔗 购买车票：",
    },
    "fa": {
        "welcome": "سلام! من رباتی برای یافتن مکان‌ها در سوچی و خرید بلیط هستم.\nدسته‌ها را انتخاب کنید:",
        "categories": "دسته‌های موجود:",
        "done": "تمام",
        "error_no_selection": "لطفاً دسته‌ها را انتخاب کنید.",
        "no_results": "نتیجه‌ای برای درخواست شما ({categories}) یافت نشد.",
        "no_address": "آدرس مشخص نشده است",
        "timeout_error": "دریافت داده‌ها ممکن نشد: سرور پاسخ نداد.",
        "connection_error": "خطای اتصال: {error}",
        "general_error": "خطایی رخ داد: {error}",
        "select_transport": "مسیر را انتخاب کنید:",
        "rzd_tickets": "قطارهای RZD",
        "flights": "بلیط هواپیما",
        "buses": "اتوبوس‌ها",
        "address": "آدرس",
        "map": "نقشه",
        "choose_language": "زبان را انتخاب کنید:",
        "language_set": "زبان تنظیم شد: {lang}",
        "detected_language": "زبان شما شناسایی شد: فارسی. از آن استفاده کنم؟",
        "rzd_sochi_moscow": "سوچی - مسکو",
        "rzd_sochi_spb": "سوچی - سن پترزبورگ",
        "rzd_sochi_krasnodar": "سوچی - کراسنودار",
        "rzd_other_route": "مسیر دیگر",
        "rzd_enter_route": "مسیر را وارد کنید: شهر - شهر",
        "rzd_train": "قطار",
        "rzd_departure": "حرکت",
        "rzd_arrival": "رسیدن",
        "rzd_duration": "مدت زمان",
        "rzd_price_rub": "روبل",
        "rzd_seats_available": "صندلی",
        "rzd_buy_tickets": "🔗 خرید بلیط:",
    },
    "tr": {
        "welcome": "Merhaba! Soçi'de yer bulma ve bilet satın alma botuyum.\nKategorileri seçin:",
        "categories": "Mevcut kategoriler:",
        "done": "Tamam",
        "error_no_selection": "Lütfen kategorileri seçin.",
        "no_results": "İsteğiniz ({categories}) için sonuç bulunamadı.",
        "no_address": "Adres belirtilmemiş",
        "timeout_error": "Veri alınamadı: sunucu zaman aşımına uğradı.",
        "connection_error": "Bağlantı hatası: {error}",
        "general_error": "Bir hata oluştu: {error}",
        "select_transport": "Rota seçin:",
        "rzd_tickets": "RZD Trenleri",
        "flights": "Uçak Biletleri",
        "buses": "Otobüsler",
        "address": "Adres",
        "map": "Harita",
        "choose_language": "Dil seçin:",
        "language_set": "Dil ayarlandı: {lang}",
        "detected_language": "Diliniz algılandı: Türkçe. Bunu kullansam mı?",
        "rzd_sochi_moscow": "Soçi - Moskova",
        "rzd_sochi_spb": "Soçi - St. Petersburg",
        "rzd_sochi_krasnodar": "Soçi - Krasnodar",
        "rzd_other_route": "Diğer güzergah",
        "rzd_enter_route": "Güzergahı girin: Şehir - Şehir",
        "rzd_train": "Tren",
        "rzd_departure": "Kalkış",
        "rzd_arrival": "Varış",
        "rzd_duration": "Süre",
        "rzd_price_rub": "RUB",
        "rzd_seats_available": "koltuk",
        "rzd_buy_tickets": "🔗 Bilet satın al:",
    },
}


# Функция для запроса билетов РЖД (заглушка)
def get_rzd_tickets(from_station, to_station, date, lang="ru"):
    try:
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
        return None, LANGUAGES[lang]["general_error"].format(error=e)


# Функция для поиска мест через Geoapify
def search_places(selected_keys, lang="ru"):
    if "rzd_tickets" in selected_keys:
        return [], None

    geoapify_categories_set = set()
    for key in selected_keys:
        if key in CATEGORIES[lang]:
            codes = CATEGORIES[lang][key].split(',')
            geoapify_categories_set.update(c.strip() for c in codes if c.strip())

    if not geoapify_categories_set:
        return None, LANGUAGES[lang]["no_results"].format(categories=", ".join(selected_keys))

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
                    address = properties.get('formatted', LANGUAGES[lang]["no_address"])
                    map_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
                    found_places.append({
                        'name': name,
                        'address': address,
                        'map_link': map_link,
                    })

        if not found_places:
            selected_names = ", ".join(selected_keys)
            error_message = LANGUAGES[lang]["no_results"].format(categories=selected_names)

    except requests.exceptions.Timeout:
        error_message = LANGUAGES[lang]["timeout_error"]
    except requests.exceptions.RequestException as e:
        error_message = LANGUAGES[lang]["connection_error"].format(error=e)
    except Exception as e:
        error_message = LANGUAGES[lang]["general_error"].format(error=e)

    return found_places, error_message


# Команда /language
async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("中文", callback_data="lang_zh")],
        [InlineKeyboardButton("فارسی", callback_data="lang_fa")],
        [InlineKeyboardButton("Türkçe", callback_data="lang_tr")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите язык / Choose language / 选择语言 / زبان را انتخاب کنید / Dil seçin:",
        reply_markup=reply_markup
    )


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    # Сбрасываем язык при каждом /start
    user_data.pop("language", None)

    # Определяем язык пользователя из настроек Telegram
    user_lang = update.effective_user.language_code
    lang_map = {
        "ru": "ru",
        "en": "en",
        "zh": "zh",
        "fa": "fa",
        "tr": "tr",
    }
    detected_lang = lang_map.get(user_lang[:2], None)

    if detected_lang:
        # Если язык поддерживается, предлагаем его использовать
        user_data["language"] = detected_lang
        keyboard = [
            [InlineKeyboardButton("Да / Yes / 是 / بله / Evet", callback_data=f"confirm_lang_{detected_lang}")],
            [InlineKeyboardButton(
                "Нет, выбрать другой / No, choose another / 不，选择其他 / خیر، یکی دیگر انتخاب کنید / Hayır, başka bir tane seç",
                callback_data="change_lang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[detected_lang]["detected_language"],
            reply_markup=reply_markup
        )
    else:
        # Если язык не поддерживается, предлагаем выбрать
        await language(update, context)


# Обработчик кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    lang = user_data.get("language", "ru")

    if "selected_categories" not in user_data:
        user_data["selected_categories"] = []

    callback_data = query.data

    # Обработка подтверждения языка
    if callback_data.startswith("confirm_lang_"):
        lang = callback_data[13:]
        user_data["language"] = lang
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"category_{cat}")]
            for cat in CATEGORIES[lang].keys()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Удаляем старое сообщение
        await query.message.delete()
        # Отправляем новое сообщение с категориями
        await query.message.reply_text(
            LANGUAGES[lang]["language_set"].format(lang=lang),
            reply_markup=reply_markup
        )
        return

    # Обработка смены языка
    if callback_data == "change_lang":
        keyboard = [
            [InlineKeyboardButton("Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("中文", callback_data="lang_zh")],
            [InlineKeyboardButton("فارسی", callback_data="lang_fa")],
            [InlineKeyboardButton("Türkçe", callback_data="lang_tr")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Удаляем старое сообщение
        await query.message.delete()
        await query.message.reply_text(
            "Выберите язык / Choose language / 选择语言 / زبان را انتخاب کنید / Dil seçin:",
            reply_markup=reply_markup
        )
        return

    # Обработка выбора языка
    if callback_data.startswith("lang_"):
        lang = callback_data[5:]
        user_data["language"] = lang
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"category_{cat}")]
            for cat in CATEGORIES[lang].keys()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Удаляем старое сообщение
        await query.message.delete()
        # Отправляем новое сообщение с категориями
        await query.message.reply_text(
            LANGUAGES[lang]["language_set"].format(lang=lang),
            reply_markup=reply_markup
        )
        return

    # Обработка категорий
    if callback_data.startswith("category_"):
        category = callback_data[9:]
        if category in user_data["selected_categories"]:
            user_data["selected_categories"].remove(category)
            await query.edit_message_text(f"{category} {LANGUAGES[lang]['done'].lower()}.")
        else:
            user_data["selected_categories"].append(category)
            await query.edit_message_text(f"{category} {LANGUAGES[lang]['done'].lower()}.")

        # Обновляем клавиатуру
        keyboard = [
            [InlineKeyboardButton(
                f"{'✅ ' if cat in user_data['selected_categories'] else ''}{cat}",
                callback_data=f"category_{cat}"
            )]
            for cat in CATEGORIES[lang].keys()
        ]
        keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["done"], callback_data="done")])

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif callback_data == "done":
        selected = user_data.get("selected_categories", [])
        if not selected:
            await query.message.reply_text(LANGUAGES[lang]["error_no_selection"])
            return

        # Проверяем, выбрана ли категория "Поезда РЖД" по значению в словаре
        is_rzd_selected = any(CATEGORIES[lang].get(cat) == "rzd_tickets" for cat in selected)
        if is_rzd_selected:
            keyboard = [
                [InlineKeyboardButton(LANGUAGES[lang]["rzd_sochi_moscow"], callback_data="route_sochi_moscow")],
                [InlineKeyboardButton(LANGUAGES[lang]["rzd_sochi_spb"], callback_data="route_sochi_spb")],
                [InlineKeyboardButton(LANGUAGES[lang]["rzd_sochi_krasnodar"], callback_data="route_sochi_krasnodar")],
                [InlineKeyboardButton(LANGUAGES[lang]["rzd_other_route"], callback_data="route_custom")],
            ]
            await query.message.reply_text(
                LANGUAGES[lang]["select_transport"],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            places, error = search_places(selected, lang)
            response = LANGUAGES[lang]["welcome"].split("\n")[0] + f": {', '.join(selected)}\n\n"

            if error:
                response += error
            elif places:
                for place in places[:5]:
                    response += (
                        f"📍 {place['name']}\n"
                        f"{LANGUAGES[lang]['address']}: {place['address']}\n"
                        f"{LANGUAGES[lang]['map']}: {place['map_link']}\n\n"
                    )
            else:
                response += LANGUAGES[lang]["no_results"].format(categories=", ".join(selected))

            await query.message.reply_text(response)
            user_data["selected_categories"] = []

    # Обработка маршрутов
    elif callback_data.startswith("route_"):
        route = callback_data[6:]

        if route == "sochi_moscow":
            from_st, to_st = "Сочи", "Москва"
        elif route == "sochi_spb":
            from_st, to_st = "Санкт-Петербург", "Сочи"
        elif route == "sochi_krasnodar":
            from_st, to_st = "Сочи", "Краснодар"
        else:
            await query.message.reply_text(
                LANGUAGES[lang]["general_error"].format(error=LANGUAGES[lang]["rzd_enter_route"]))
            return

        date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
        tickets, error = get_rzd_tickets(from_st, to_st, date, lang)

        if error:
            await query.message.reply_text(error)
            return

        if not tickets:
            await query.message.reply_text(f"{LANGUAGES[lang]['no_results'].format(categories=f'{from_st} - {to_st}')}")
            return

        response = f"🚂 {LANGUAGES[lang]['rzd_tickets']} {from_st} - {to_st} ({date}):\n\n"
        for ticket in tickets:
            response += (
                f"{LANGUAGES[lang]['rzd_train']} {ticket['train']}\n"
                f"{LANGUAGES[lang]['rzd_departure']}: {ticket['departure']}\n"
                f"{LANGUAGES[lang]['rzd_arrival']}: {ticket['arrival']}\n"
                f"{LANGUAGES[lang]['rzd_duration']}: {ticket['duration']}\n"
            )
            for cls, info in ticket['classes'].items():
                response += f"- {cls}: {info['price']} {LANGUAGES[lang]['rzd_price_rub']} ({LANGUAGES[lang]['rzd_seats_available']}: {info['seats']})\n"
            response += "\n"

        response += f"{LANGUAGES[lang]['rzd_buy_tickets']} https://pass.rzd.ru"
        await query.message.reply_text(response)


# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_data = context.user_data
    lang = user_data.get("language", "ru")

    # Обработка запроса транспорта
    if " - " in text and any(
            word in text.lower() for word in ["билет", "поезд", "ржд", "ticket", "train"]):
        parts = [p.strip() for p in text.split(" - ") if p.strip()]
        if len(parts) == 2:
            from_st, to_st = parts
            date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
            tickets, error = get_rzd_tickets(from_st, to_st, date, lang)

            if error:
                await update.message.reply_text(error)
                return

            if not tickets:
                await update.message.reply_text(LANGUAGES[lang]["no_results"].format(categories=f"{from_st} - {to_st}"))
                return

            response = f"🚂 {LANGUAGES[lang]['rzd_tickets']} {from_st} - {to_st} ({date}):\n\n"
            for ticket in tickets:
                response += (
                    f"{LANGUAGES[lang]['rzd_train']} {ticket['train']}\n"
                    f"{LANGUAGES[lang]['rzd_departure']}: {ticket['departure']}\n"
                    f"{LANGUAGES[lang]['rzd_arrival']}: {ticket['arrival']}\n"
                    f"{LANGUAGES[lang]['rzd_duration']}: {ticket['duration']}\n"
                )
                for cls, info in ticket['classes'].items():
                    response += f"- {cls}: {info['price']} {LANGUAGES[lang]['rzd_price_rub']} ({LANGUAGES[lang]['rzd_seats_available']}: {info['seats']})\n"
                response += "\n"

            response += f"{LANGUAGES[lang]['rzd_buy_tickets']} https://pass.rzd.ru"
            await update.message.reply_text(response)
            return

    # Обработка обычных категорий
    selected = [cat.strip() for cat in text.split(',') if cat.strip() in CATEGORIES[lang]]
    if not selected:
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES[lang].keys())
        await update.message.reply_text(
            f"{LANGUAGES[lang]['categories']}\n{categories_list}\n"
            f"Или используйте /start для выбора."
        )
        return

    places, error = search_places(selected, lang)
    response = f"{LANGUAGES[lang]['welcome'].split('\n')[0]}: {', '.join(selected)}\n\n"

    if error:
        response += error
    elif places:
        for place in places[:5]:
            response += (
                f"📍 {place['name']}\n"
                f"{LANGUAGES[lang]['address']}: {place['address']}\n"
                f"{LANGUAGES[lang]['map']}: {place['map_link']}\n\n"
            )
    else:
        response += LANGUAGES[lang]["no_results"].format(categories=", ".join(selected))

    await update.message.reply_text(response)


# Главная функция
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    if GEOAPIFY_API_KEY and GEOAPIFY_API_KEY != "YOUR_API_KEY":
        main()
    else:
        logger.error("Ошибка: Неверный Geoapify API ключ!")