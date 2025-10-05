from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from datetime import datetime

from db.user_queries import get_user_by_id, update_user_balance
from db.game_queries import save_game_result, get_football_dice_stats

router = Router()

class FootballDiceStates(StatesGroup):
    choosing_bet = State()
    round_1 = State()
    round_2 = State()
    result = State()

# Футбольные ставки
FOOTBALL_BET_AMOUNTS = [100, 250, 500, 1000, 2500, 5000, 10000]

# Футбольные фразы комментатора
COMMENTATOR_PHRASES = {
    'start': [
        "Добро пожаловать на стадион! Готовы к футбольным костям? ⚽🎲",
        "Мяч в центре поля! Кто забьёт первый с пенальти? 🎯",
        "Напряжение нарастает... Пенальти начинается! 🔥",
        "Болельщики замерли в ожидании первого удара! 👀",
        "Сегодня на поле - лучшие исполнители пенальти! 💫"
    ],
    'goblin': [
        "Судья готов к броску! ⚽",
        "Вратарь нервно переминается на линии! 🧤",
        "Мяч ждёт своего исполнителя! 🔵",
        "Напряжение витает в воздухе! 🌬️",
        "Кто проявит хладнокровие? ❄️"
    ],
    'round_inter': [
        "Ну что, готов к следующему удару? ⚽",
        "Ха! Давай посмотрим, что дальше! 👀",
        "Не радуйся раньше времени! 😏",
        "Следующий удар решит всё! 🎯",
        "Ты думаешь, это удача? Ха! 🍀"
    ],
    'win': [
        "ГООООЛ! Невероятная победа! 🎉",
        "Вот это хладнокровие! Игрок демонстрирует класс! ⭐",
        "Болельщики сходят с ума! Какая игра! 🤯",
        "Такой точности я давно не видел! ✨",
        "Это будет помниться долго! Великолепно! 👏"
    ],
    'lose': [
        "Мимо! Упустили победу... Жаль 😔",
        "Не повезло сегодня... В следующий раз точно получится! 💪",
        "Вратарь оказался сильнее... Но вы держались достойно! 🛡️",
        "Иногда промахиваются даже лучшие... Не вешайте нос! 🌟",
        "Это всего лишь одна серия! Впереди ещё много матчей! ⚽"
    ],
    'draw': [
        "Ничья! Напряжённая борьба до последнего удара! ⏱️",
        "Равная игра! Оба заслуживают уважения! 🤝",
        "Интрига сохраняется до следующей встречи! 🔄",
        "Никто не хотел уступать! Вот это характер! 💪",
        "Справедливый результат! Оба молодцы! 👏"
    ]
}

# Футбольные эмодзи для "костей" (голы)
FOOTBALL_DICE = ["①", "②", "③", "④", "⑤", "⑥"]  # Цифры в кружках как голы

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        # Игнорируем ошибку "message is not modified"
        pass

async def show_stats(callback: CallbackQuery):
    """Показать статистику футбольных костей"""
    user_id = callback.from_user.id
    stats = await get_football_dice_stats(user_id)
    
    stats_text = (
        f"📊 <b>Статистика Футбольных Пенальти</b>\n\n"
        f"<blockquote>🎯 Всего игр: {stats['total_games']}\n"
        f"✅ Побед: {stats['wins']}\n"
        f"❌ Поражений: {stats['losses']}\n"
        f"🤝 Ничьих: {stats['draws']}\n"
        f"📈 Процент побед: {stats['win_percentage']}%\n\n"
        f"💰 Общий выигрыш: {stats['total_win']} монет\n"
        f"🎰 Общие ставки: {stats['total_bet']} монет\n"
        f"💵 Прибыль: {stats['profit']} монет</blockquote>\n\n"
        f"💪 Продолжайте играть, удача обязательно улыбнётся! ⚽️"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к игре", callback_data="back_to_football_dice")]
    ])
    
    await safe_edit_message(callback, stats_text, keyboard)

@router.callback_query(F.data == "footballDice_stats")
async def handle_stats(callback: CallbackQuery):
    """Обработчик кнопки статистики"""
    await show_stats(callback)

