from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from typing import Dict, Any

from db.user_queries import *
from db.game_queries import *

router = Router()

# Футбольные карты (игроки с рейтингом вместо карточных значений)
# Масти для карт
SUITS = ["♥", "♦", "♣", "♠"]

# Футбольные карты с русскими именами и мастями
FOOTBALL_CARDS = {}

# Создаем карты по аналогии с игральными (4 масти для каждого номинала)
# Туз (1 или 11 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Лионель Месси {suit}'] = 11
    FOOTBALL_CARDS[f'Криштиану Роналду {suit}'] = 11
    FOOTBALL_CARDS[f'Пеле {suit}'] = 11
    FOOTBALL_CARDS[f'Марадона {suit}'] = 11

# Король (10 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Неймар {suit}'] = 10
    FOOTBALL_CARDS[f'Килиан Мбаппе {suit}'] = 10
    FOOTBALL_CARDS[f'Роберт Левандовски {suit}'] = 10
    FOOTBALL_CARDS[f'Кевин Де Брейне {suit}'] = 10

# Дама (10 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Вирджил ван Дейк {suit}'] = 10
    FOOTBALL_CARDS[f'Мануэль Нойер {suit}'] = 10
    FOOTBALL_CARDS[f'Лука Модрич {suit}'] = 10
    FOOTBALL_CARDS[f'Карим Бензема {suit}'] = 10

# Валет (10 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Мохамед Салах {suit}'] = 10
    FOOTBALL_CARDS[f'Харри Кейн {suit}'] = 10
    FOOTBALL_CARDS[f'Эрлинг Холанн {suit}'] = 10
    FOOTBALL_CARDS[f'Садио Мане {suit}'] = 10

# 10 (10 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Сон Хын Мин {suit}'] = 10
    FOOTBALL_CARDS[f'Джошуа Киммих {suit}'] = 10
    FOOTBALL_CARDS[f'Тони Кроос {suit}'] = 10
    FOOTBALL_CARDS[f'Серхио Рамос {suit}'] = 10

# 9 (9 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Поль Погба {suit}'] = 9
    FOOTBALL_CARDS[f'Антуан Гризманн {suit}'] = 9
    FOOTBALL_CARDS[f'Рахим Стерлинг {suit}'] = 9
    FOOTBALL_CARDS[f'Маркус Рэшфорд {suit}'] = 9

# 8 (8 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Джейдон Санчо {suit}'] = 8
    FOOTBALL_CARDS[f'Фил Фоден {suit}'] = 8
    FOOTBALL_CARDS[f'Деклан Райс {suit}'] = 8
    FOOTBALL_CARDS[f'Мэйсон Маунт {suit}'] = 8

# 7 (7 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Нголо Канте {suit}'] = 7
    FOOTBALL_CARDS[f'Анхель Ди Мария {suit}'] = 7
    FOOTBALL_CARDS[f'Эден Азар {suit}'] = 7
    FOOTBALL_CARDS[f'Лукас Эрнандес {suit}'] = 7

# 6 (6 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Трент Александер-Арнольд {suit}'] = 6
    FOOTBALL_CARDS[f'Андрю Робертсон {suit}'] = 6
    FOOTBALL_CARDS[f'Кайл Уокер {suit}'] = 6
    FOOTBALL_CARDS[f'Аймерик Лапорт {suit}'] = 6

# 5 (5 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Жоржиньо {suit}'] = 5
    FOOTBALL_CARDS[f'Марко Верратти {suit}'] = 5
    FOOTBALL_CARDS[f'Френки де Йонг {suit}'] = 5
    FOOTBALL_CARDS[f'Родри {suit}'] = 5

# 4 (4 очков)
for suit in SUITS:
    FOOTBALL_CARDS[f'Эдер Милитан {suit}'] = 4
    FOOTBALL_CARDS[f'Давид Алаба {suit}'] = 4
    FOOTBALL_CARDS[f'Альфонсо Дэвис {suit}'] = 4
    FOOTBALL_CARDS[f'Ашраф Хакими {suit}'] = 4

# 3 (3 очка)
for suit in SUITS:
    FOOTBALL_CARDS[f'Анхель ди Мария {suit}'] = 3
    FOOTBALL_CARDS[f'Кай Хаверц {suit}'] = 3
    FOOTBALL_CARDS[f'Джейми Варди {suit}'] = 3
    FOOTBALL_CARDS[f'Рафаэль Варан {suit}'] = 3

