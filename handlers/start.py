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
⚽ <b>Добро пожаловать в FootyCards 2!</b>

🎯 <b>Начни своё футбольное приключение:</b>

<blockquote>
📦 <b>1. Открывай паки</b> - Начни с бесплатного пака в магазине
🔄 <b>2. Получай карты</b> - Собирай уникальных футболистов
🎮 <b>3. Играй и зарабатывай</b> - Участвуй в игровых режимах
💎 <b>4. Улучшай коллекцию</b> - Покупай новые паки на заработанные монеты
</blockquote>

🎁 <b>Прямо сейчас доступен бесплатный пак!</b>
💫 Открывается <b>каждые 3 часа</b> - не пропусти!

💰 <b>Стартовый бонус:</b> 100 монет для первых покупок!

<i>Начни с магазина паков → открой бесплатный пак → играй и зарабатывай!</i> 🚀
            """
    else:
        welcome_text = f"""
⚽ <b>С возвращением, {username}!</b> 🏆

🎯 <b>Продолжаем футбольное приключение:</b>

<blockquote>
📦 <b>Магазин паков</b> - Проверь, готов ли бесплатный пак
🎮 <b>Игровые режимы</b> - Зарабатывай монеты для новых паков
🃏 <b>Мои карты</b> - Смотри свою коллекцию и прогресс
🏪 <b>Маркет</b> - Обменивайся картами с другими игроками
</blockquote>

💡 <b>Помни:</b> Бесплатный пак обновляется каждые 3 часа!
⚡ Зарабатывай монеты в игровых режимах для ещё больше паков!

<i>К новым футбольным достижениям!</i> ⚽
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