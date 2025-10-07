from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.markdown import html_decoration as hd

from db.user_queries import *

router = Router()

# Конфигурация каналов для подписки
CHANNELS_CONFIG = {
    -1002655732796: {  # ID канала 1
        'name': '📢 Футбольные новости',
        'url': 'https://t.me/RonaldoOrMessiQuest'
    },
    -1002459798852: {  # ID канала 2
        'name': '🎮 Основной канал', 
        'url': 'https://t.me/FootyCardsChannel'
    }
}

async def check_channels_subscription(user_id: int, bot: Bot) -> tuple[bool, list]:
    """
    Проверяет подписку пользователя на все каналы
    Возвращает (все_ли_подписки_активны, список_неподписанных_каналов)
    """
    not_subscribed = []
    
    for channel_id, channel_info in CHANNELS_CONFIG.items():
        try:
            # Проверяем статус подписки
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            # Если пользователь не подписан или покинул канал
            if member.status in ['left', 'kicked']:
                not_subscribed.append((channel_id, channel_info))
        except Exception as e:
            print(f"Ошибка при проверке канала {channel_id}: {e}")
            # В случае ошибки считаем, что пользователь не подписан
            not_subscribed.append((channel_id, channel_info))
    
    return len(not_subscribed) == 0, not_subscribed