@router.callback_query(F.data == "back_to_football_dice")
async def back_to_game(callback: CallbackQuery, state: FSMContext):
    """Возврат к игре из статистики"""
    await start_football_dice(callback, state)

@router.callback_query(F.data == "open_footballDice")
async def start_football_dice(callback: CallbackQuery, state: FSMContext):
    """Начало футбольной игры в кости"""
    user_id = callback.from_user.id
    user = await get_user_by_id(user_id)
    
    if user['balance'] < min(FOOTBALL_BET_AMOUNTS):
        await callback.answer(
            f"⚽ Нужно минимум {min(FOOTBALL_BET_AMOUNTS)} монет для выхода на поле!",
            show_alert=True
        )
        return
    
    # Создаем кнопки ставок
    bet_buttons = []
    for amount in FOOTBALL_BET_AMOUNTS:
        if user['balance'] >= amount:
            bet_buttons.append([InlineKeyboardButton(
                text=f"⚽ Ставка: {amount} монет",
                callback_data=f"footballDice_bet:{amount}"
            )])
    
    # Добавляем кнопку статистики и назад
    bet_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="footballDice_stats"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=bet_buttons)
    commentator_phrase = random.choice(COMMENTATOR_PHRASES['start'])
    
    await safe_edit_message(
        callback,
        f"⚽ <b>ФУТБОЛЬНЫЕ ПЕНАЛЬТИ</b>\n\n"
        f"🎙️ <i>\"{commentator_phrase}\"</i>\n\n"
        f"📜 <b>Правила игры:</b>\n"
        f"<blockquote>▫️ Бросаем «кости» в 2 раунда\n"
        f"▫️ Суммируем результаты (голы)\n"
        f"▫️ Кто забил больше - забирает ставку\n"
        f"▫️ При ничье - возврат ставки</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user['balance']} монет\n\n"
        f"<i>Выберите размер ставки:</i>",
        keyboard
    )
    
    await state.set_state(FootballDiceStates.choosing_bet)

@router.callback_query(F.data.startswith("footballDice_bet:"))
async def set_bet(callback: CallbackQuery, state: FSMContext):
    """Установка ставки и начало игры"""
    bet_amount = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    user_info = await get_user_by_id(user_id)
    if user_info['balance'] < bet_amount:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return
    
    # Снимаем ставку
    await update_user_balance(user_id, -bet_amount)
    
    await state.update_data(bet_amount=bet_amount, player_score=0, opponent_score=0)
    
    await safe_edit_message(
        callback,
        f"⚽ <b>Ставка принята: {bet_amount} монет</b>\n\n"
        f"🎙️ <i>\"Отлично! Посмотрим, на что ты способен!\"</i>\n\n"
        f"<i>Мяч устанавливается на точку пенальти...</i>"
    )
    
    await asyncio.sleep(2)
    await start_round(callback, state, round_number=1)
    await state.set_state(FootballDiceStates.round_1)

