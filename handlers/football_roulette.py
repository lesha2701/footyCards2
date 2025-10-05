from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from datetime import datetime

from db.user_queries import get_user_by_id, update_user_balance
from db.game_queries import save_game_result, get_football_roulette_stats

router = Router()

class FootballRouletteStates(StatesGroup):
    choosing_bet = State()
    choosing_bet_type = State()
    choosing_number = State()
    choosing_color = State()
    choosing_sector = State()
    spinning = State()
    result = State()

# Ставки для рулетки
ROULETTE_BET_AMOUNTS = [100, 250, 500, 1000, 2500, 5000, 10000]

# Рулетка чисел (0-36 как в европейской рулетке)
ROULETTE_NUMBERS = list(range(37))  # 0-36

# Цвета рулетки (0 - зеленый, остальные чередуются)
ROULETTE_COLORS = {
    0: '🟢',  # Зеленый
    **{num: '🔴' if num % 2 == 1 else '⚫' for num in range(1, 37)}  # Красный/Черный
}

# Сектора рулетки
ROULETTE_SECTORS = {
    '1st_12': {'range': range(1, 13), 'multiplier': 3, 'name': '1-12'},
    '2nd_12': {'range': range(13, 25), 'multiplier': 3, 'name': '13-24'}, 
    '3rd_12': {'range': range(25, 37), 'multiplier': 3, 'name': '25-36'},
    '1-18': {'range': range(1, 19), 'multiplier': 2, 'name': '1-18'},
    '19-36': {'range': range(19, 37), 'multiplier': 2, 'name': '19-36'},
    'even': {'condition': lambda x: x % 2 == 0 and x != 0, 'multiplier': 2, 'name': 'Чётные'},
    'odd': {'condition': lambda x: x % 2 == 1, 'multiplier': 2, 'name': 'Нечётные'},
    'red': {'condition': lambda x: ROULETTE_COLORS[x] == '🔴', 'multiplier': 2, 'name': 'Красные'},
    'black': {'condition': lambda x: ROULETTE_COLORS[x] == '⚫', 'multiplier': 2, 'name': 'Чёрные'}
}

# Футбольные фразы комментатора для рулетки
ROULETTE_PHRASES = {
    'start': [
        "Добро пожаловать на футбольную рулетку! ⚽🎰",
        "Мяч на точке... Куда он полетит? 🎯",
        "Напряжение как перед пенальти! 🔥",
        "Болельщики замерли в ожидании... 👀",
        "Футбольная удача на твоей стороне! 💫"
    ],
    'spin': [
        "Мяч крутится по полю... ⚽",
        "Вращение начинается! 🔄",
        "Куда же приземлится мяч? 🎯",
        "Секундочку, определяется результат... ⏳",
        "Удача на твоей стороне! 🍀"
    ],
    'win': [
        "ГООООЛ! Невероятный выигрыш! 🎉",
        "Вот это точность! Прямо в девятку! ⭐",
        "Болельщики сходят с ума! Какая игра! 🤯",
        "Такой удачи я давно не видел! ✨",
        "Это будет помниться долго! Великолепно! 👏"
    ],
    'lose': [
        "Мимо! Не повезло... 😔",
        "Вратарь поймал мяч! В следующий раз получится! 💪",
        "Соперник оказался сильнее... Но ты держался достойно! 🛡️",
        "Иногда не везёт даже лучшим... Не вешай нос! 🌟",
        "Это всего лишь один удар! Впереди ещё много матчей! ⚽"
    ],
    'jackpot': [
        "ХЕТ-ТРИК! АБСОЛЮТНЫЙ ДЖЕКПОТ! 🎯",
        "БРАВО! Точность снайпера! 💫",
        "Такого я ещё не видел! Феноменально! 🤩",
        "Это войдёт в историю турнира! Легендарно! 📜",
        "Снимите шляпу! Величайший выигрыш! 🎩"
    ]
}

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        pass

