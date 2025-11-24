from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import html

from db.user_queries import get_user_by_id, create_user
from db.user_queries import create_referral, get_user_by_id as get_referrer_user

router = Router()

def is_private_chat(chat_id: int, user_id: int) -> bool:
    """Проверяет, находится ли пользователь в личном чате с ботом"""
    return chat_id == user_id

def create_welcome_keyboard(is_private_chat: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для приветственного сообщения"""
    if is_private_chat:
        # В личном чате - обычные кнопки меню
        buttons = [
            [InlineKeyboardButton(text="📋 Открыть меню", callback_data="open_menu")],
            [InlineKeyboardButton(text="📦 Магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral_system")]
        ]
    else:
        # В групповом чате - кнопка для перехода в бота
        buttons = [
            [InlineKeyboardButton(text="🎮 Перейти к боту", url="https://t.me/footyCards2bot")],
            [InlineKeyboardButton(text="📦 Открыть магазин", url="https://t.me/footyCards2bot?start=shop")],
            [InlineKeyboardButton(text="👥 Пригласить друзей", url="https://t.me/footyCards2bot?start=ref")]
        ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(CommandStart())
async def start(message: Message, state: FSMContext, bot) -> None:
    """Обработчик команды /start с поддержкой реферальных ссылок"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = html.escape(message.from_user.full_name)
    
    # Обновляем юзернейм пользователя
    if hasattr(message.from_user, 'username') and message.from_user.username:
        from db.user_queries import update_user_uz
        await update_user_uz(user_id, message.from_user.username)
    
    # Проверяем тип чата
    is_private = is_private_chat(chat_id, user_id)
    
    # Если команда вызвана не в личном чате, показываем упрощенное приветствие
    if not is_private:
        welcome_text = f"""
⚽ <b>Добро пожаловать в FootyCards 2!</b> 🏆

🎴 <b>Коллекционная карточная игра про футбол</b>

💫 <b>Что вас ждет:</b>
• Собирайте карточки футболистов
• Открывайте паки с игроками
• Участвуйте в тренировках и матчах
• Обменивайтесь картами с другими игроками
• Соревнуйтесь за место в рейтинге

🚀 <b>Чтобы начать играть, перейдите в личный чат с ботом!</b>

<i>Нажмите кнопку ниже чтобы продолжить</i> 👇
"""
        
        keyboard = create_welcome_keyboard(is_private)
        
        await message.reply(
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    # Дальше идет оригинальная логика для личного чата
    # Проверяем реферальный параметр
    args = message.text.split()
    referrer_id = None
    referral_bonus = 0
    
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1][4:])  # Извлекаем ID из ref_12345
            
            # Проверяем что пользователь не приглашает сам себя
            if referrer_id == user_id:
                referrer_id = None
            else:
                # Проверяем существует ли приглашающий
                referrer = await get_referrer_user(referrer_id)
                if not referrer:
                    referrer_id = None
        except ValueError:
            referrer_id = None
    
    # Проверяем есть ли пользователь в БД, если нет - добавляем
    user = await get_user_by_id(user_id)
    is_new_user = not user
    
    if is_new_user:
        # Создаем нового пользователя с бонусом за реферал
        start_balance = 400
        if referrer_id:
            start_balance += 50  # Дополнительный бонус новому пользователю за переход по ссылке
            referral_bonus = 50
        
        user = await create_user(
            user_id=user_id,
            username=username,
            balance=start_balance
        )
        
        # Если есть реферальная ссылка, создаем связь
        if referrer_id:
            await create_referral(referrer_id, user_id)
            
            # Отправляем сообщение приглашающему
            try:
                referred_username = message.from_user.username or message.from_user.first_name
                
                # Создаем клавиатуру с кнопкой меню
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Главное меню", callback_data="open_menu")],
                    [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral_system")]
                ])
                
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 <b>У вас новый реферал!</b>\n\n"
                        f"Пользователь <b>{referred_username}</b> присоединился по вашей ссылке!\n"
                        f"💫 <b>Бонус:</b> +50 монет новому игроку\n\n"
                        f"Как только он откроет пак и пройдет тренировку, вы оба получите основные награды! 💰\n\n"
                        f"🔗 <b>Ваша реферальная ссылка работает!</b>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Не удалось отправить уведомление приглашающему {referrer_id}: {e}")
    
    # Разные тексты для новых и существующих пользователей
    if is_new_user:
        if referrer_id:
            welcome_text = f"""
⚽ <b>Добро пожаловать в FootyCards 2!</b>

🎁 <b>Реферальный бонус активирован!</b>
💫 Вы получили <b>+50 монет</b> за переход по ссылке друга!

🎯 <b>Начни своё футбольное приключение:</b>

<blockquote>
📦 <b>1. Открывай паки</b> - Начни с бесплатного пака в магазине
🃏 <b>2. Используйте команду футКарта2</b> - ОТкрывай дополнительные карточки!
🔄 <b>3. Получай карты</b> - Собирай уникальных футболистов  
🎮 <b>4. Играй и зарабатывай</b> - Участвуй в игровых режимах
💎 <b>5. Улучшай коллекцию</b> - Покупай новые паки на заработанные монеты
</blockquote>

💰 <b>Ваш баланс:</b> 250 монет (200 стартовых + 50 реферальных)

🎊 <b>Чтобы получить полную награду:</b>
• Открой хотя бы 1 пак карточек
• Пройди хотя бы 1 тренировку
• После этого получишь ещё <b>200 монет</b>!

⚡ <b>Ваш друг тоже получит награду!</b>

<i>Начни с магазина паков → открой бесплатный пак → играй и зарабатывай!</i> 🚀
            """
        else:
            welcome_text = f"""
⚽ <b>Добро пожаловать в FootyCards 2!</b>

🎯 <b>Начни своё футбольное приключение:</b>

<blockquote>
📦 <b>1. Открывай паки</b> - Начни с бесплатного пака в магазине
🃏 <b>2. Используйте команду футКарта2</b> - ОТкрывай дополнительные карточки!
🔄 <b>3. Получай карты</b> - Собирай уникальных футболистов
🎮 <b>4. Играй и зарабатывай</b> - Участвуй в игровых режимах
💎 <b>5. Улучшай коллекцию</b> - Покупай новые паки на заработанные монеты
</blockquote>

💰 <b>Стартовый бонус:</b> 400 монет для первых покупок!

👥 <b>Хочешь получить больше монет?</b>
Приглашай друзей и получай до 1000+ монет за каждого!
Найди реферальную систему в меню.

🎁 <b>Прямо сейчас доступен бесплатный пак!</b>
💫 Открывается <b>каждые 3 часа</b> - не пропусти!

<i>Начни с магазина паков → открой бесплатный пак → играй и зарабатывай!</i> 🚀
            """
    else:
        # Для существующих пользователей показываем обычное приветствие
        welcome_text = f"""
⚽ <b>С возвращением, {username}!</b> 🏆

🎯 <b>Продолжаем футбольное приключение:</b>

<blockquote>
📦 <b>Магазин паков</b> - Проверь, готов ли бесплатный пак
🃏 <b>Используйте команду футКарта2</b> - ОТкрывай дополнительные карточки!
🎮 <b>Игровые режимы</b> - Зарабатывай монеты для новых паков
🃏 <b>Мои карты</b> - Смотри свою коллекцию и прогресс
🏪 <b>Маркет</b> - Обменивайся картами с другими игроками
👥 <b>Пригласить друзей</b> - Получай бонусы за рефералов
</blockquote>

💡 <b>Помни:</b> Бесплатный пак обновляется каждые 3 часа!
⚡ Зарабатывай монеты в игровых режимах для ещё больше паков!

👥 <b>Реферальная система:</b>
Приглашай друзей и получай до 1000+ монет за каждого!

<i>К новым футбольным достижениям!</i> ⚽
        """

    # Создаем кнопки в зависимости от ситуации
    if is_new_user and referrer_id:
        buttons = [
            [InlineKeyboardButton(text="📦 Открыть магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="⚔️ Начать тренировку", callback_data="open_training")],
            [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referral_system")],
            [InlineKeyboardButton(text="📋 Полное меню", callback_data="open_menu")]
        ]
    elif is_new_user:
        buttons = [
            [InlineKeyboardButton(text="📦 Открыть магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referral_system")],
            [InlineKeyboardButton(text="📋 Полное меню", callback_data="open_menu")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="📋 Открыть меню", callback_data="open_menu")]
        ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Отправляем сообщение с кнопкой перехода в меню
    await message.answer(
        text=welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()

@router.callback_query(F.data == "open_menu")
async def open_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки открытия меню"""
    # Проверяем, находится ли пользователь в личном чате
    if not is_private_chat(callback.message.chat.id, callback.from_user.id):
        await callback.answer("⚠️ Перейдите в личный чат с ботом для использования меню", show_alert=True)
        return
    
    from handlers.main_menu import show_menu  # Импортируем здесь чтобы избежать циклического импорта
    await show_menu(callback, state)