# 2 (2 очка)
for suit in SUITS:
    FOOTBALL_CARDS[f'Джордан Пикфорд {suit}'] = 2
    FOOTBALL_CARDS[f'Уго Льорис {suit}'] = 2
    FOOTBALL_CARDS[f'Ян Облак {suit}'] = 2
    FOOTBALL_CARDS[f'Тибо Куртуа {suit}'] = 2

# Футбольные фразы комментатора вместо бандитки
COMMENTATOR_PHRASES = {
    'start': [
        "Добро пожаловать на стадион! Готовы к футбольному 21? ⚽",
        "Мяч в центре поля! Кто забьёт первый? 🎯",
        "Напряжение нарастает... Игра начинается! 🔥",
        "Болельщики замерли в ожидании первого паса! 👀",
        "Сегодня на поле - лучшие из лучших! 💫"
    ],
    'win': [
        "ГООООЛ! Невероятная победа! 🎉",
        "Вот это мастерство! Игрок демонстрирует класс! ⭐",
        "Болельщики сходят с ума! Какая игра! 🤯",
        "Такой красоты я давно не видел! Фантастика! ✨",
        "Это будет помниться долго! Великолепно! 👏"
    ],
    'lose': [
        "Упустили победу... Жаль 😔",
        "Не повезло сегодня... В следующий раз точно получится! 💪",
        "Соперник был сильнее... Но вы держались достойно! 🛡️",
        "Иногда проигрывают даже лучшие... Не вешайте нос! 🌟",
        "Это всего лишь одна игра! Впереди ещё много матчей! ⚽"
    ],
    'perfect_score': [
        "ИДЕАЛЬНЫЙ ХЕТ-ТРИК! 21 очко! 🎯",
        "БРАВО! Абсолютная точность! 💫",
        "Такого я ещё не видел! Феноменально! 🤩",
        "Это войдёт в историю турнира! Легендарно! 📜",
        "Снимите шляпу! Величайшее выступление! 🎩"
    ],
    'draw': [
        "Ничья! Напряжённая борьба до последней секунды! ⏱️",
        "Равная игра! Оба заслуживают уважения! 🤝",
        "Интрига сохраняется до следующей встречи! 🔄",
        "Никто не хотел уступать! Вот это характер! 💪",
        "Справедливый результат! Оба молодцы! 👏"
    ],
    'add_player': [
        "Игрок выходит на замену! Усиливаем атаку! ⚡",
        "Свежие силы на поле! Что это изменит? 🔄",
        "Тренер делает ход! Интересное решение! 🧠",
        "Новый игрок входит в игру! Посмотрим на его impact! 💥",
        "Ротация составов! Кто проявит себя? 🌟"
    ],
    'stand': [
        "Игрок доволен составом! Решено не менять 🤔",
        "Тренер сохраняет текущую тактику! Интересно... 🧐",
        "Никаких замен! Верят в текущую команду! 💪",
        "Состав остаётся прежним! Рискованно? 🎲",
        "Решено не рисковать! Играем тем, что есть! ⚽"
    ],
    'over_score': [
        "Перебор! Слишком много игроков в атаке! 🚨",
        "Тактическая ошибка! Перегрузили состав 😬",
        "Дисбаланс в команде! Нужно было лучше распределить силы! ⚖️",
        "Перебор с атакующими! Забыли про защиту! 🛡️",
        "Команда потеряла равновесие! Слишком рискованно! 💣"
    ]
}

class Football21States(StatesGroup):
    choosing_bet = State()
    playing = State()

# Ставки для футбольной версии
FOOTBALL_BET_AMOUNTS = [100, 250, 500, 1000, 2000]