async def show_roulette_stats(callback: CallbackQuery):
    """Показать статистику футбольной рулетки"""
    user_id = callback.from_user.id
    stats = await get_football_roulette_stats(user_id)
    
    stats_text = (
        f"🎰 <b>Статистика Футбольной Рулетки</b>\n\n"
        f"<blockquote>🎯 Всего спинов: {stats['total_games']}\n"
        f"✅ Выигрышных ставок: {stats['wins']}\n"
        f"❌ Проигрышных ставок: {stats['losses']}\n"
        f"📈 Процент побед: {stats['win_percentage']}%</blockquote>\n\n"
        f"<blockquote>💰 Общий выигрыш: {stats['total_win']} монет\n"
        f"🎰 Общие ставки: {stats['total_bet']} монет\n"
        f"💵 Прибыль: {stats['profit']} монет\n"
        f"🏆 Самый большой выигрыш: {stats['biggest_win']} монет</blockquote>\n\n"
        f"💪 Продолжайте играть, удача обязательно улыбнётся! ⚽"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к рулетке", callback_data="back_to_roulette")]
    ])
    
    await safe_edit_message(callback, stats_text, keyboard)

@router.callback_query(F.data == "roulette_stats")
async def handle_roulette_stats(callback: CallbackQuery):
    """Обработчик кнопки статистики рулетки"""
    await show_roulette_stats(callback)

@router.callback_query(F.data == "back_to_roulette")
async def back_to_roulette(callback: CallbackQuery, state: FSMContext):
    """Возврат к рулетке из статистики"""
    await start_football_roulette(callback, state)

@router.callback_query(F.data == "open_roulette")
async def start_football_roulette(callback: CallbackQuery, state: FSMContext):
    """Начало игры в футбольную рулетку"""
    user_id = callback.from_user.id
    user = await get_user_by_id(user_id)
    
    if user['balance'] < min(ROULETTE_BET_AMOUNTS):
        await callback.answer(
            f"🎰 Нужно минимум {min(ROULETTE_BET_AMOUNTS)} монет для игры!",
            show_alert=True
        )
        return
    
    # Создаем кнопки ставок
    bet_buttons = []
    for amount in ROULETTE_BET_AMOUNTS:
        if user['balance'] >= amount:
            bet_buttons.append([InlineKeyboardButton(
                text=f"🎰 Ставка: {amount} монет",
                callback_data=f"roulette_bet:{amount}"
            )])
    
    # Добавляем кнопку статистики и назад
    bet_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="roulette_stats"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=bet_buttons)
    commentator_phrase = random.choice(ROULETTE_PHRASES['start'])
    
    await safe_edit_message(
        callback,
        f"🎰 <b>ФУТБОЛЬНАЯ РУЛЕТКА</b>\n\n"
        f"🎙️ <i>\"{commentator_phrase}\"</i>\n\n"
        f"📜 <b>Правила игры:</b>\n"
        f"<blockquote>▫️ Ставьте на числа, цвета или сектора\n"
        f"▫️ Мяч вращается и останавливается на случайном числе\n"
        f"▫️ Выигрыш зависит от типа ставки и множителя\n"
        f"▫️ Прямая ставка на число: x36\n"
        f"▫️ Ставка на цвет/чётность: x2\n"
        f"▫️ Ставка на сектор: x2-x3</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user['balance']} монет\n\n"
        f"<i>Выберите размер ставки:</i>",
        keyboard
    )
    
    await state.set_state(FootballRouletteStates.choosing_bet)

