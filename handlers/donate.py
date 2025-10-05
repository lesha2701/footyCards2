from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.markdown import html_decoration as hd
from typing import List

from db.user_queries import *

router = Router()

# Конфигурация доната
EXCHANGE_RATE = 10  # 1 рубль = 10 монет
ADMIN_USERNAME = "hwwerg"  # Замените на ваш username
PAYMENT_CARD = "4276 7700 1393 4549"  # Ваша карта для платежей
TON_WALLET = "UQCXhiGFGOuCYZwZu3nCT2uJGnAIjZY72N1Q7gtSzWJrfe02"  # Ваш TON кошелек

@router.callback_query(F.data == "donate_menu")
async def show_donate_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню доната"""
    text = """<b>💎 Пополнение баланса</b>

🎯 <i>Выберите способ пополнения:</i>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data="donate_card")],
        [InlineKeyboardButton(text="🎁 Telegram Подарок", callback_data="donate_gift")],
        [InlineKeyboardButton(text="🔐 Криптовалюта (TON)", callback_data="donate_crypto")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="donate_terms")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "donate_card")
async def show_donate_card(callback: CallbackQuery, state: FSMContext):
    """Показывает информацию о пополнении картой"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатил", 
            url=f"https://t.me/{ADMIN_USERNAME}?text=ID:{callback.from_user.id};Сумма:*укажите*;Валюта:монеты"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="donate_menu")]
    ])
    
    text = f"""<b>💳 Пополнение банковской картой</b>

💰 <b>Курс обмена:</b>
<blockquote>1 рубль = {EXCHANGE_RATE} монет</blockquote>

🏦 <b>Реквизиты для перевода:</b>
<blockquote><code>{PAYMENT_CARD}</code> (Сбербанк)</blockquote>

📥 <b>Инструкция по пополнению:</b>
<blockquote>1. Совершите перевод на указанные реквизиты
2. Нажмите кнопку <b>"✅ Я оплатил"</b>
3. Отправьте скриншот перевода
4. Укажите в сообщении:
   • Ваш ID: <code>{callback.from_user.id}</code>
   • Сумму перевода
   • Желаемую валюту (монеты)</blockquote>

⏳ <b>Баланс будет пополнен в течение 15 минут</b>
🌙 <i>Ночью время пополнения может быть увеличено</i>"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "donate_gift")
async def show_donate_gift(callback: CallbackQuery, state: FSMContext):
    """Показывает информацию о пополнении через подарки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎁 Отправить подарок", 
            url=f"https://t.me/{ADMIN_USERNAME}?start=gift"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="donate_menu")]
    ])
    
    text = f"""<b>🎁 Пополнение через Telegram Подарки</b>

⭐️ <b>Курс обмена:</b>
<blockquote>Обычный подарок (1 звезда) → 20 монет
Редкий подарок (1 звезды) → 30 монет</blockquote>

🎯 <b>Инструкция по пополнению:</b>
<blockquote>1. Нажмите кнопку <b>"🎁 Отправить подарок"</b>
2. Выберите подарок и отправьте на аккаунт @{ADMIN_USERNAME}
3. Напишите мне в личные сообщения:
   • Ваш ID: <code>{callback.from_user.id}</code>
   • Тип отправленного подарка</blockquote>

⏳ <b>Баланс будет пополнен в течение 5 минут</b>

💫 <b>Подарки доступны в:</b>
• iOS: Telegram Premium → Подарки
• Android: Меню → Подарки"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "donate_crypto")
async def show_donate_crypto(callback: CallbackQuery, state: FSMContext):
    """Показывает информацию о пополнении криптовалютой"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я оплатил", 
            url=f"https://t.me/{ADMIN_USERNAME}?text=ID:{callback.from_user.id};Сумма:*укажите*;Валюта:монеты;Сеть:TON"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="donate_menu")]
    ])
    
    text = f"""<b>🔐 Пополнение криптовалютой (TON)</b>

💰 <b>Курс обмена:</b>
<blockquote>1 TON = {EXCHANGE_RATE * 300} монет
0.1 TON = {EXCHANGE_RATE * 30} монет</blockquote>

🏦 <b>TON кошелек для перевода:</b>
<blockquote><code>{TON_WALLET}</code></blockquote>

📥 <b>Инструкция по пополнению:</b>
<blockquote>1. Совершите перевод на указанный кошелек
2. Нажмите кнопку <b>"✅ Я оплатил"</b>
3. Отправьте хэш транзакции
4. Укажите в сообщении:
   • Ваш ID: <code>{callback.from_user.id}</code>
   • Сумму перевода в TON
   • Желаемую валюту (монеты)</blockquote>

⏳ <b>Баланс будет пополнен в течение 30 минут</b>"""
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "donate_terms")
async def show_donate_terms(callback: CallbackQuery, state: FSMContext):
    """Показывает пользовательское соглашение"""
    text = """<b>📜 Пользовательское соглашение</b>

<blockquote>
1. <b>Общие положения</b>
1.1. Сервис позволяет добровольно пополнять игровой баланс
1.2. Все операции считаются пожертвованиями

2. <b>Условия перевода</b>
2.1. Минимальная сумма перевода - 10 рублей / 0.1 TON
2.2. Переводы принимаются только от владельцев средств

3. <b>Начисление валюты</b>
3.1. Валюта начисляется в течение 24 часов
3.2. Администрация оставляет право отказать в начислении

4. <b>Ответственность</b>
4.1. Сервис не несёт ответственности за ошибочные переводы
4.2. Все спорные ситуации решаются индивидуально

5. <b>Конфиденциальность</b>
5.1. Данные о переводах хранятся 6 месяцев
5.2. Скриншоты используются для подтверждения платежа
</blockquote>

⚠️ <i>Совершая перевод, вы соглашаетесь с условиями</i>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="donate_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)