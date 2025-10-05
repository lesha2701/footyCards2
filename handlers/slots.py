from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from datetime import datetime

from db.user_queries import get_user_by_id, update_user_balance
from db.game_queries import save_game_result, get_slot_machine_stats

router = Router()

class SlotMachineStates(StatesGroup):
    choosing_bet = State()
    spinning = State()
    result = State()

# Ставки для слота
SLOT_BET_AMOUNTS = [50, 100, 250, 500, 1000, 2500]

# Символы слота (футбольная тематика)
SLOT_SYMBOLS = {
    '⚽': {'name': 'Мяч', 'multiplier': 2},
    '🥅': {'name': 'Ворота', 'multiplier': 3},
    '👟': {'name': 'Бутса', 'multiplier': 4},
    '🏆': {'name': 'Кубок', 'multiplier': 5},
    '🎯': {'name': 'Мишень', 'multiplier': 10},
    '🧤': {'name': 'Перчатка', 'multiplier': 15},
    '⭐': {'name': 'Звезда', 'multiplier': 25},  # Джекпот символ
}

# Комбинации и множители
COMBINATIONS = {
    '3x⭐': {'multiplier': 100, 'name': 'ДЖЕКПОТ!'},
    '3x🎯': {'multiplier': 20, 'name': 'Супер выигрыш!'},
    '3x🧤': {'multiplier': 15, 'name': 'Отличная комбинация!'},
    '3x🏆': {'multiplier': 10, 'name': 'Отличная комбинация!'},
    '3x👟': {'multiplier': 8, 'name': 'Хорошая комбинация!'},
    '3x🥅': {'multiplier': 6, 'name': 'Хорошая комбинация!'},
    '3x⚽': {'multiplier': 4, 'name': 'Неплохая комбинация!'},
    '2x⭐': {'multiplier': 5, 'name': 'Бонус за звезды!'},
    'any_2': {'multiplier': 2, 'name': 'Малый выигрыш!'},
}

# Фразы для анимации
SPIN_PHRASES = [
    "Барабаны крутятся... 🎰",
    "Символы выстраиваются... 🔄",
    "Удача на твоей стороне! 🍀",
    "Футбольная магия в действии! ⚽",
    "Победа уже близко! 🏆",
    "Секундочку, определяется результат... ⏳"
]

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        pass

async def show_slot_stats(callback: CallbackQuery):
    """Показать статистику слот-машины"""
    user_id = callback.from_user.id
    stats = await get_slot_machine_stats(user_id)
    
    stats_text = (
        f"🎰 <b>Статистика Слот-Машины</b>\n\n"
        f"<blockquote>🎯 Всего спинов: {stats['total_games']}\n"
        f"✅ Выигрышных спинов: {stats['wins']}\n"
        f"📈 Процент побед: {stats['win_percentage']}%\n"
        f"💰 Джекпотов: {stats['jackpots']}</blockquote>\n\n"
        f"<blockquote>🏆 Самый большой выигрыш: {stats['biggest_win']} монет\n"
        f"💸 Общий выигрыш: {stats['total_win']} монет\n"
        f"🎫 Общие ставки: {stats['total_bet']} монет\n"
        f"💵 Прибыль: {stats['profit']} монет</blockquote>\n\n"
        f"🎮 <i>Удачи в следующем спине! Может, именно ты сорвёшь джекпот!</i> 💫"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к автомату", callback_data="back_to_slots")]
    ])
    
    await safe_edit_message(callback, stats_text, keyboard)

@router.callback_query(F.data == "slot_stats")
async def handle_slot_stats(callback: CallbackQuery):
    """Обработчик кнопки статистики слотов"""
    await show_slot_stats(callback)

@router.callback_query(F.data == "back_to_slots")
async def back_to_slots(callback: CallbackQuery, state: FSMContext):
    """Возврат к слот-машине из статистики"""
    await start_slot_machine(callback, state)

@router.callback_query(F.data == "open_slots")
async def start_slot_machine(callback: CallbackQuery, state: FSMContext):
    """Начало игры в слот-машину"""
    user_id = callback.from_user.id
    user = await get_user_by_id(user_id)
    
    if user['balance'] < min(SLOT_BET_AMOUNTS):
        await callback.answer(
            f"🎰 Нужно минимум {min(SLOT_BET_AMOUNTS)} монет для игры!",
            show_alert=True
        )
        return
    
    # Создаем кнопки ставок
    bet_buttons = []
    for amount in SLOT_BET_AMOUNTS:
        if user['balance'] >= amount:
            bet_buttons.append([InlineKeyboardButton(
                text=f"🎰 Ставка: {amount} монет",
                callback_data=f"slot_bet:{amount}"
            )])
    
    # Добавляем кнопку статистики и назад
    bet_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="slot_stats"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=bet_buttons)
    
    await safe_edit_message(
        callback,
        f"🎰 <b>ФУТБОЛЬНЫЙ СЛОТ-АВТОМАТ</b>\n\n"
        f"⚽ <b>Символы и множители:</b>\n"
        f"<blockquote>⚽ Мяч - x{SLOT_SYMBOLS['⚽']['multiplier']}\n"
        f"🥅 Ворота - x{SLOT_SYMBOLS['🥅']['multiplier']}\n"
        f"👟 Бутса - x{SLOT_SYMBOLS['👟']['multiplier']}\n"
        f"🏆 Кубок - x{SLOT_SYMBOLS['🏆']['multiplier']}\n"
        f"🎯 Мишень - x{SLOT_SYMBOLS['🎯']['multiplier']}\n"
        f"🧤 Перчатка - x{SLOT_SYMBOLS['🧤']['multiplier']}\n"
        f"⭐ Звезда - x{SLOT_SYMBOLS['⭐']['multiplier']} (Джекпот!)</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user['balance']} монет\n\n"
        f"<i>Выберите размер ставки:</i>",
        keyboard
    )
    
    await state.set_state(SlotMachineStates.choosing_bet)