async def create_subscription_keyboard(not_subscribed_channels: list) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками для подписки на каналы"""
    buttons = []
    
    for channel_id, channel_info in not_subscribed_channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 Подписаться на {channel_info['name']}",
                url=channel_info['url']
            )
        ])
    
    # Кнопка проверки подписки
    buttons.append([
        InlineKeyboardButton(
            text="✅ Я подписался!",
            callback_data="check_subscription"
        )
    ])
    
    # Кнопка возврата в меню
    buttons.append([
        InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data="back_to_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data == "open_menu")
async def cmd_castle(message: Message, state: FSMContext):
    await show_menu(message, state)

async def show_menu(message: Message | CallbackQuery, state: FSMContext):
    """Показывает главное меню со статистикой игрока"""
    user_id = message.from_user.id
    
    try:
        # Получаем статистику пользователя
        user_stats = await get_user_stats(user_id)
        
        # Создаем красивое оформление статистики
        stats_text = await create_compact_stats_display(user_stats)
        
        # Основной текст меню
        text = (
            f"🎮 <b>Главное меню</b>\n\n"
            f"{stats_text}\n"
            f"📋 <b>Выберите действие:</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="⚔️ Игровые режимы", callback_data="play_menu")],
            [InlineKeyboardButton(text="🏪 Маркет", callback_data="market_menu")],
            [InlineKeyboardButton(text="🃏 Мои карты", callback_data="my_cards")],
            [InlineKeyboardButton(text="🏆 Рейтинг игроков", callback_data="show_leaderboard")],
            [InlineKeyboardButton(text="📚 Коллекции", callback_data="show_collections")],  # Новая кнопка
            [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="donate_menu")]
        ])
        
        if isinstance(message, CallbackQuery):
            try:
                # Пытаемся отредактировать существующее сообщение
                await message.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                print(f"[{datetime.now()}] Меню со статистикой отредактировано для пользователя {user_id}")
            except Exception as e:
                print(f"[{datetime.now()}] Не удалось отредактировать меню: {e}, отправляем новое")
                # Если не получается отредактировать, отправляем новое сообщение
                await message.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            print(f"[{datetime.now()}] Новое меню со статистикой отправлено для пользователя {user_id}")
            
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в show_menu: {e}")
        # Резервный вариант без статистики
        text = "📋 <b>Главное меню:</b>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="⚔️ Игровые режимы", callback_data="play_menu")],
            [InlineKeyboardButton(text="🏪 Маркет", callback_data="market_menu")],
            [InlineKeyboardButton(text="🃏 Мои карты", callback_data="my_cards")],
            [InlineKeyboardButton(text="🏆 Рейтинг игроков", callback_data="show_leaderboard")],
            [InlineKeyboardButton(text="📚 Коллекции", callback_data="show_collections")],  # Новая кнопка
            [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="donate_menu")]
        ])
        
        if isinstance(message, CallbackQuery):
            try:
                await message.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await message.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "play_menu")
async def play_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Проверяет подписку перед входом в игровые режимы"""
    
    # Проверяем подписку на каналы
    is_subscribed, not_subscribed = await check_channels_subscription(callback.from_user.id, bot)
    
    if not is_subscribed:
        # Показываем сообщение о необходимости подписки
        channels_list = "\n".join([
            f"• {channel_info['name']}" 
            for _, channel_info in not_subscribed
        ])
        
        subscription_message = (
            "🎮 <b>Доступ к игровым режимам</b>\n\n"
            "Чтобы играть в наши игры, необходимо подписаться на следующие каналы:\n\n"
            f"{channels_list}\n\n"
            "После подписки нажмите кнопку <b>✅ Я подписался!</b>"
        )
        
        keyboard = await create_subscription_keyboard(not_subscribed)
        
        await callback.message.edit_text(
            text=subscription_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return
    
    # Если подписка есть, показываем игровые режимы
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Футбольные тренировки", callback_data="open_training")],
        [InlineKeyboardButton(text="🎲 Футбольные кости", callback_data="open_footballDice")],
        [InlineKeyboardButton(text="🃏 Блэк Джек", callback_data="open_football21")],
        [InlineKeyboardButton(text="🎰 Слот-машина", callback_data="open_slots")],
        [InlineKeyboardButton(text="🎯 Футбольная рулетка", callback_data="open_roulette")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text("⚔️ Игровые режимы:", reply_markup=keyboard)

@router.callback_query(F.data == "check_subscription")
async def check_subscription_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Проверяет подписку после нажатия кнопки 'Я подписался'"""
    
    is_subscribed, not_subscribed = await check_channels_subscription(callback.from_user.id, bot)
    
    if is_subscribed:
        # Если подписан на все каналы, показываем игровые режимы
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💪 Футбольные тренировки", callback_data="open_training")],
            [InlineKeyboardButton(text="🎲 Футбольные кости", callback_data="open_footballDice")],
            [InlineKeyboardButton(text="🃏 Блэк Джек", callback_data="open_football21")],
            [InlineKeyboardButton(text="🎰 Слот-машина", callback_data="open_slots")],
            [InlineKeyboardButton(text="🎯 Футбольная рулетка", callback_data="open_roulette")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(
            "✅ <b>Отлично! Вы подписаны на все каналы!</b>\n\n"
            "⚔️ Игровые режимы:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        # Если еще не подписан на все каналы
        channels_list = "\n".join([
            f"• {channel_info['name']}" 
            for _, channel_info in not_subscribed
        ])
        
        subscription_message = (
            "❌ <b>Вы еще не подписались на все каналы!</b>\n\n"
            "Осталось подписаться на:\n\n"
            f"{channels_list}\n\n"
            "После подписки нажмите кнопку <b>✅ Я подписался!</b> еще раз"
        )
        
        keyboard = await create_subscription_keyboard(not_subscribed)
        
        await callback.message.edit_text(
            text=subscription_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await callback.answer("Вы еще не подписались на все каналы!", show_alert=True)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await show_menu(callback, state)

async def create_compact_stats_display(stats) -> str:
    """Создает компактное отображение статистики"""
    if not stats:
        return "📊 <i>Статистика загружается...</i>"
    
    # Рассчитываем метрики
    win_rate = 0
    if stats['total_games'] > 0:
        win_rate = (stats['wins'] / stats['total_games']) * 100
    
    training_success_rate = 0
    if stats['total_trainings'] > 0:
        training_success_rate = (stats['successful_trainings'] / stats['total_trainings']) * 100
    
    return (
        f"💰 <b>{stats['balance']:,}</b> | "
        f"⭐ <b>{stats['score']:,}</b> | "
        f"🃏 <b>{stats['total_cards']:,}</b>\n"
        f"🎮 WR: <b>{win_rate:.1f}%</b> | "
        f"💪 Eff: <b>{training_success_rate:.1f}%</b>\n"
    )

@router.callback_query(F.data == "show_leaderboard")
async def show_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Показывает рейтинг игроков по очкам"""
    user_id = callback.from_user.id
    
    try:
        # Получаем данные рейтинга
        leaderboard_data = await get_leaderboard(user_id)
        
        if not leaderboard_data:
            await callback.answer("❌ Ошибка загрузки рейтинга", show_alert=True)
            return
        
        # Создаем красивое отображение рейтинга
        leaderboard_text = await create_leaderboard_display(leaderboard_data, user_id)
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        
        # Отправляем или редактируем сообщение
        try:
            await callback.message.edit_text(
                text=leaderboard_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(
                text=leaderboard_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в show_leaderboard: {e}")
        await callback.answer("❌ Ошибка загрузки рейтинга", show_alert=True)

async def create_leaderboard_display(leaderboard_data, current_user_id: int) -> str:
    """Создает красивое отображение рейтинга"""
    top_players = leaderboard_data['top_players']
    user_position = leaderboard_data['user_position']
    total_players = leaderboard_data['total_players']
    current_user = leaderboard_data['current_user']
    
    # Эмодзи для позиций в топе
    position_emojis = {
        1: "🥇",
        2: "🥈", 
        3: "🥉"
    }
    
    # Заголовок
    text = "🏆 <b>Рейтинг игроков по очкам</b>\n\n"
    
    # Топ игроков
    if top_players:
        text += "<b>Топ-10 игроков:</b>\n"
        text += "<blockquote>"
        
        for i, player in enumerate(top_players, 1):
            emoji = position_emojis.get(i, f"{i}.")
            username = player['username'] or f"Игрок {player['user_id']}"
            
            # Обрезаем длинные имена пользователей
            if len(username) > 20:
                username = username[:20] + "..."
            
            # Выделяем текущего пользователя
            if player['user_id'] == current_user_id:
                text += f"{emoji} <b>👉 {username}</b> - {player['score']:,} очков ⭐\n"
            else:
                text += f"{emoji} {username} - {player['score']:,} очков\n"
        text += "</blockquote>"
    else:
        text += "😴 <i>Пока никто не заработал очков</i>\n"
    
    text += "\n"
    
    # Позиция текущего пользователя
    if user_position:
        if user_position <= 10:
            text += f"✅ <b>Вы в топ-10!</b> Позиция: #{user_position}\n"
        else:
            text += f"📊 <b>Ваша позиция:</b> #{user_position} из {total_players}\n"
            
        if current_user:
            text += f"⭐ <b>Ваши очки:</b> {current_user['score']:,}\n"
    else:
        text += "📊 <i>У вас пока нет очков в рейтинге</i>\n"
    
    # Общая статистика
    text += f"\n👥 <b>Всего игроков в рейтинге:</b> {total_players}"
    
    return text

@router.callback_query(F.data == "show_collections")
async def show_collections(callback: CallbackQuery, state: FSMContext):
    """Показывает информацию о коллекциях"""
    user_id = callback.from_user.id
    
    try:
        # Получаем данные о коллекциях
        collections_data = await get_collections_info()
        
        if not collections_data:
            await callback.answer("❌ Ошибка загрузки информации о коллекциях", show_alert=True)
            return
        
        # Создаем красивое отображение коллекций
        collections_text = await create_collections_display(collections_data)
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        
        # Отправляем или редактируем сообщение
        try:
            await callback.message.edit_text(
                text=collections_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(
                text=collections_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        await callback.answer()
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в show_collections: {e}")
        await callback.answer("❌ Ошибка загрузки информации о коллекциях", show_alert=True)

async def create_collections_display(collections_data) -> str:
    """Создает красивое отображение информации о коллекциях"""
    
    # Разделяем коллекции на активные и архивные
    active_collections = [c for c in collections_data if c['is_active']]
    archived_collections = [c for c in collections_data if not c['is_active']]
    
    text = "📚 <b>Информация о коллекциях</b>\n\n"
    
    # Активные коллекции
    if active_collections:
        text += "🟢 <b>АКТИВНЫЕ КОЛЛЕКЦИИ</b>\n"
        text += "<blockquote>"
        
        for collection in active_collections:
            # Прогресс коллекции
            progress_percent = (collection['cards_opened'] / collection['total_cards']) * 100 if collection['total_cards'] > 0 else 0
            progress_bar = create_progress_bar(collection['cards_opened'], collection['total_cards'])
        
            
            text += (
                f"<b>{collection['name']}</b>\n"
                f"📊 {progress_bar} {progress_percent:.1f}%\n"
                f"🎴 {collection['cards_opened']}/{collection['total_cards']} карт\n"
            )
            
            if collection['description']:
                text += f"<i>{collection['description']}</i>\n"
            
            text += "\n"
        
        text += "</blockquote>"
    else:
        text += "😴 <i>Нет активных коллекций</i>\n\n"
    
    # Архивные коллекции
    if archived_collections:
        text += "🔴 <b>АРХИВНЫЕ КОЛЛЕКЦИИ</b>\n"
        text += "<blockquote>"
        
        for collection in archived_collections[:5]:  # Показываем только последние 5
            progress_percent = (collection['cards_opened'] / collection['total_cards']) * 100 if collection['total_cards'] > 0 else 0

            
            text += (
                f"<b>{collection['name']}</b>\n"
                f"🎴 {collection['cards_opened']}/{collection['total_cards']} карт\n"
                f"✅ Завершена на {progress_percent:.1f}%\n\n"
            )
        
        # Если архивных коллекций больше 5, показываем только количество
        if len(archived_collections) > 5:
            text += f"<i>... и еще {len(archived_collections) - 5} коллекций</i>\n"
        
        text += "</blockquote>"
    
    # Общая статистика
    total_collections = len(collections_data)
    total_cards = sum(c['total_cards'] for c in collections_data)
    total_opened = sum(c['cards_opened'] for c in collections_data)
    overall_progress = (total_opened / total_cards) * 100 if total_cards > 0 else 0
    
    text += f"\n\n📈 <b>Общая статистика:</b>\n"
    text += f"<blockquote>• Всего коллекций: {total_collections}\n"
    text += f"• Всего карт в системе: {total_cards}\n"
    text += f"• Открыто карт: {total_opened}\n"
    text += f"• Общий прогресс: {overall_progress:.1f}%</blockquote>"
    
    return text

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создает текстовый прогресс-бар"""
    if total == 0:
        return "░" * length
    
    filled = round((current / total) * length)
    empty = length - filled
    return "█" * filled + "░" * empty