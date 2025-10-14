# Vocabulary Bot 📚

Telegram-бот для изучения языков с автоматическим добавлением слов в Anki.

## Возможности

- 🔄 **Двусторонний перевод**: Русский ↔ Английский
- 🖼️ **Изображения**: Автоматический поиск релевантных изображений для каждого слова
- 📝 **Примеры использования**: 3 примера с переводом для каждого слова
- 📚 **Интеграция с Anki**: Добавление карточек напрямую в Anki с автоматической синхронизацией
- ⚡ **Анимация загрузки**: Красивая GIF-анимация во время обработки запроса
- 👤 **Персональные колоды**: Отдельная колода для каждого пользователя
- 🐳 **Docker**: Простое развертывание через Docker Compose

## Требования

- Docker и Docker Compose
- Anki Desktop (для автоматического добавления карточек)
- Telegram Bot Token
- OpenAI API Key
- Unsplash API Key

## Быстрый старт

### 1. Установите AnkiConnect в Anki Desktop

- Откройте Anki
- Tools → Add-ons → Get Add-ons
- Введите код: `2055492159`
- Перезапустите Anki
- **Важно:** Anki должен быть запущен для работы бота!

### 2. Клонируйте репозиторий

```bash
git clone <repository_url>
cd TranslatorBot
```

### 3. Настройте конфигурацию

Скопируйте `.env.example` в `.env` и заполните ваши ключи:

```bash
cp .env.example .env
nano .env
```

Пример `.env`:
```env
TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
OPENAI_API_KEY=sk-...
UNSPLASH_ACCESS_KEY=your_unsplash_key
```

### 4. Запустите с помощью Docker Compose

```bash
docker-compose up -d
```

Проверить логи:
```bash
docker-compose logs -f
```

Остановить бота:
```bash
docker-compose down
```

## Получение API ключей

### Telegram Bot Token

1. Найдите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям и выберите имя для бота
4. Скопируйте токен

### OpenAI API Key

1. Зарегистрируйтесь на [OpenAI](https://platform.openai.com/)
2. Перейдите в раздел API Keys
3. Создайте новый ключ
4. Скопируйте ключ (он показывается только один раз!)

### Unsplash Access Key

1. Зарегистрируйтесь на [Unsplash Developers](https://unsplash.com/developers)
2. Создайте новое приложение
3. Скопируйте Access Key из настроек приложения

## Альтернативный запуск (без Docker)

### Установка

```bash
# Установите зависимости
pip install -r requirements.txt

# Создайте .env файл
cp .env.example .env
# Отредактируйте .env и добавьте ваши ключи
```

### Запуск

```bash
# Убедитесь, что Anki Desktop запущен!
python main.py
```

## Использование

1. Откройте бота в Telegram и отправьте `/start`
2. Отправьте слово или фразу боту
3. Бот автоматически определит язык и переведет:
   - Русский → Английский
   - Английский → Русский
4. Получите перевод с изображением и примерами
5. Нажмите кнопку **"📚 Добавить в Anki"**
6. Карточка автоматически добавится в Anki и синхронизируется с AnkiWeb

## Структура проекта

```
TranslatorBot/
├── main.py              # Основной файл бота
├── anki.py              # Модуль для работы с AnkiConnect
├── Dockerfile           # Docker конфигурация
├── docker-compose.yml   # Docker Compose конфигурация
├── .env.example         # Пример файла конфигурации
├── .dockerignore        # Файлы, игнорируемые Docker
├── requirements.txt     # Зависимости Python
└── README.md           # Документация
```

## Формат карточек Anki

**Лицевая сторона:**
- Слово на исходном языке
- Изображение

**Обратная сторона:**
- Перевод
- 3 примера использования с переводом

Каждый пользователь получает свою колоду: `Vocabulary Bot - {Имя пользователя}`

## Технологии

- **Python 3.11**: Основной язык
- **pyTelegramBotAPI**: Работа с Telegram Bot API
- **LangChain + OpenAI**: Генерация переводов и примеров (GPT-4)
- **AnkiConnect**: Интеграция с Anki
- **Unsplash API**: Поиск релевантных изображений
- **Docker & Docker Compose**: Контейнеризация
- **python-dotenv**: Управление конфигурацией

## Устранение неполадок

### Ошибка подключения к Anki

- ✅ Убедитесь, что Anki Desktop **запущен**
- ✅ Проверьте, что AnkiConnect установлен (код: `2055492159`)
- ✅ Перезапустите Anki
- ✅ Если используете Docker, убедитесь, что используется `network_mode: host`

### Синхронизация не работает

- ✅ Проверьте настройки синхронизации в Anki (Preferences → Network)
- ✅ Убедитесь, что вы вошли в AnkiWeb аккаунт
- ✅ Попробуйте синхронизировать вручную один раз

### Изображения не загружаются

- ✅ Проверьте правильность `UNSPLASH_ACCESS_KEY` в `.env`
- ✅ Убедитесь, что у вас есть интернет-соединение
- ✅ Проверьте квоты Unsplash API (50 запросов/час для бесплатного плана)

### Бот не отвечает

- ✅ Проверьте логи: `docker-compose logs -f`
- ✅ Убедитесь, что `TOKEN` в `.env` правильный
- ✅ Проверьте баланс OpenAI API

## Docker команды

```bash
# Запустить бота
docker-compose up -d

# Посмотреть логи
docker-compose logs -f

# Перезапустить бота
docker-compose restart

# Остановить бота
docker-compose down

# Пересобрать и запустить
docker-compose up -d --build
```