@router.callback_query(F.data == "open_football21")
async def open_football21(callback: CallbackQuery, state: FSMContext):
    """Открытие футбольной игры 21"""
    user_id = callback.from_user.id
    user = await get_user_by_id(user_id)

    if user['balance'] < min(FOOTBALL_BET_AMOUNTS):
        await callback.answer(
            f"⚽ Нужно минимум {min(FOOTBALL_BET_AMOUNTS)} монет для выхода на поле!",
            show_alert=True
        )
        return

    # Устанавливаем состояние выбора ставки
    await state.set_state(Football21States.choosing_bet)

    # Кнопки ставок
    bet_buttons = []
    for amount in FOOTBALL_BET_AMOUNTS:
        if user['balance'] >= amount:
            bet_buttons.append([InlineKeyboardButton(
                text=f"⚽ Ставка: {amount} монет",
                callback_data=f"football21_bet:{amount}"
            )])

    # Добавляем кнопки просмотра карт и статистики
    bet_buttons.append([InlineKeyboardButton(text="📊 Статистика", callback_data="football21_stats")])
    bet_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=bet_buttons)
    commentator_phrase = random.choice(COMMENTATOR_PHRASES['start'])

    await callback.message.edit_text(
        f"⚽ <b>ФУТБОЛЬНЫЙ БЛЭК ДЖЕК</b>\n\n"
        f"🎙️ <i>\"{commentator_phrase}\"</i>\n\n"
        f"📜 <b>Правила игры:</b>\n"
        f"<blockquote>▫️ Собери команду на 21 очко\n"
        f"▫️ Каждый игрок имеет свой рейтинг\n"
        f"▫️ Идеальная команда (21 очко) = x3 ставки\n"
        f"▫️ Перебор (>21) = автоматическое поражение\n"
        f"▫️ При ничье - возврат ставки</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user['balance']} монет\n\n"
        f"<i>Выберите действие:</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("football21_bet:"))
async def start_football21(callback: CallbackQuery, state: FSMContext):
    """Начало футбольной игры 21"""
    user_id = callback.from_user.id
    bet_amount = int(callback.data.split(":")[1])
    
    user_info = await get_user_by_id(user_id)
    if user_info['balance'] < bet_amount:
        await callback.answer("Недостаточно монет!", show_alert=True)
        return

    # Снимаем ставку
    await update_user_balance(user_id, -bet_amount)

    # Формируем начальные команды
    available_players = list(FOOTBALL_CARDS.keys())
    user_team = random.sample(available_players, 2)
    opponent_team = random.sample(available_players, 2)

    # Считаем очки
    user_score = calculate_score_with_aces(user_team)
    opponent_score = calculate_score_with_aces(opponent_team)

    await state.update_data(
        bet_amount=bet_amount,
        user_score=user_score,
        opponent_score=opponent_score,
        user_team=user_team,
        opponent_team=opponent_team,
        available_players=available_players
    )

    # Устанавливаем состояние игры
    await state.set_state(Football21States.playing)

    # Проверяем сразу выигрышные комбинации
    if user_score == 21 and opponent_score != 21:
        await handle_perfect_score(callback, state)
        return
    elif opponent_score == 21 and user_score != 21:
        await handle_opponent_perfect(callback, state)
        return
    elif user_score == 21 and opponent_score == 21:
        await handle_double_perfect(callback, state)
        return

    # Показываем текущее состояние игры
    await show_game_state(callback, state)

async def show_game_state(callback: CallbackQuery, state: FSMContext):
    """Показывает текущее состояние игры"""
    data = await state.get_data()
    
    # Форматируем список игроков с значениями
    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_visible = data['opponent_team'][0]  # Показываем только первого игрока соперника
    opponent_value = FOOTBALL_CARDS[opponent_visible]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить игрока", callback_data="football21_add")],
        [InlineKeyboardButton(text="⏹️ Зафиксировать состав", callback_data="football21_stand")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>ФУТБОЛЬНЫЙ 21 - ТЕКУЩИЙ СЧЁТ</b>\n\n"
        f"<b>Ваша команда:</b> {data['user_score']} очков\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b>\n"
        f"• {opponent_visible} - {opponent_value}\n"
        f"• ⚽ [Скрытый игрок]\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['add_player'])}\"</i>\n\n"
        f"Что будете делать?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "football21_add", Football21States.playing)
async def add_player(callback: CallbackQuery, state: FSMContext):
    """Добавление нового игрока в команду"""
    data = await state.get_data()
    
    # Исключаем уже выбранных игроков
    used_players = data['user_team'] + data['opponent_team']
    available_players = [p for p in data['available_players'] if p not in used_players]
    
    if not available_players:
        await callback.answer("Больше нет доступных игроков!", show_alert=True)
        return

    new_player = random.choice(available_players)
    new_user_team = data['user_team'] + [new_player]
    new_user_score = calculate_score_with_aces(new_user_team)

    await state.update_data(
        user_team=new_user_team,
        user_score=new_user_score
    )

    # Проверяем перебор
    if new_user_score > 21:
        await handle_over_score(callback, state)
        return

    await show_game_state(callback, state)
    await callback.answer(f"Добавлен: {new_player}!")

@router.callback_query(F.data == "football21_stand", Football21States.playing)
async def stand_team(callback: CallbackQuery, state: FSMContext):
    """Фиксация состава и завершение игры"""
    data = await state.get_data()
    
    # Соперник добирает игроков по правилам (до 17 очков)
    opponent_team = data['opponent_team']
    opponent_score = data['opponent_score']
    used_players = data['user_team'] + opponent_team
    available_players = [p for p in data['available_players'] if p not in used_players]

    while opponent_score < 17 and available_players:
        new_player = random.choice(available_players)
        opponent_team.append(new_player)
        opponent_score += FOOTBALL_CARDS[new_player]
        available_players.remove(new_player)

    await state.update_data(
        opponent_team=opponent_team,
        opponent_score=opponent_score
    )

    await finish_football21(callback, state)

async def finish_football21(callback: CallbackQuery, state: FSMContext):
    """Завершение игры и подсчет результатов"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Форматируем списки команд с значениями
    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['opponent_team']])

    # Определяем результат
    if data['user_score'] > 21:
        result = "lose"
        result_text = "💀 ПЕРЕБОР! Ваша команда несбалансирована!"
        win_amount = 0
        phrase = random.choice(COMMENTATOR_PHRASES['over_score'])
    elif data['opponent_score'] > 21:
        result = "win"
        win_amount = data['bet_amount'] * 2
        result_text = f"✨ ПОБЕДА! Соперник перебрал! +{win_amount} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['win'])
    elif data['user_score'] > data['opponent_score']:
        result = "win"
        win_amount = data['bet_amount'] * 2
        result_text = f"✨ ПОБЕДА! Ваша команда сильнее! +{win_amount} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['win'])
    elif data['user_score'] < data['opponent_score']:
        result = "lose"
        win_amount = 0
        result_text = "💀 ПОРАЖЕНИЕ! Соперник оказался сильнее!"
        phrase = random.choice(COMMENTATOR_PHRASES['lose'])
    else:
        result = "draw"
        win_amount = data['bet_amount']
        result_text = f"🔄 НИЧЬЯ! Возврат {data['bet_amount']} монет"
        phrase = random.choice(COMMENTATOR_PHRASES['draw'])

    # Начисляем выигрыш
    if win_amount > 0:
        await update_user_balance(user_id, win_amount)

    # Сохраняем результат игры
    await save_game_result(
        user_id=user_id,
        game_type="football_21",
        result=result,
        bet_amount=data['bet_amount'],
        win_amount=win_amount,
        player_score=data['user_score'],
        opponent_score=data['opponent_score']
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>ФИНАЛЬНЫЙ СЧЁТ</b>\n\n"
        f"<b>Ваша команда:</b> {data['user_score']} очков\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b> {data['opponent_score']} очков\n"
        f"{opponent_team_text}\n\n"
        f"🎙️ <i>\"{phrase}\"</i>\n\n"
        f"💰 <b>{result_text}</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.clear()

# Обработчики специальных ситуаций (perfect score и т.д.)
async def handle_perfect_score(callback: CallbackQuery, state: FSMContext):
    """Обработка идеального счета 21"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    win_amount = data['bet_amount'] * 3
    await update_user_balance(user_id, win_amount)
    
    await save_game_result(
        user_id=user_id,
        game_type="football_21",
        result="win",
        bet_amount=data['bet_amount'],
        win_amount=win_amount,
        player_score=21,
        opponent_score=data['opponent_score']
    )

    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['opponent_team']])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>ИДЕАЛЬНЫЙ ХЕТ-ТРИК! 🎯</b>\n\n"
        f"<b>Ваша команда:</b> 21 очко\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b> {data['opponent_score']} очков\n"
        f"{opponent_team_text}\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['perfect_score'])}\"</i>\n\n"
        f"💰 <b>ВЫИГРЫШ: {win_amount} монет! (x3 ставки)</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.clear()

