import os
import telebot
import requests
from typing import Optional
from anki import AnkiConnect
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

load_dotenv()

bot = telebot.TeleBot(os.environ["TOKEN"])

# Хранилище для временных данных карточек
user_cards = {}

# Настройка LangChain с OpenAI
llm = ChatOpenAI(
    model="gpt-4o-mini",
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
        print(f"Извлечено ключевое слово для поиска: {keyword}")
        return keyword
    except Exception as e:
        print(f"Ошибка извлечения ключевого слова: {e}")
        # Если не удалось извлечь, возвращаем первое слово
        return text.split()[0] if text else text


def get_image_url(query: str) -> Optional[str]:
    """Получает URL изображения через Unsplash API"""
    try:
        # Используем Unsplash API для поиска изображений
        access_key = os.getenv("UNSPLASH_ACCESS_KEY")

        if not access_key:
            print("UNSPLASH_ACCESS_KEY не найден в .env")
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
        print(f"Ошибка получения изображения: {e}")
        return None


@bot.message_handler(commands=['start'])
def start_bot(message: Message) -> None:
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я бот-переводчик. Отправь мне слово или фразу:\n"
        "• Русский → Английский\n"
        "• Английский → Русский\n\n"
        "Я автоматически определю язык и переведу с примерами использования.\n\n"
        "Просто напиши слово и отправь мне!"
    )
    bot.send_message(message.chat.id, welcome_text)


@bot.message_handler(func=lambda message: True)
def translate_word(message: Message) -> None:
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
        print(f"Получен URL изображения: {image_url}")

        # Создаем кнопку для добавления в Anki
        keyboard = InlineKeyboardMarkup()
        add_to_anki_btn = InlineKeyboardButton("📚 Добавить в Anki", callback_data=f"add_anki_{message.message_id}")
        keyboard.add(add_to_anki_btn)

        # Сохраняем данные карточки для последующего добавления в Anki
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
                print("Изображение успешно отправлено")
            except Exception as img_error:
                # Если не удалось отправить фото, отправляем только текст
                print(f"Ошибка отправки изображения: {img_error}")
                bot.reply_to(message, formatted_response, parse_mode='Markdown', reply_markup=keyboard)
        else:
            print("URL изображения не получен, отправляем только текст")
            bot.reply_to(message, formatted_response, parse_mode='Markdown', reply_markup=keyboard)

        # Удаляем GIF с загрузкой
        if loading_msg:
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except:
                pass

    except Exception as e:
        # Удаляем GIF в случае ошибки
        if loading_msg:
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except:
                pass
        bot.reply_to(message, f"Произошла ошибка при переводе: {str(e)}\nПопробуйте еще раз.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_anki_'))
def handle_add_to_anki(call: CallbackQuery):
    try:
        # Извлекаем message_id из callback_data
        message_id = int(call.data.split('_')[2])

        if message_id not in user_cards:
            bot.answer_callback_query(call.id, "❌ Данные карточки не найдены", show_alert=True)
            return

        card_data = user_cards[message_id]

        # Создаем подключение к AnkiConnect
        anki = AnkiConnect()

        # Проверяем подключение
        if not anki.check_connection():
            bot.answer_callback_query(
                call.id,
                "❌ Не удалось подключиться к Anki.\nУбедитесь, что Anki запущен и установлен плагин AnkiConnect.",
                show_alert=True
            )
            return

        # Проверяем/создаем модель
        anki.ensure_model_exists()

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
                # Форматируем примеры в список
                examples = examples_text.replace("\n", "<br>")
            else:
                translation = parts.strip()

        # Добавляем карточку напрямую в Anki
        image_filename = f"vocab_{message_id}.jpg" if card_data['image_url'] else None

        anki.add_note(
            deck_name="Vocabulary Bot",
            word=card_data['word'],
            translation=translation if translation else ai_text,
            examples=examples,
            image_url=card_data['image_url'],
            image_filename=image_filename
        )

        bot.answer_callback_query(call.id, "✅ Карточка добавлена в Anki!", show_alert=False)

        # Запускаем синхронизацию с AnkiWeb
        sync_status = "🔄 Синхронизация запущена..."
        sync_msg = bot.send_message(call.message.chat.id, sync_status)

        try:
            if anki.sync():
                bot.edit_message_text(
                    "✅ Карточка успешно добавлена и синхронизирована!\nОна доступна на всех ваших устройствах.",
                    call.message.chat.id,
                    sync_msg.message_id
                )
            else:
                bot.edit_message_text(
                    "✅ Карточка добавлена в Anki!\n⚠️ Автоматическая синхронизация не удалась. Синхронизируйте вручную.",
                    call.message.chat.id,
                    sync_msg.message_id
                )
        except Exception as sync_error:
            print(f"Ошибка синхронизации: {sync_error}")
            bot.edit_message_text(
                "✅ Карточка добавлена в Anki!\n⚠️ Синхронизация не удалась. Синхронизируйте вручную.",
                call.message.chat.id,
                sync_msg.message_id
            )

        # Удаляем данные карточки
        del user_cards[message_id]

    except Exception as e:
        error_msg = str(e)
        print(f"Ошибка добавления в Anki: {error_msg}")

        if "cannot create note because it is a duplicate" in error_msg.lower():
            bot.answer_callback_query(call.id, "⚠️ Эта карточка уже есть в Anki", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"❌ Ошибка: {error_msg}", show_alert=True)


if __name__ == "__main__":
    bot.infinity_polling()
