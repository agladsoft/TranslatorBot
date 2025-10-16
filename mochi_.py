import uuid
import requests
from mochi.auth import Auth
from typing import Optional
from mochi.client import Mochi


class MochiConnect:
    """Класс для работы с Mochi API через mochi-api-client"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        auth = Auth.Token(api_key)
        self.client = Mochi(auth=auth)

    def get_basic_template(self) -> Optional[dict]:
        """Получает шаблон Basic (с полями Front и Back)"""
        try:
            templates = self.client.templates.list_templates()

            # Ищем шаблон с именем "Basic" или первый доступный шаблон
            for template in templates:
                if template.get('name') and 'basic' in template['name'].lower():
                    # Получаем полную информацию о шаблоне
                    full_template = self.client.templates.get_template(template['id'])
                    print(f"Найден шаблон Basic: {full_template}")
                    return full_template

            # Если не нашли Basic, возвращаем первый шаблон (если есть)
            if templates and len(templates) > 0:
                full_template = self.client.templates.get_template(templates[0]['id'])
                print(f"Используем первый шаблон: {full_template}")
                return full_template

            return None
        except Exception as e:
            print(f"Ошибка получения шаблонов: {e}")
            return None

    def get_or_create_deck(self, deck_name: str) -> str:
        """Получает или создает колоду по имени и возвращает deck_id"""
        # Получаем список всех колод
        decks = self.client.decks.list_decks()

        # Ищем колоду с нужным именем
        for deck in decks:
            if deck.get('name') == deck_name:
                return deck['id']

        # Если не найдена, создаем новую
        new_deck = self.client.decks.create_deck(name=deck_name)
        return new_deck['id']

    def card_exists(self, deck_id: str, front_text: str) -> bool:
        """Проверяет, существует ли карточка с таким front текстом в колоде"""
        try:
            # Получаем все карточки из колоды
            cards = self.client.cards.list_cards(deck_id=deck_id)

            # Нормализуем искомый текст (убираем markdown заголовки и пробелы)
            normalized_search = front_text.replace('#', '').strip().lower()

            # Проверяем каждую карточку
            for card in cards:
                # Проверяем в полях
                fields = card.get('fields', {})
                for field_id, field_data in fields.items():
                    field_value = field_data.get('value', '')
                    normalized_field = field_value.replace('#', '').strip().lower()
                    if normalized_search in normalized_field or normalized_field in normalized_search:
                        print(f"Найдена существующая карточка: {card.get('id')}")
                        return True

                # Также проверяем content для карточек без шаблона
                content = card.get('content', '')
                normalized_content = content.replace('#', '').strip().lower()
                if normalized_search in normalized_content:
                    print(f"Найдена существующая карточка (по content): {card.get('id')}")
                    return True

            return False
        except Exception as e:
            print(f"Ошибка проверки дубликатов: {e}")
            # В случае ошибки разрешаем создание карточки
            return False

    def upload_attachment(self, card_id: str, filename: str, file_data: bytes) -> bool:
        """Загружает вложение к карточке через API эндпоинт"""
        try:
            url = f"https://app.mochi.cards/api/cards/{card_id}/attachments/{filename}"

            # Создаем multipart/form-data запрос точно как в curl примере
            # -F file="@/path/to/file" соответствует files={'file': ...}
            files = {'file': file_data}

            # Используем requests.post с HTTP Basic Auth (api_key как username, пустой password)
            # Не указываем Content-Type явно - requests сам установит multipart/form-data с boundary
            response = requests.post(
                url,
                files=files,
                auth=(self.api_key, ''),
                timeout=30
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Ошибка загрузки вложения: {e}")
            if hasattr(e, 'response'):
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return False

    def add_card(self, deck_id: str, front_text: str, back_text: str, image_url: Optional[str] = None) -> dict:
        """Добавляет карточку в Mochi с front и back полями"""

        # Получаем шаблон Basic
        template = self.get_basic_template()

        # Инициализируем переменные
        front_field_id = None
        back_field_id = None

        if template:
            template_id = template['id']

            # Получаем ID полей из шаблона
            fields_info = template.get('fields', {})
            print(f"Поля шаблона: {fields_info}")

            # Ищем ID полей "front" и "back" (или похожие)
            for field_id, field_data in fields_info.items():
                field_name = field_data.get('name', '').lower()
                if 'front' in field_name or field_name == 'name':
                    front_field_id = field_id
                elif 'back' in field_name:
                    back_field_id = field_id

            print(f"Front field ID: {front_field_id}, Back field ID: {back_field_id}")

            # Формируем поля карточки
            card_fields = {}
            if front_field_id:
                card_fields[front_field_id] = {
                    "id": front_field_id,
                    "value": front_text
                }
            if back_field_id:
                card_fields[back_field_id] = {
                    "id": back_field_id,
                    "value": back_text
                }

            # Создаем карточку с полями
            card = self.client.cards.create_card(
                content="",  # content не используется при работе с полями
                deck_id=deck_id,
                template_id=template_id,
                fields=card_fields
            )
        else:
            # Если шаблон не найден, создаем обычную карточку
            content = f"{front_text}\n---\n{back_text}"
            card = self.client.cards.create_card(content=content, deck_id=deck_id)

        print(f"Карточка создана: {card.get('id')}")

        # Если есть изображение, загружаем его как вложение
        if image_url and card:
            try:
                # Скачиваем изображение
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()

                # Генерируем уникальное имя файла
                card_id = card['id']
                filename = f"{uuid.uuid4().hex[:8]}.jpg"

                # Загружаем вложение
                if self.upload_attachment(card_id, filename, img_response.content):
                    # Обновляем front поле, добавив ссылку на изображение
                    if template and front_field_id:
                        # Добавляем изображение в начало front текста
                        updated_front = f"![](@media/{filename})\n\n{front_text}"

                        # Обновляем поле через update_card
                        updated_fields = card.get('fields', {})
                        if front_field_id in updated_fields:
                            updated_fields[front_field_id]['value'] = updated_front

                        self.client.cards.update_card(card_id=card_id, fields=updated_fields)
                        print(f"Изображение успешно добавлено в front: {filename}")
                    else:
                        # Для карточек без шаблона обновляем content
                        current_card = self.client.cards.get_card(card_id)
                        current_content = current_card.get('content', '')
                        updated_content = f"![](@media/{filename})\n\n{current_content}"
                        self.client.cards.update_card(card_id=card_id, content=updated_content)
                        print(f"Изображение успешно добавлено: {filename}")

            except Exception as e:
                print(f"Ошибка добавления изображения: {e}")

        return card

    def check_connection(self) -> bool:
        """Проверяет подключение к Mochi API"""
        try:
            self.client.decks.list_decks()
            return True
        except Exception as e:
            print(f"Ошибка подключения к Mochi: {e}")
            return False

    def close(self):
        """Закрывает соединение"""
        self.client.close()