async def handle_opponent_perfect(callback: CallbackQuery, state: FSMContext):
    """Обработка ситуации, когда у соперника идеальный счет 21"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    await save_game_result(
        user_id=user_id,
        game_type="football_21",
        result="lose",
        bet_amount=data['bet_amount'],
        win_amount=0,
        player_score=data['user_score'],
        opponent_score=21
    )

    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['opponent_team']])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>КРИТИЧЕСКАЯ НЕУДАЧА! 💀</b>\n\n"
        f"<b>Ваша команда:</b> {data['user_score']} очков\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b> 21 очко\n"
        f"{opponent_team_text}\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['lose'])}\"</i>\n\n"
        f"💀 <b>Соперник собрал идеальную команду!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.clear()

async def handle_double_perfect(callback: CallbackQuery, state: FSMContext):
    """Обработка ситуации, когда обе команды набрали 21 очко"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Возвращаем ставку
    await update_user_balance(user_id, data['bet_amount'])
    
    await save_game_result(
        user_id=user_id,
        game_type="football_21",
        result="draw",
        bet_amount=data['bet_amount'],
        win_amount=data['bet_amount'],
        player_score=21,
        opponent_score=21
    )

    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['opponent_team']])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>НЕВЕРОЯТНАЯ НИЧЬЯ! 🤝</b>\n\n"
        f"<b>Ваша команда:</b> 21 очко\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b> 21 очко\n"
        f"{opponent_team_text}\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['draw'])}\"</i>\n\n"
        f"🔄 <b>Обе команды идеальны! Возврат ставки.</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.clear()

