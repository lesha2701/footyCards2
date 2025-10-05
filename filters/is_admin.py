from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery


class IsAdmin(BaseFilter):

    def __init__(self, user_ids: int | list[int]) -> None:
        self._user_ids = user_ids

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if isinstance(self._user_ids, int):
            return event.from_user.id == self._user_ids
        return event.from_user.id in self._user_ids