@router.callback_query(F.data.startswith("slot_bet:"))
async def set_slot_bet(callback: CallbackQuery, state: FSMContext):
    """Установка ставки и начало игры"""
    bet_amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    user_info = await get_user_by_id(user_id)
    if user_info['balance'] < bet_amount:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return
    
    # Снимаем ставку
    await update_user_balance(user_id, -bet_amount)
    
    await state.update_data(bet_amount=bet_amount)
    
    await safe_edit_message(
        callback,
        f"🎰 <b>Ставка принята: {bet_amount} монет</b>\n\n"
        f"<i>Готовься к вращению барабанов...</i>"
    )
    
    await asyncio.sleep(1)
    await spin_slots(callback, state)

async def spin_slots(callback: CallbackQuery, state: FSMContext):
    """Анимация вращения слотов"""
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    
    # Генерируем финальную комбинацию
    symbols = list(SLOT_SYMBOLS.keys())
    final_reels = [
        random.choice(symbols),
        random.choice(symbols),
        random.choice(symbols)
    ]
    
    # Анимация вращения
    for i in range(8):  # 8 кадров анимации
        spinning_reels = [
            random.choice(symbols),
            random.choice(symbols),
            random.choice(symbols)
        ]
        
        # Постепенно замедляем анимацию
        if i > 5:
            spinning_reels[0] = final_reels[0]
        if i > 6:
            spinning_reels[1] = final_reels[1]
        if i > 7:
            spinning_reels[2] = final_reels[2]
        
        # Упрощенное отображение для мобильных
        spin_text = (
            f"🎰 <b>СЛОТ-АВТОМАТ</b> | Ставка: {bet_amount} монет\n\n"
            f"│ {spinning_reels[0]} │ {spinning_reels[1]} │ {spinning_reels[2]} │\n\n"
            f"<i>{random.choice(SPIN_PHRASES)}</i>"
        )
        
        await safe_edit_message(callback, spin_text)
        await asyncio.sleep(0.3 + i * 0.1)  # Замедляемся
    
    # Показываем финальный результат
    await show_result(callback, state, final_reels)

async def show_result(callback: CallbackQuery, state: FSMContext, reels: list):
    """Показ результата и подсчет выигрыша"""
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    user_id = callback.from_user.id
    
    # Анализируем комбинацию
    win_amount = 0
    result_type = "lose"
    combo_name = ""
    
    # Проверяем комбинации
    if reels[0] == reels[1] == reels[2]:
        # Все три одинаковые
        symbol = reels[0]
        multiplier = SLOT_SYMBOLS[symbol]['multiplier']
        win_amount = bet_amount * multiplier
        combo_name = f"3x{symbol}"
        result_type = "jackpot" if symbol == "⭐" else "win"
        
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # Две одинаковые
        if "⭐" in reels and reels.count("⭐") == 2:
            # Две звезды
            win_amount = bet_amount * COMBINATIONS['2x⭐']['multiplier']
            combo_name = "2x⭐"
        else:
            # Любые две одинаковые
            win_amount = bet_amount * COMBINATIONS['any_2']['multiplier']
            combo_name = "Две одинаковые"
        result_type = "win"
    
    # Начисляем выигрыш
    if win_amount > 0:
        await update_user_balance(user_id, win_amount)
    
    # Сохраняем результат игры (без additional_data)
    await save_game_result(
        user_id=user_id,
        game_type="slot_machine",
        result=result_type,
        bet_amount=bet_amount,
        win_amount=win_amount,
        player_score=0,
        opponent_score=0
    )
    
    user_info = await get_user_by_id(user_id)
    
    # Формируем сообщение о результате
    result_text = ""
    if win_amount > 0:
        if result_type == "jackpot":
            result_text = f"🎉 <b>ДЖЕКПОТ!!!</b> 🎉\n+{win_amount} монет!"
        else:
            result_text = f"🎊 <b>ВЫИГРЫШ!</b> +{win_amount} монет!"
    else:
        result_text = "😢 <b>ПРОИГРЫШ</b>\nПопробуй ещё раз!"
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить ещё раз", callback_data=f"slot_bet:{bet_amount}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="slot_stats")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])
    
    await safe_edit_message(
        callback,
        f"🎰 <b>РЕЗУЛЬТАТ</b> | Ставка: {bet_amount} монет\n\n"
        f"│ {reels[0]} │ {reels[1]} │ {reels[2]} │\n\n"
        f"{result_text}\n\n"
        f"💎 <b>Комбинация:</b> {combo_name if combo_name else 'Нет выигрыша'}\n"
        f"🏦 Баланс: <b>{user_info['balance']} монет</b>\n\n"
        f"<i>Удача любит смелых! 🍀</i>",
        keyboard
    )
    
    await state.set_state(SlotMachineStates.result)

@router.callback_query(F.data.startswith("slot_bet:"), SlotMachineStates.result)
async def spin_again(callback: CallbackQuery, state: FSMContext):
    """Повторный спин с той же ставкой"""
    bet_amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    user_info = await get_user_by_id(user_id)
    if user_info['balance'] < bet_amount:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return
    
    # Снимаем ставку
    await update_user_balance(user_id, -bet_amount)
    
    await state.update_data(bet_amount=bet_amount)
    await spin_slots(callback, state)