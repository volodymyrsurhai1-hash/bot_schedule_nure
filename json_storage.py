import json
import os
from pathlib import Path

import aiofiles


class ChatStorage:
    """Класс для работы с JSON хранилищем чатов и групп"""

    def __init__(self, file_path: str = "jsons/chats.json"):
        self.file_path = Path(file_path)
        self._ensure_directory()

    def _ensure_directory(self):
        """Создает директорию для JSON файлов если её нет"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def save_chat_group(self, chat_id: int, group_id: int):
        """
        Сохраняет связь между chat_id и group_id

        Args:
            chat_id: ID чата в Telegram
            group_id: ID группы из API расписания
        """
        chats = await self.get_all_chats()
        chats[str(chat_id)] = group_id

        async with aiofiles.open(self.file_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(chats, indent=4, ensure_ascii=False))

    async def get_group_id(self, chat_id: int) -> int | None:
        """
        Получает group_id по chat_id

        Args:
            chat_id: ID чата в Telegram

        Returns:
            ID группы или None если не найдено
        """
        if not os.path.exists(self.file_path):
            return None

        try:
            async with aiofiles.open(self.file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                chats = json.loads(content)
                return chats.get(str(chat_id))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    async def get_all_chats(self) -> dict:
        """
        Возвращает словарь всех сохраненных чатов

        Returns:
            Словарь в формате {"chat_id": group_id}
        """
        if not os.path.exists(self.file_path):
            return {}

        try:
            async with aiofiles.open(self.file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            return {}

    async def delete_chat(self, chat_id: int) -> bool:
        """
        Удаляет чат из хранилища

        Args:
            chat_id: ID чата в Telegram

        Returns:
            True если чат был удален, False если чата не было
        """
        chats = await self.get_all_chats()
        chat_key = str(chat_id)

        if chat_key in chats:
            del chats[chat_key]
            async with aiofiles.open(self.file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(chats, indent=4, ensure_ascii=False))
            return True
        return False

    async def chat_exists(self, chat_id: int) -> bool:
        """
        Проверяет существует ли чат в хранилище

        Args:
            chat_id: ID чата в Telegram

        Returns:
            True если чат существует
        """
        chats = await self.get_all_chats()
        return str(chat_id) in chats