async def start_round(callback: CallbackQuery, state: FSMContext, round_number: int):
    """Начало раунда"""
    state_data = await state.get_data()
    bet_amount = state_data['bet_amount']
    user_id = callback.from_user.id
    
    # Генерируем результаты (голы)
    player_goals = random.randint(1, 6)
    opponent_goals = random.randint(1, 6)
    
    await state.update_data(
        player_score=state_data['player_score'] + player_goals,
        opponent_score=state_data['opponent_score'] + opponent_goals,
        last_player_goals=player_goals,
        last_opponent_goals=opponent_goals
    )
    
    new_state_data = await state.get_data()
    
    # Анимация броска
    for i in range(3):
        temp_goals = random.randint(1, 6)
        # Добавляем уникальный текст для каждого кадра анимации
        animation_text = f"⚽ <b>Раунд {round_number}</b> | Ставка: {bet_amount} монет\n\n"
        animation_text += f"Твой удар: {FOOTBALL_DICE[temp_goals-1]}\n"
        animation_text += f"Удар соперника: {FOOTBALL_DICE[temp_goals-1]}\n\n"
        
        if i == 0:
            animation_text += "<i>Мяч устанавливается...</i>"
        elif i == 1:
            animation_text += "<i>Разбег... Удар!</i>"
        else:
            animation_text += "<i>Мяч летит в створ ворот...</i>"
        
        await safe_edit_message(callback, animation_text)
        await asyncio.sleep(1)
    
    round_phrase = random.choice(COMMENTATOR_PHRASES['round_inter'])
    
    await safe_edit_message(
        callback,
        f"⚽ <b>РАУНД {round_number} ЗАВЕРШЁН</b>\n\n"
        f"Твои голы: {FOOTBALL_DICE[player_goals-1]} = <b>{player_goals}</b>\n"
        f"Голы соперника: {FOOTBALL_DICE[opponent_goals-1]} = <b>{opponent_goals}</b>\n\n"
        f"🎙️ <i>\"{round_phrase}\"</i>\n\n"
        f"📊 <b>Текущий счёт:</b>\n"
        f"Ты: {new_state_data['player_score']} голов\n"
        f"Соперник: {new_state_data['opponent_score']} голов"
    )
    
    if round_number == 1:
        # Переходим ко второму раунду
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚽ Бить пенальти", callback_data="next_round")]
        ])
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.set_state(FootballDiceStates.round_2)
    else:
        # Завершаем игру
        await asyncio.sleep(3)
        await finish_game(callback, state)

@router.callback_query(F.data == "next_round")
async def start_second_round(callback: CallbackQuery, state: FSMContext):
    """Начало второго раунда"""
    await safe_edit_message(
        callback,
        f"⚽ <b>ВТОРОЙ РАУНД</b>\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['goblin'])}\"</i>\n\n"
        f"<i>Мяч снова устанавливается на точку...</i>"
    )
    await asyncio.sleep(2)
    await start_round(callback, state, round_number=2)

async def finish_game(callback: CallbackQuery, state: FSMContext):
    """Завершение игры и подсчет результатов"""
    state_data = await state.get_data()
    player_total = state_data['player_score']
    opponent_total = state_data['opponent_score']
    bet_amount = state_data['bet_amount']
    user_id = callback.from_user.id
    
    # Определяем результат
    if player_total > opponent_total:
        win_amount = bet_amount * 2
        result = "win"
        result_text = f"✨ <b>ТЫ ПОБЕДИЛ!</b> +{win_amount} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['win'])
    elif player_total < opponent_total:
        result = "lose"
        win_amount = 0
        result_text = f"💀 <b>ТЫ ПРОИГРАЛ!</b> Соперник забирает {bet_amount} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['lose'])
    else:
        result = "draw"
        win_amount = bet_amount
        result_text = f"🔄 <b>НИЧЬЯ!</b> Возврат {bet_amount} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['draw'])
    
    # Начисляем выигрыш
    if win_amount > 0:
        await update_user_balance(user_id, win_amount)
    
    # Сохраняем результат игры
    await save_game_result(
        user_id=user_id,
        game_type="football_dice",
        result=result,
        bet_amount=bet_amount,
        win_amount=win_amount,
        player_score=player_total,
        opponent_score=opponent_total
    )
    
    user_info = await get_user_by_id(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_footballDice")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="footballDice_stats")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])
    
    await safe_edit_message(
        callback,
        f"⚽ <b>ИГРА ЗАВЕРШЕНА!</b>\n\n"
        f"🏁 <b>ФИНАЛЬНЫЙ СЧЁТ:</b>\n"
        f"Ты: {player_total} голов {FOOTBALL_DICE[random.randint(0,5)]}\n"
        f"Соперник: {opponent_total} голов {FOOTBALL_DICE[random.randint(0,5)]}\n\n"
        f"🎙️ <i>\"{phrase}\"</i>\n\n"
        f"💰 <b>{result_text}</b>\n"
        f"🏦 Твой баланс: <b>{user_info['balance']} монет</b>",
        keyboard
    )
    await state.set_state(FootballDiceStates.result)