from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile 
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from datetime import datetime, timedelta
import html
import random
import asyncio
import os

from db.pack_queries import *
from db.user_queries import *
from db.card_queries import *

# В ваш config.py добавьте:
class ChatPackConfig:
    # Ключевое слово для активации
    TRIGGER_WORD = "футкарта2"
    
    # Кд между открытиями (3 часа как у обычных паков)
    COOLDOWN_HOURS = 3
    
    # Шансы выпадения для чат-паков
    CHANCE_COMMON = 64
    CHANCE_RARE = 30
    CHANCE_EPIC = 5
    CHANCE_LEGENDARY = 1
    
    # Бонус за первую карту
    FIRST_CARD_BONUS = 200

router = Router()

def is_private_chat(chat_id: int, user_id: int) -> bool:
    """Проверяет, находится ли пользователь в личном чате с ботом"""
    return chat_id == user_id

def create_chat_pack_keyboard(is_first_card: bool, is_private_chat: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для сообщения с карточкой"""
    
    if is_private_chat:
        # Если уже в личном чате - показываем обычные кнопки
        if is_first_card:
            buttons = [
                [InlineKeyboardButton(text="📦 Открыть паки в магазине", callback_data="show_shop_packs")],
                [InlineKeyboardButton(text="🃏 Мои карточки", callback_data="my_cards")],
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="open_menu")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="📦 Открыть ещё паки", callback_data="show_shop_packs")],
                [InlineKeyboardButton(text="🃏 Моя коллекция", callback_data="my_cards")],
                [InlineKeyboardButton(text="⚔️ Тренировка", callback_data="open_training")]
            ]
    else:
        # Если в групповом чате - кнопка для перехода в бота
        if is_first_card:
            buttons = [
                [InlineKeyboardButton(text="📦 Открыть паки в магазине", url="https://t.me/footyCards2bot?start=shop")]
            ]
        else:
            buttons = [
                [InlineKeyboardButton(text="📦 Открыть ещё паки", url="https://t.me/footyCards2bot?start=shop")]
            ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Исправленный фильтр - используем lower() для регистронезависимого сравнения
@router.message(F.text)
async def open_chat_pack(message: Message, bot: Bot):
    """Обработчик открытия карточки в чате по ключевому слову"""
    
    # Проверяем, содержит ли сообщение ключевое слово (регистронезависимо)
    text = message.text.strip().lower()
    trigger = ChatPackConfig.TRIGGER_WORD.lower()
    
    # Игнорируем сообщения, которые не содержат ключевое слово
    if trigger not in text:
        return
    
    # Дополнительная проверка: слово должно быть отдельным, а не частью другого слова
    words = text.split()
    if trigger not in words:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id  # ID сообщения для ответа
    username = html.escape(message.from_user.full_name)
    
    # Проверяем, может ли пользователь открыть пак (ГЛОБАЛЬНАЯ проверка)
    can_open, reason = await can_open_chat_pack(user_id)
    
    if not can_open:
        is_private = is_private_chat(chat_id, user_id)
        keyboard = create_chat_pack_keyboard(False, is_private)
        
        # Отправляем ответ с указанием message_id для ответа
        await bot.send_message(
            chat_id=chat_id,
            text=f"⏰ {username}, следующую карточку можно будет открыть через {reason}\n\n",
            reply_markup=keyboard,
            reply_to_message_id=message_id  # Важно: указываем на какое сообщение отвечаем
        )
        return
    
    # Получаем или создаем запись пользователя
    user = await get_user_by_id(user_id)
    is_first_card = not user
    
    # ОБНОВЛЯЕМ ГЛОБАЛЬНЫЙ СТАТУС ОТКРЫТИЙ ДО генерации карточки
    if await get_chat_pack_status(user_id):
        # Обновляем запись - устанавливаем cooldown
        await update_chat_pack_opening(user_id)
    else:
        # Создаем запись с cooldown
        await create_chat_pack_record_with_cooldown(user_id)
    
    # Генерируем карточку с шансами из конфига
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        number = random.randint(0, 99)
        
        if number < ChatPackConfig.CHANCE_COMMON:
            card = await getCard(conn, 'common')
            rarity = 'common'
        elif number < ChatPackConfig.CHANCE_COMMON + ChatPackConfig.CHANCE_RARE:
            card = await getCard(conn, 'rare') 
            rarity = 'rare'
        elif number < ChatPackConfig.CHANCE_COMMON + ChatPackConfig.CHANCE_RARE + ChatPackConfig.CHANCE_EPIC:
            card = await getCard(conn, 'epic')
            rarity = 'epic'
        else:
            card = await getCard(conn, 'legendary')
            rarity = 'legendary'
    
    if not card:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Не удалось сгенерировать карточку. Попробуйте позже.",
            reply_to_message_id=message_id
        )
        return
    
    if is_first_card:
        # Создаем нового пользователя
        user = await create_user(
            user_id=user_id,
            username=username,
            balance=200  # Стартовый баланс
        )
        # Выдаем бонус за первую карту
        await update_user_balance(user_id, ChatPackConfig.FIRST_CARD_BONUS)
        current_balance = 400
    else:
        current_balance = user['balance']
    
    # Добавляем карточку пользователю
    user_card = await add_card_to_user(user_id, card['id'])
    
    if not user_card:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ Ошибка при добавлении карточки в коллекцию.",
            reply_to_message_id=message_id
        )
        return
    
    # Формируем сообщение с карточкой
    card_text = await format_card_message(card, user_card, rarity, is_first_card, user_id, current_balance)
    
    # Определяем тип чата и создаем соответствующую клавиатуру
    is_private = is_private_chat(chat_id, user_id)
    keyboard = create_chat_pack_keyboard(is_first_card, is_private)
    
    # Отправляем карточку с фото как ответ на сообщение
    await send_card_with_photo_reply(bot, chat_id, message_id, card, card_text, keyboard, rarity)

async def send_card_with_photo_reply(bot: Bot, chat_id: int, reply_to_message_id: int, card: Dict, text: str, keyboard: InlineKeyboardMarkup, rarity: str):
    """Отправляет карточку с фотографией игрока как ответ на сообщение"""
    try:
        # Получаем путь к изображению
        image_path = f"players/{card['rarity']}/{card['uniq_name']}.jpg"

        if os.path.exists(image_path):
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                reply_to_message_id=reply_to_message_id  # Отвечаем на конкретное сообщение
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                reply_to_message_id=reply_to_message_id  # Отвечаем на конкретное сообщение
            )
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")
        # Фолбэк на текстовое сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            reply_to_message_id=reply_to_message_id  # Отвечаем на конкретное сообщение
        )

async def send_card_with_photo(bot: Bot, chat_id: int, card: Dict, text: str, keyboard: InlineKeyboardMarkup, rarity: str):
    """Отправляет карточку с фотографией игрока"""
    try:
        # Получаем путь к изображению
        image_path = f"players/{card['rarity']}/{card['uniq_name']}.jpg"

        if os.path.exists(image_path):
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Ошибка при отправке фото: {e}")
        # Фолбэк на текстовое сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

async def format_card_message(card: Dict, user_card: Dict, rarity: str, is_first_card: bool, user_id: int, balance: int) -> str:
    """Форматирует сообщение с карточкой в стиле вашего бота"""
    
    rarity_emoji = {
        'common': '⚪',
        'rare': '🔵',
        'epic': '🟣', 
        'legendary': '🟡'
    }.get(rarity, '⚪')
    
    # Базовое сообщение с карточкой
    text = f"""
{rarity_emoji} <b>🎴 НОВАЯ КАРТОЧКА!</b> {rarity_emoji}

<blockquote>👤 <b>{card['player_name']}</b>
{rarity_emoji} <b>Редкость:</b> {rarity.capitalize()}
🎯 <b>Рейтинг:</b> {card['weight']}
🏷️ <b>Коллекция:</b> {card.get('collection_name', 'Базовая')}
🔢 <b>Номер:</b> #{user_card['serial_number']}</blockquote>
"""    
    # Добавляем поздравление для первой карты
    if is_first_card:
        text += f"""
🎉 <b>ПОЗДРАВЛЯЕМ С ПЕРВОЙ КАРТОЧКОЙ!</b>

💫 Вы получаете <b>{ChatPackConfig.FIRST_CARD_BONUS} монет</b> в подарок!
💰 Теперь у вас <b>{balance} монет</b> (200 стартовых + 200 бонус)

🚀 <i>Продолжайте собирать коллекцию!</i>
"""
    else:
        # Получаем глобальную статистику для пользователя
        pack_status = await get_chat_pack_status(user_id)
        total_opened = pack_status['total_opened'] if pack_status else 1
        
        text += f"""
💫 <b>Карточка добавлена в вашу коллекцию!</b>

📊 Всего открыто в чатах: <b>{total_opened}</b>
⏰ Следующая карточка через: <b>3 часа</b>
"""
    
    return text

# Команда для проверки статуса
@router.message(Command("футкартастатус"))
async def check_chat_pack_status(message: Message):
    """Показывает статус открытия карточек в чате"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    can_open, reason = await can_open_chat_pack(user_id)
    
    # Определяем тип чата
    is_private = is_private_chat(chat_id, user_id)
    
    if can_open:
        if reason == "first_time":
            text = "🎴 Вы можете открыть свою первую карточку в любом чате!\n\nНапишите 'футКарта' чтобы получить карточку игрока!"
        else:
            text = "✅ Вы можете открыть карточку в любом чате!\n\nНапишите 'футКарта' чтобы получить карточку игрока!"
    else:
        text = f"⏰ Следующую карточку можно будет открыть через {reason}\n\n💡 Паки в магазине доступны всегда!"
    
    # Создаем клавиатуру в зависимости от типа чата
    if is_private:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Открыть паки в магазине", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="open_menu")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Открыть паки в магазине", url="https://t.me/footyCards2bot?start=shop")]
        ])
    
    await message.reply(text, reply_markup=keyboard)

# Команда для админов
@router.message(Command("футкартастат"))
async def chat_pack_stats(message: Message):
    """Показывает общую статистику по открытиям во всех чатах"""
    stats = await get_chat_pack_stats()
    
    if stats and stats['total_users']:
        text = f"""
📊 <b>Общая статистика открытий во всех чатах</b>

👥 Всего участников: <b>{stats['total_users']}</b>
🎴 Всего открыто карточек: <b>{stats['total_opened']}</b>
⏰ Последнее открытие: <b>{stats['last_opened'].strftime('%d.%m.%Y %H:%M') if stats['last_opened'] else 'Никогда'}</b>

💡 Участники могут открывать по 1 карточке каждые 3 часа
"""
    else:
        text = "📊 В чатах еще не открывали карточки\n\n💡 Напишите 'футКарта' чтобы получить первую карточку!"
    
    await message.reply(text)