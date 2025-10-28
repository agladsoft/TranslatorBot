import os
import logging
import telebot
import requests
from typing import Optional
from mochi_ import MochiConnect
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, Response
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
bot = telebot.TeleBot(os.environ["TOKEN"])

# Хранилище для временных данных карточек
user_cards = {}

# Настройка LangChain с OpenAI
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0
)

# Создаем шаблон промпта
prompt_template = ChatPromptTemplate.from_messages([
    ("system", "Ты профессиональный переводчик."),
    ("user", """Определи язык текста "{text}".
Если текст на русском - переведи на английский.
Если текст на английском - переведи на русский.
Если текст на другом языке - переведи на английский.

Предоставь:
1. Перевод слова/фразы
2. 3 примера использования этого слова в предложениях с переводом

ВАЖНО! Порядок в примерах:
- Если исходный текст на АНГЛИЙСКОМ - пиши примеры: [английский пример] - [русский перевод]
- Если исходный текст на РУССКОМ - пиши примеры: [русский пример] - [английский перевод]

Требования:
1. Не используй кавычки и скобки.
2. В примерах ВСЕГДА первым идет пример на языке исходного текста "{text}", вторым - его перевод.

Ответь в следующем формате:
Перевод: [перевод]
Примеры:
1. [пример на исходном языке] - [перевод]
2. [пример на исходном языке] - [перевод]
3. [пример на исходном языке] - [перевод]""")
])

# Создаем цепочку
translation_chain = prompt_template | llm | StrOutputParser()

# Создаем промпт для извлечения ключевого слова
keyword_prompt = ChatPromptTemplate.from_messages([
    ("system", "Ты помощник, который извлекает ключевые слова из текста."),
    ("user", """Из текста "{text}" извлеки ОДНО главное существительное, которое лучше всего подходит для поиска изображения.
Если это одно слово - верни его.
Если это предложение - верни самое важное существительное.
Верни ТОЛЬКО слово на английском языке, без объяснений.""")
])

keyword_chain = keyword_prompt | llm | StrOutputParser()


def get_image_search_keyword(text: str) -> str:
    """Извлекает ключевое слово для поиска изображения"""
    try:
        keyword = keyword_chain.invoke({"text": text}).strip()
        logger.info(f"Извлечено ключевое слово для поиска: {keyword}")
        return keyword
    except Exception as e:
        logger.error(f"Ошибка извлечения ключевого слова: {e}")
        # Если не удалось извлечь, возвращаем первое слово
        return text.split()[0] if text else text


def get_image_url(query: str) -> Optional[str]:
    """Получает URL изображения через Unsplash API"""
    try:
        # Используем Unsplash API для поиска изображений
        access_key = os.getenv("UNSPLASH_ACCESS_KEY")

        if not access_key:
            logger.warning("UNSPLASH_ACCESS_KEY не найден в .env")
            return None

        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 1,
            "client_id": access_key
        }

        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                # Получаем URL изображения
                return data["results"][0]["urls"]["regular"]

        return None
    except Exception as e:
        logger.error(f"Ошибка получения изображения: {e}")
        return None


@bot.message_handler(commands=['start'])
def start_bot(message: Message) -> None:
    logger.info(f"start_bot called by {message.from_user.first_name}")
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я бот-переводчик. Отправь мне слово или фразу:\n"
        "• Русский → Английский\n"
        "• Английский → Русский\n\n"
        "Я автоматически определю язык и переведу с примерами использования.\n\n"
        "Просто напиши слово и отправь мне!"
    )
    bot.send_message(message.chat.id, welcome_text)
    logger.info("start message sent")