async def handle_over_score(callback: CallbackQuery, state: FSMContext):
    """Обработка перебора очков"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Соперник все равно добирает игроков
    opponent_team = data['opponent_team']
    opponent_score = data['opponent_score']
    used_players = data['user_team'] + opponent_team
    available_players = [p for p in data['available_players'] if p not in used_players]

    while opponent_score < 17 and available_players:
        new_player = random.choice(available_players)
        opponent_team.append(new_player)
        opponent_score += FOOTBALL_CARDS[new_player]
        available_players.remove(new_player)

    await save_game_result(
        user_id=user_id,
        game_type="football_21",
        result="lose",
        bet_amount=data['bet_amount'],
        win_amount=0,
        player_score=data['user_score'],
        opponent_score=opponent_score
    )

    user_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['user_team']])
    opponent_team_text = "\n".join([f"• {player} - {FOOTBALL_CARDS[player]}" for player in data['opponent_team']])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть снова", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(
        f"⚽ <b>ПЕРЕБОР! 🚨</b>\n\n"
        f"<b>Ваша команда:</b> {data['user_score']} очков (перебор!)\n"
        f"{user_team_text}\n\n"
        f"<b>Команда соперника:</b> {opponent_score} очков\n"
        f"{opponent_team_text}\n\n"
        f"🎙️ <i>\"{random.choice(COMMENTATOR_PHRASES['over_score'])}\"</i>\n\n"
        f"💀 <b>Слишком много игроков! Команда несбалансирована!</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.clear()

@router.callback_query(F.data == "football21_stats")
async def show_football21_stats(callback: CallbackQuery):
    """Показывает статистику игр в футбольный 21"""
    user_id = callback.from_user.id
    stats = await get_user_game_stats(user_id, "football_21")
    
    if stats['total_games'] == 0:
        text = "📊 <b>Статистика Футбольного Блэк Джека</b>\n\n"
        text += "Вы ещё не сыграли ни одной игры! 🏃‍♂️\n"
        text += "Начните играть, чтобы собрать статистику! ⚽"
    else:
        win_rate = (stats['wins'] / stats['total_games'] * 100) if stats['total_games'] > 0 else 0
        profit = stats['total_winnings'] - stats['total_bets']
        
        text = (
            "📊 <b>Статистика Футбольного Блэк Джека</b>\n\n"
            f"<blockquote>🎯 Всего игр: {stats['total_games']}\n"
            f"✅ Побед: {stats['wins']}\n"
            f"❌ Поражений: {stats['losses']}\n"
            f"🤝 Ничьих: {stats['draws']}\n"
            f"📈 Процент побед: {win_rate:.1f}%\n\n"
            f"💰 Общий выигрыш: {stats['total_winnings']} монет\n"
            f"🎰 Общие ставки: {stats['total_bets']} монет\n"
            f"💵 Прибыль: {profit} монет</blockquote>\n\n"
        )
        
        if profit > 0:
            text += "⭐ Вы в плюсе! Отличная игра! 🏆"
        else:
            text += "💪 Продолжайте играть, удача обязательно улыбнётся! ⚽"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚽ Играть", callback_data="open_football21")],
        [InlineKeyboardButton(text="🏠 Назад", callback_data="back_to_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

def calculate_score_with_aces(cards):
    """Рассчитывает сумму очков с учетом тузов (1 или 11)"""
    total = 0
    aces = 0
    
    for card in cards:
        value = FOOTBALL_CARDS[card]
        if value == 11:  # Это туз
            aces += 1
            total += 11
        else:
            total += value
    
    # Корректируем тузы если перебор
    while total > 21 and aces > 0:
        total -= 10  # Туз становится 1 вместо 11
        aces -= 1
    
    return total