@router.callback_query(F.data.startswith("roulette_bet:"))
async def set_roulette_bet(callback: CallbackQuery, state: FSMContext):
    """Установка ставки и выбор типа ставки"""
    bet_amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    user_info = await get_user_by_id(user_id)
    if user_info['balance'] < bet_amount:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return
    
    await state.update_data(bet_amount=bet_amount)
    
    # Предлагаем выбрать тип ставки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 На число", callback_data="bet_type:number")],
        [InlineKeyboardButton(text="🎨 На цвет", callback_data="bet_type:color")],
        [InlineKeyboardButton(text="📊 На сектор", callback_data="bet_type:sector")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="open_roulette")]
    ])
    
    await safe_edit_message(
        callback,
        f"🎰 <b>Ставка принята: {bet_amount} монет</b>\n\n"
        f"<i>Выберите тип ставки:</i>\n\n"
        f"🔢 <b>На число:</b> x36 (прямая ставка)\n"
        f"🎨 <b>На цвет:</b> x2 (красный/черный)\n"
        f"📊 <b>На сектор:</b> x2-x3 (чётные/нечётные, 1-18 и т.д.)",
        keyboard
    )
    
    await state.set_state(FootballRouletteStates.choosing_bet_type)

@router.callback_query(F.data.startswith("bet_type:"))
async def choose_bet_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа ставки"""
    bet_type = callback.data.split(":")[1]
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    
    if bet_type == "number":
        # Создаем клавиатуру с числами рулетки (группируем по 12 чисел)
        number_buttons = []
        row = []
        for i in range(37):  # 0-36
            color = ROULETTE_COLORS[i]
            row.append(InlineKeyboardButton(
                text=f"{color}{i}",
                callback_data=f"number_bet:{i}"
            ))
            if len(row) == 6:  # 6 чисел в строке
                number_buttons.append(row)
                row = []
        if row:  # Добавляем последнюю неполную строку
            number_buttons.append(row)
        
        number_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"roulette_bet:{bet_amount}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=number_buttons)
        
        await safe_edit_message(
            callback,
            f"🎰 <b>Ставка на число</b> | {bet_amount} монет\n\n"
            f"<i>Выберите число от 0 до 36:</i>\n"
            f"🟢 0 - зелёный (джекпот)\n"
            f"🔴 Нечётные - красные\n"
            f"⚫ Чётные - чёрные\n\n"
            f"<b>Множитель: x36</b>",
            keyboard
        )
        await state.set_state(FootballRouletteStates.choosing_number)
        
    elif bet_type == "color":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Красные (x2)", callback_data="color_bet:red")],
            [InlineKeyboardButton(text="⚫ Чёрные (x2)", callback_data="color_bet:black")],
            [InlineKeyboardButton(text="🟢 Зелёный (x36)", callback_data="color_bet:green")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"roulette_bet:{bet_amount}")]
        ])
        
        await safe_edit_message(
            callback,
            f"🎰 <b>Ставка на цвет</b> | {bet_amount} монет\n\n"
            f"<i>Выберите цвет:</i>\n\n"
            f"🔴 <b>Красные:</b> x2 (все нечётные числа)\n"
            f"⚫ <b>Чёрные:</b> x2 (все чётные числа)\n"
            f"🟢 <b>Зелёный:</b> x36 (только 0)",
            keyboard
        )
        await state.set_state(FootballRouletteStates.choosing_color)
        
    elif bet_type == "sector":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1-12 (x3)", callback_data="sector_bet:1st_12")],
            [InlineKeyboardButton(text="13-24 (x3)", callback_data="sector_bet:2nd_12")],
            [InlineKeyboardButton(text="25-36 (x3)", callback_data="sector_bet:3rd_12")],
            [InlineKeyboardButton(text="1-18 (x2)", callback_data="sector_bet:1-18")],
            [InlineKeyboardButton(text="19-36 (x2)", callback_data="sector_bet:19-36")],
            [InlineKeyboardButton(text="Чётные (x2)", callback_data="sector_bet:even")],
            [InlineKeyboardButton(text="Нечётные (x2)", callback_data="sector_bet:odd")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"roulette_bet:{bet_amount}")]
        ])
        
        await safe_edit_message(
            callback,
            f"🎰 <b>Ставка на сектор</b> | {bet_amount} монет\n\n"
            f"<i>Выберите сектор:</i>\n\n"
            f"📊 <b>Дюжины:</b> x3 (1-12, 13-24, 25-36)\n"
            f"🔢 <b>Половины:</b> x2 (1-18, 19-36)\n"
            f"⚖️ <b>Чётность:</b> x2 (чётные/нечётные)",
            keyboard
        )
        await state.set_state(FootballRouletteStates.choosing_sector)

@router.callback_query(F.data.startswith("number_bet:"))
async def place_number_bet(callback: CallbackQuery, state: FSMContext):
    """Ставка на конкретное число"""
    chosen_number = int(callback.data.split(":")[1])
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    
    await state.update_data(
        bet_type="number",
        chosen_number=chosen_number,
        multiplier=36
    )
    
    color = ROULETTE_COLORS[chosen_number]
    await safe_edit_message(
        callback,
        f"🎰 <b>Ставка на число:</b> {color}{chosen_number}\n"
        f"💰 <b>Ставка:</b> {bet_amount} монет\n"
        f"📈 <b>Множитель:</b> x36\n\n"
        f"<i>Мяч устанавливается на поле...</i>"
    )
    
    await asyncio.sleep(1)
    await spin_roulette(callback, state)

@router.callback_query(F.data.startswith("color_bet:"))
async def place_color_bet(callback: CallbackQuery, state: FSMContext):
    """Ставка на цвет"""
    color = callback.data.split(":")[1]
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    
    if color == "green":
        multiplier = 36
        bet_type = "number"
        chosen_number = 0
    else:
        multiplier = 2
        bet_type = "color"
        chosen_number = None
    
    await state.update_data(
        bet_type=bet_type,
        chosen_color=color,
        chosen_number=chosen_number,
        multiplier=multiplier
    )
    
    color_emoji = "🟢" if color == "green" else "🔴" if color == "red" else "⚫"
    await safe_edit_message(
        callback,
        f"🎰 <b>Ставка на цвет:</b> {color_emoji} {color.capitalize()}\n"
        f"💰 <b>Ставка:</b> {bet_amount} монет\n"
        f"📈 <b>Множитель:</b> x{multiplier}\n\n"
        f"<i>Мяч устанавливается на поле...</i>"
    )
    
    await asyncio.sleep(1)
    await spin_roulette(callback, state)

@router.callback_query(F.data.startswith("sector_bet:"))
async def place_sector_bet(callback: CallbackQuery, state: FSMContext):
    """Ставка на сектор"""
    sector = callback.data.split(":")[1]
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    sector_info = ROULETTE_SECTORS[sector]
    
    await state.update_data(
        bet_type="sector",
        chosen_sector=sector,
        multiplier=sector_info['multiplier']
    )
    
    await safe_edit_message(
        callback,
        f"🎰 <b>Ставка на сектор:</b> {sector_info['name']}\n"
        f"💰 <b>Ставка:</b> {bet_amount} монет\n"
        f"📈 <b>Множитель:</b> x{sector_info['multiplier']}\n\n"
        f"<i>Мяч устанавливается на поле...</i>"
    )
    
    await asyncio.sleep(1)
    await spin_roulette(callback, state)

async def spin_roulette(callback: CallbackQuery, state: FSMContext):
    """Анимация вращения рулетки"""
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    
    # Генерируем выигрышное число
    winning_number = random.choice(ROULETTE_NUMBERS)
    winning_color = ROULETTE_COLORS[winning_number]
    
    # Анимация вращения
    for i in range(12):  # 12 кадров анимации
        # Показываем случайные числа во время вращения
        temp_numbers = [random.choice(ROULETTE_NUMBERS) for _ in range(5)]
        temp_colors = [ROULETTE_COLORS[num] for num in temp_numbers]
        
        spin_text = (
            f"🎰 <b>РУЛЕТКА ВРАЩАЕТСЯ...</b>\n\n"
            f"⚽ Мяч летит над числами:\n"
            f"{' '.join([f'{color}{num}' for color, num in zip(temp_colors, temp_numbers)])}\n\n"
            f"<i>{random.choice(ROULETTE_PHRASES['spin'])}</i>"
        )
        
        await safe_edit_message(callback, spin_text)
        await asyncio.sleep(0.5 + i * 0.1)  # Замедляемся
    
    # Показываем результат
    await show_roulette_result(callback, state, winning_number, winning_color)

async def show_roulette_result(callback: CallbackQuery, state: FSMContext, winning_number: int, winning_color: str):
    """Показ результата рулетки"""
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    user_id = callback.from_user.id
    bet_type = state_data.get('bet_type')
    
    # Проверяем выигрыш
    win_amount = 0
    result = "lose"
    win_description = ""
    
    if bet_type == "number":
        chosen_number = state_data.get('chosen_number')
        if chosen_number == winning_number:
            win_amount = bet_amount * state_data['multiplier']
            result = "win"
            win_description = f"Прямое попадание в {winning_color}{winning_number}!"
        else:
            win_description = f"Выпало {winning_color}{winning_number}, а вы ставили на {ROULETTE_COLORS[chosen_number]}{chosen_number}"
            
    elif bet_type == "color":
        chosen_color = state_data.get('chosen_color')
        if (chosen_color == "red" and winning_color == "🔴") or \
           (chosen_color == "black" and winning_color == "⚫") or \
           (chosen_color == "green" and winning_number == 0):
            win_amount = bet_amount * state_data['multiplier']
            result = "win"
            win_description = f"Цвет совпал! Выпал {winning_color}"
        else:
            win_description = f"Выпал {winning_color}, а вы ставили на {chosen_color}"
            
    elif bet_type == "sector":
        chosen_sector = state_data.get('chosen_sector')
        sector_info = ROULETTE_SECTORS[chosen_sector]
        
        is_win = False
        if 'range' in sector_info:
            is_win = winning_number in sector_info['range']
        elif 'condition' in sector_info:
            is_win = sector_info['condition'](winning_number)
            
        if is_win:
            win_amount = bet_amount * state_data['multiplier']
            result = "win"
            win_description = f"Сектор {sector_info['name']} сыграл!"
        else:
            win_description = f"Выпало {winning_number}, не входит в {sector_info['name']}"
    
    # Начисляем выигрыш
    if win_amount > 0:
        await update_user_balance(user_id, win_amount)
    
    # Сохраняем результат игры
    await save_game_result(
        user_id=user_id,
        game_type="football_roulette",
        result=result,
        bet_amount=bet_amount,
        win_amount=win_amount,
        player_score=0,
        opponent_score=0
    )
    
    user_info = await get_user_by_id(user_id)
    
    # Формируем сообщение о результате
    if win_amount > 0:
        if winning_number == 0:
            result_text = f"🎉 <b>ДЖЕКПОТ! ЗЕЛЁНЫЙ НОЛЬ!</b> +{win_amount} монет!"
            phrase = random.choice(ROULETTE_PHRASES['jackpot'])
        else:
            result_text = f"🎊 <b>ВЫИГРЫШ!</b> +{win_amount} монет!"
            phrase = random.choice(ROULETTE_PHRASES['win'])
    else:
        result_text = "😢 <b>ПРОИГРЫШ</b>"
        phrase = random.choice(ROULETTE_PHRASES['lose'])
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить ещё раз", callback_data=f"roulette_bet:{bet_amount}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="roulette_stats")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])
    
    await safe_edit_message(
        callback,
        f"🎰 <b>РЕЗУЛЬТАТ РУЛЕТКИ</b>\n\n"
        f"⚽ <b>Выпало:</b> {winning_color}{winning_number}\n\n"
        f"📝 <b>Ваша ставка:</b> {bet_amount} монет\n"
        f"📈 <b>Множитель:</b> x{state_data.get('multiplier', 1)}\n\n"
        f"💬 <b>{win_description}</b>\n\n"
        f"🎙️ <i>\"{phrase}\"</i>\n\n"
        f"💰 <b>{result_text}</b>\n"
        f"🏦 Баланс: <b>{user_info['balance']} монет</b>\n\n"
        f"<i>Удача любит смелых! 🍀</i>",
        keyboard
    )
    
    await state.set_state(FootballRouletteStates.result)