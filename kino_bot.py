import json
from json import JSONDecodeError

from kinopoisk_unofficial.model.filter_order import FilterOrder
# сортировка по фильтру
from kinopoisk_unofficial.client.exception.not_found import NotFound
from kinopoisk_unofficial.request.films.film_search_by_filters_request import FilmSearchByFiltersRequest
# возвращает список id стран и жанров, которые могут быть использованы в поиске по фильтру
from telebot import TeleBot, apihelper
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, \
    ReplyKeyboardRemove
# InLineKeyboardButton - название кнопки
# InLineKeyboardMarkup - клавиатура inline
# ReplyKeyboardMarkup - клавиатура reply
# KeyboardButton - кнопка
# ReplyKeyboardRemove - удаление клавиатуры после нажатия
from kinopoisk_unofficial.kinopoisk_api_client import KinopoiskApiClient
from kinopoisk_unofficial.request.films.filters_request import FiltersRequest

apihelper.ENABLE_MIDDLEWARE = True
# обработка запросов и ответов

KINOPOISK_TOKEN = "69de329b-227f-4871-bb11-3086e2608e69"
TELEGRAM_TOKEN = "5450027225:AAEnb_YUSCOLjVN_BCXb5BkMzm44WBlPjNA"

bot = TeleBot(TELEGRAM_TOKEN, parse_mode="html") # html - дальше <b> и <i>
api_client = KinopoiskApiClient(KINOPOISK_TOKEN)

GENRES = {}
SESSIONS = {}


def get_genres(): # создание списка кнопок
    genres = api_client.films.send_filters_request(FiltersRequest()).genres

    for x in genres:
        title = x.genre
        title = title[0].upper() + title[1:]
        GENRES[title] = x.id


@bot.message_handler(commands=["start"])
def on_start(message):
    markup = ReplyKeyboardMarkup()
    bot.send_message(
        chat_id=message.chat.id,
        text="<b>Привет!</b>",
        reply_markup=markup
    )

    on_help(message)


@bot.message_handler(commands=["help"])
def on_help(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            'Поиск по жанру',
            callback_data=json.dumps(
                {
                    "type": "initiate_query",
                    "query_parameter": "genre"
                }
            )
        ),
        InlineKeyboardButton(
            'Поиск по году',
            callback_data=json.dumps(
                {
                    "type": "initiate_query",
                    "query_parameter": "year"
                }
            )
        )
    )

    bot.send_message(
        chat_id=message.chat.id,
        text="Я помогу тебе найти прекрасный фильм для просмотра!",
        reply_markup=markup
    )


@bot.middleware_handler(update_types=["callback_query"]) # отвечает за прием данных от пользователя
def on_callback_query(instance, message):
    try: # перехватывает все коллбеки на кнопки рядом с сообщениями (inline buttons) и преобразует строку в json
        message.data = json.loads(message.data)
    except JSONDecodeError as e:
        print(e)


@bot.callback_query_handler(func=lambda query: query.data["type"] == "initiate_query")
def on_initiate_query(query):
    data = query.data
    message = query.message

    def query_genre():
        markup = ReplyKeyboardMarkup()

        for item in GENRES.keys():
            markup.add(
                KeyboardButton(
                    text=item
                )
            )

        bot.send_message(
            chat_id=message.chat.id,
            text="Какой жанр хотите глянуть?",
            reply_markup=markup
        )

    def query_year():
        bot.send_message(
            chat_id=message.chat.id,
            text="Кино какого года изволите смотреть?"
        )

    if data["query_parameter"] == "genre":
        query_genre()
    elif data["query_parameter"] == "year":
        query_year()


@bot.callback_query_handler(func=lambda query: query.data["type"] == "restart")
def on_restart(query):
    message = query.message

    on_help(message)


@bot.message_handler(func=lambda x: x.text in GENRES)
def on_film_query_by_genre(message):
    genre = message.text

    request = FilmSearchByFiltersRequest()
    request.genre = [GENRES[genre]]

    query_film(message, request)


@bot.message_handler(func=lambda x: x.text.isnumeric())
def on_film_query_by_year(message):
    year = int(message.text)

    request = FilmSearchByFiltersRequest()
    request.year_from = year
    request.year_to = year

    query_film(message, request)


def query_film(message, request):
    request.order = FilterOrder.RATING

    chat_id = message.chat.id

    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = set()

    while True:
        try:
            response = api_client.films.send_film_search_by_filters_request(request)
            
            for film in response.items:
                if film.kinopoisk_id not in SESSIONS[chat_id]:
                    SESSIONS[chat_id].add(film.kinopoisk_id)

                    markup = ReplyKeyboardRemove()

                    message = [
                        "Держи, нашлось кино!",
                        "",
                        f"<b>Название</b>: {film.name_ru or film.name_en}",
                        f"<b>Рейтинг</b>: {film.rating_kinopoisk}"
                    ]

                    bot.send_message(
                        chat_id=chat_id,
                        text="\n".join(message),
                        reply_markup=markup
                    )

                    markup = InlineKeyboardMarkup()
                    markup.add(
                        InlineKeyboardButton(
                            text="Да, капитан!",
                            callback_data=json.dumps(
                                {
                                    "type": "restart"
                                }
                            )
                        )
                    )

                    bot.send_message(
                        chat_id=chat_id,
                        text="Попробуем ещё раз?",
                        reply_markup=markup
                    )

                    return

            request._FilmSearchByFiltersRequest__page += 1 # используется для перехода на следующую страницу

            if request.page > response.totalPages:
                markup = ReplyKeyboardRemove()

                bot.send_message(
                    chat_id=message.chat.id,
                    text="Таких фильмов больше нет :(",
                    reply_markup=markup
                )

                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton(
                        text="Да, капитан!",
                        callback_data=json.dumps(
                            {
                                "type": "restart"
                            }
                        )
                    )
                )

                bot.send_message(
                    chat_id=chat_id,
                    text="Попробуем ещё раз?",
                    reply_markup=markup
                )
                return
        except NotFound as e:
            print(e)
            markup = ReplyKeyboardRemove()

            bot.send_message(
                chat_id=message.chat.id,
                text="Таких фильмов больше нет :(",
                reply_markup=markup
            )

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(
                    text="Да, капитан!",
                    callback_data=json.dumps(
                        {
                            "type": "restart"
                        }
                    )
                )
            )

            bot.send_message(
                chat_id=chat_id,
                text="Попробуем ещё раз?",
                reply_markup=markup
            )

            return


@bot.message_handler(func=lambda message: True)
def on_error(message):
    reply_markup = ReplyKeyboardRemove()
    bot.send_message(
        chat_id=message.chat.id,
        text="Ой, я не настолько умный. Попробуй что-то попроще :(",
        reply_markup=reply_markup
    )


if __name__ == '__main__':
    get_genres()
    bot.infinity_polling()
