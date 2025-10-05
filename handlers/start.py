from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import html

from db.user_queries import get_user_by_id, create_user

router = Router()

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    """Обработчик команды /start с красивым оформлением"""
    user_id = message.from_user.id
    username = html.escape(message.from_user.full_name)
    
    # Проверяем есть ли пользователь в БД, если нет - добавляем
    user = await get_user_by_id(user_id)
    is_new_user = not user
    
    if is_new_user:
        await create_user(
            user_id=user_id,
            username=username,
            balance=100  # Стартовый бонус
        )
    
    # Разные тексты для новых и существующих пользователей
    if is_new_user:
        welcome_text = f"""
🎉 <b>Добро пожаловать в FootyCards 2!</b> ⚽

<b>Твой футбольный мир коллекционных карт:</b>

<blockquote>🏆 <b>Собирай</b> - Открывай паки с уникальными картами игроков
⭐ <b>Коллекционируй</b> - Получи все карты из ограниченных коллекций
🔄 <b>Обменивайся</b> - Торгуй картами с другими коллекционерами
🏅 <b>Соревнуйся</b> - Участвуй в турнирах и поднимайся в рейтинге</blockquote>

🎁 <b>Стартовый бонус:</b> 100 монет для первых паков!

<i>Готов начать своё футбольное приключение?</i> 🚀
        """
    else:
        welcome_text = f"""
⚽ <b>С возвращением, {username}!</b> 🏆

Твоя коллекция ждёт тебя! Продолжай собирать уникальные карты футболистов.

🎯 <b>Что будем делать сегодня?</b>
<blockquote>• Откроем новые паки? 📦
• Проверим новые коллекции? 🎨
• Может обменяемся картами? 🔄</blockquote>

<i>Вперёд к новым футбольным трофеям!</i>
        """

    button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Открыть меню", callback_data="open_menu")]
    ])
    
    # Отправляем сообщение с кнопкой перехода в меню
    await message.answer(
        text=welcome_text,
        reply_markup=button,
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()