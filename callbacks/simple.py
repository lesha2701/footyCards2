from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "say_hello")
async def say_hello(query: CallbackQuery) -> None:
    await query.answer("Hello!")