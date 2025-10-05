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
    user_id = message.from_user.id
    text = "📋 <b>Главное меню:</b>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Магазин паков", callback_data="show_shop_packs")],
        [InlineKeyboardButton(text="🃏 Мои карты", callback_data="my_cards")],
        [InlineKeyboardButton(text="⚔️ Игровые режимы", callback_data="play_menu")],
        [InlineKeyboardButton(text="🏪 Маркет", callback_data="market_menu")],
        [InlineKeyboardButton(text="💎 Пополнить баланс", callback_data="donate_menu")]
    ])
    
    if isinstance(message, CallbackQuery):
        try:
            # Пытаемся отредактировать существующее сообщение
            await message.message.edit_text(text, reply_markup=keyboard)
        except Exception as e:
            # Если не получается (например, сообщение с фото), отправляем новое
            await message.message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

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