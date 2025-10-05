from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.markdown import html_decoration as hd

from db.user_queries import *

router = Router()

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
async def play_menu(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Футбольные тренировки", callback_data="open_training")],
        [InlineKeyboardButton(text="🎲 Футбольные кости", callback_data="open_footballDice")],
        [InlineKeyboardButton(text="🃏 Блэк Джек", callback_data="open_football21")],
        [InlineKeyboardButton(text="🎰 Слот-машина", callback_data="open_slots")],
        [InlineKeyboardButton(text="🎯 Футбольная рулетка", callback_data="open_roulette")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text("⚔️ Игровые режимы:", reply_markup=keyboard)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню замка"""
    await show_menu(callback, state)