@bot.message_handler(func=lambda message: True)
def translate_word(message: Message) -> None:
    logger.info(f"translate_word called for: {message.text}")
    loading_msg = None

    try:
        text = message.text.strip()

        # Отправляем GIF с загрузкой (используем известный URL с анимацией загрузки)
        loading_gif_url = "https://i.gifer.com/8cEp.gif"
        loading_msg = bot.send_animation(
            message.chat.id,
            loading_gif_url,
            caption="⏳ Загрузка перевода и изображения...",
            reply_to_message_id=message.message_id
        )

        # Показываем индикатор "печатает..."
        bot.send_chat_action(message.chat.id, 'typing')

        # Используем LangChain цепочку для перевода
        ai_response = translation_chain.invoke({"text": text})

        # Форматируем ответ для пользователя с markdown разметкой
        formatted_response = f"📝 *Слово:* {text}\n\n{ai_response}"

        # Улучшаем форматирование ответа AI
        formatted_response = formatted_response.replace("Перевод:", "*Перевод:*")
        formatted_response = formatted_response.replace("Примеры:", "\n*Примеры:*")

        # Показываем индикатор "загружает фото..."
        bot.send_chat_action(message.chat.id, 'upload_photo')

        # Извлекаем ключевое слово для поиска изображения
        search_keyword = get_image_search_keyword(text)

        # Получаем изображение по ключевому слову
        image_url = get_image_url(search_keyword)
        logger.info(f"Получен URL изображения: {image_url}")

        # Создаем кнопку для добавления в Mochi
        keyboard = InlineKeyboardMarkup()
        add_to_mochi_btn = InlineKeyboardButton("📚 Добавить в Mochi", callback_data=f"add_mochi_{message.message_id}")
        keyboard.add(add_to_mochi_btn)

        # Сохраняем данные карточки для последующего добавления в Mochi
        user_cards[message.message_id] = {
            'word': text,
            'translation': ai_response,
            'image_url': image_url,
            'user_id': message.from_user.id
        }

        if image_url:
            try:
                # Отправляем фото с подписью и кнопкой (parse_mode для markdown)
                bot.send_photo(
                    message.chat.id,
                    image_url,
                    caption=formatted_response,
                    parse_mode='Markdown',
                    reply_markup=keyboard,
                    reply_to_message_id=message.message_id
                )
                logger.info("Изображение успешно отправлено")
            except Exception as img_error:
                # Если не удалось отправить фото, отправляем только текст
                logger.error(f"Ошибка отправки изображения: {img_error}")
                bot.reply_to(message, formatted_response, parse_mode='Markdown', reply_markup=keyboard)
        else:
            logger.info("URL изображения не получен, отправляем только текст")
            bot.reply_to(message, formatted_response, parse_mode='Markdown', reply_markup=keyboard)

        # Удаляем GIF с загрузкой
        if loading_msg:
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except Exception as e:
                logger.error(f"Ошибка удаления loading GIF: {e}")

    except Exception as e:
        logger.error(f"Ошибка при переводе: {e}")
        # Удаляем GIF в случае ошибки
        if loading_msg:
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except Exception as ex:
                logger.error(f"Ошибка удаления loading GIF: {ex}")
        bot.reply_to(message, f"Произошла ошибка при переводе: {str(e)}\nПопробуйте еще раз.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_mochi_'))
def handle_add_to_mochi(call: CallbackQuery):
    logger.info(f"handle_add_to_mochi called for: {call.data}")
    try:
        # Извлекаем message_id из callback_data
        message_id = int(call.data.split('_')[2])

        if message_id not in user_cards:
            bot.answer_callback_query(call.id, "❌ Данные карточки не найдены", show_alert=True)
            return

        card_data = user_cards[message_id]

        # Получаем API ключ из переменных окружения
        mochi_api_key = os.getenv("MOCHI_API_KEY")
        if not mochi_api_key:
            bot.answer_callback_query(
                call.id,
                "❌ MOCHI_API_KEY не найден в .env файле",
                show_alert=True
            )
            return

        # Создаем подключение к Mochi
        mochi = MochiConnect(mochi_api_key)

        # Проверяем подключение
        if not mochi.check_connection():
            bot.answer_callback_query(
                call.id,
                "❌ Не удалось подключиться к Mochi.\nПроверьте API ключ.",
                show_alert=True
            )
            return

        # Создаем уникальное имя колоды для пользователя
        user_id = card_data['user_id']
        user_name = call.from_user.first_name or f"User{user_id}"
        deck_name = f"Vocabulary Bot - {user_name}"

        # Получаем или создаем колоду
        deck_id = mochi.get_or_create_deck(deck_name)

        # Парсим перевод и примеры из AI ответа
        ai_text = card_data['translation']
        translation = ""
        examples = ""

        # Извлекаем перевод (строка после "Перевод:")
        if "Перевод:" in ai_text:
            parts = ai_text.split("Перевод:", 1)[1]
            if "Примеры:" in parts:
                translation = parts.split("Примеры:", 1)[0].strip()
                examples_text = parts.split("Примеры:", 1)[1].strip()
                examples = examples_text
            else:
                translation = parts.strip()

        # Формируем front и back для Basic flashcard
        # Front - слово (большой размер через заголовок)
        front_text = f"# {card_data['word']}"

        # Back - перевод (большой размер) и примеры
        back_text = f"## {translation or ai_text}"
        if examples:
            back_text += f"\n\n{examples}"

        # Проверяем, существует ли уже такая карточка
        if mochi.card_exists(deck_id, front_text):
            logger.info(f"Карточка уже существует: {front_text}")
            bot.answer_callback_query(call.id, "⚠️ Такая карточка уже существует в Mochi!", show_alert=True)

            # Обновляем кнопку на статус "уже существует"
            exists_keyboard = InlineKeyboardMarkup()
            exists_btn = InlineKeyboardButton("⚠️ Карточка уже существует", callback_data="done")
            exists_keyboard.add(exists_btn)
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=exists_keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка обновления кнопки: {e}")

            # Удаляем данные карточки
            del user_cards[message_id]
            return

        # Добавляем карточку в Mochi
        mochi.add_card(
            deck_id=deck_id,
            front_text=front_text,
            back_text=back_text,
            image_url=card_data['image_url']
        )

        logger.info(f"Карточка добавлена в Mochi: {front_text}")
        bot.answer_callback_query(call.id, "✅ Карточка добавлена в Mochi!", show_alert=False)

        # Обновляем кнопку на успешное сообщение
        success_keyboard = InlineKeyboardMarkup()
        success_btn = InlineKeyboardButton("✅ Добавлено в Mochi", callback_data="done")
        success_keyboard.add(success_btn)

        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=success_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка обновления кнопки: {e}")

        # Удаляем данные карточки
        del user_cards[message_id]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка добавления в Mochi: {error_msg}")
        bot.answer_callback_query(call.id, f"❌ Ошибка: {error_msg}", show_alert=True)


# FastAPI endpoints
@app.get("/")
async def root():
    return {"status": "Bot is running"}


@app.post("/webhook")
async def webhook(request: Request):
    """Обработка webhook от Telegram"""
    try:
        json_data = await request.json()
        logger.info(f"Received update_id: {json_data.get('update_id')}")

        # Обрабатываем сообщения напрямую
        if 'message' in json_data:
            message = telebot.types.Message.de_json(json_data['message'])
            logger.info(f"Message from {message.from_user.first_name}: {message.text}")

            # Вызываем обработчики напрямую
            if message.text and message.text.startswith('/start'):
                start_bot(message)
            else:
                translate_word(message)

        # Обрабатываем callback queries
        elif 'callback_query' in json_data:
            callback_query = telebot.types.CallbackQuery.de_json(json_data['callback_query'])
            logger.info(f"Callback query: {callback_query.data}")
            handle_add_to_mochi(callback_query)

        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error in webhook: {e}", exc_info=True)
        return Response(status_code=500)


@app.get("/set-webhook")
async def set_webhook():
    """Установка webhook URL"""
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        return JSONResponse(
            status_code=400,
            content={"error": "WEBHOOK_URL not set in environment"}
        )

    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{webhook_url}/webhook")
        return {"status": "Webhook set successfully", "url": webhook_url}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
