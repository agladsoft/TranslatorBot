import base64
import requests
from typing import Optional, Any


class AnkiConnect:
    """Класс для работы с AnkiConnect API"""

    def __init__(self, url: str = "http://localhost:8765"):
        self.url = url

    def request(self, action: str, **params) -> Any:
        """Отправляет запрос к AnkiConnect"""
        payload = {
            "action": action,
            "version": 6,
            "params": params
        }
        response = requests.post(self.url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if len(result) != 2:
            raise Exception('response has an unexpected number of fields')
        if 'error' not in result:
            raise Exception('response is missing required error field')
        if 'result' not in result:
            raise Exception('response is missing required result field')
        if result['error'] is not None:
            raise Exception(result['error'])

        return result['result']

    def create_deck(self, deck_name: str):
        """Создает колоду если её нет"""
        return self.request("createDeck", deck=deck_name)

    def add_note(self, deck_name: str, word: str, translation: str, examples: str,
                 image_url: Optional[str] = None, image_filename: Optional[str] = None):
        """Добавляет карточку в Anki"""

        # Создаем колоду если её нет
        self.create_deck(deck_name)

        # Формируем поля карточки
        fields = {
            "Word": word,
            "Translation": translation,
            "Examples": examples
        }

        # Добавляем изображение если есть
        picture = None
        if image_url and image_filename:
            try:
                # Скачиваем изображение
                img_response = requests.get(image_url, timeout=10)
                img_data = base64.b64encode(img_response.content).decode('utf-8')

                picture = {
                    "url": image_url,
                    "filename": image_filename,
                    "data": img_data,
                    "fields": ["Image"]
                }
            except Exception as e:
                print(f"Ошибка загрузки изображения: {e}")

        # Формируем запрос на добавление карточки
        note = {
            "deckName": deck_name,
            "modelName": "VocabularyBot",
            "fields": fields,
            "options": {
                "allowDuplicate": False
            },
            "tags": ["vocabulary-bot"]
        }

        if picture:
            note["picture"] = [picture]

        return self.request("addNote", note=note)

    def ensure_model_exists(self, model_name: str = "VocabularyBot"):
        """Проверяет и создает модель карточки если её нет"""
        try:
            models = self.request("modelNames")
            if model_name in models:
                return True

            # Создаем модель
            model = {
                "modelName": model_name,
                "inOrderFields": ["Word", "Translation", "Examples", "Image"],
                "css": """
                    .card {
                        font-family: arial;
                        font-size: 20px;
                        text-align: center;
                        color: black;
                        background-color: white;
                    }
                    .word {
                        font-size: 32px;
                        font-weight: bold;
                        margin-bottom: 20px;
                    }
                    img {
                        max-width: 400px;
                        max-height: 300px;
                        margin: 20px 0;
                    }
                """,
                "cardTemplates": [
                    {
                        "Name": "Card 1",
                        "Front": '<div class="word">{{Word}}</div>{{Image}}',
                        "Back": '{{FrontSide}}<hr id="answer"><div>{{Translation}}</div><div style="font-size: 16px; margin-top: 10px;">{{Examples}}</div>'
                    }
                ]
            }

            self.request("createModel", **model)
            return True
        except Exception as e:
            print(f"Ошибка создания модели: {e}")
            return False

    def check_connection(self) -> bool:
        """Проверяет подключение к Anki"""
        try:
            self.request("version")
            return True
        except Exception as e:
            print(f"Ошибка подключения к Anki: {e}")
            return False

    def sync(self):
        """Синхронизирует Anki с AnkiWeb"""
        try:
            self.request("sync")
            return True
        except Exception as e:
            print(f"Ошибка синхронизации: {e}")
            return False
