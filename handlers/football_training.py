from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from datetime import datetime, timedelta
import re

from db.user_queries import get_user_by_id, update_user_balance, update_user_trophies
from db.game_queries import (
    save_training_result, 
    get_training_stats, 
    check_training_cooldown,
    get_memory_records,
    get_dribbling_records,
    check_and_update_memory_record,
    check_and_update_dribbling_record,
    get_minesweeper_stats
)

router = Router()

class FootballTrainingStates(StatesGroup):
    choosing_drill = State()
    memory_challenge = State()
    memory_challenge_playing = State()
    dribbling_challenge = State()
    minesweeper_challenge = State()

# Тренировочные упражнения с наградами
TRAINING_DRILLS = {
    'memory_challenge': {
        'name': '🧠 Футбольная память',
        'description': 'Запомни последовательность и повтори её',
        'reward': 150,
        'cooldown': timedelta(minutes=10)
    },
    'dribbling_challenge': {
        'name': '🌀 Обводка соперников',
        'description': 'Проведи мяч мимо защитников',
        'reward': 150,
        'cooldown': timedelta(minutes=10)
    },
    'minesweeper': {
        'name': '💣 Футбольный сапёр',
        'description': 'Найди мяч среди мин',
        'reward': 135,  # Максимум 9 * 15 = 135 монет
        'cooldown': timedelta(minutes=10)
    }
}

# Дополним фразы тренера
# Дополним фразы тренера - добавим все необходимые ключи
COACH_PHRASES = {
    'welcome': [
        "Добро пожаловать на тренировку! Готов улучшить свои навыки? ⚽",
        "На поле поработаем! Покажи, на что способен! 💪",
        "Тренировка - путь к совершенству! Начнём? 🏃‍♂️",
        "Футбольное мастерство не приходит само! За работу! 🔥",
        "Сегодня будем оттачивать технику! Выбирай упражнение! 🎯",
        "Разминка окончена, пора к делу! Выбирай упражнение! 🔥",
        "Футбол - это не только ноги, но и голова! Проверим твою память! 🧠"
    ],
    'success': [
        "Отлично! Настоящий профессионал! 👏",
        "Браво! Техника на высшем уровне! ⭐",
        "Вот это да! Ты рождён для футбола! 🌟",
        "Идеальное выполнение! Так держать! 💫",
        "Мастерский приём! Тренер гордится! 🏆",
        "Феноменально! Такой концентрации я давно не видел! 🔥",
        "Великолепно! Ты просто машина! 🚀",
        "Потрясающе! С таким подходом ты станешь звездой! 🌠",
        "Изумительно! Твои навыки поражают! 💎",
        "Безупречно! Настоящий мастер своего дела! 🏅"
    ],
    'failure': [
        "Не расстраивайся! Практика делает совершенным! 💪",
        "Было близко! В следующий раз получится! 🔄",
        "Нужно больше тренироваться! Не сдавайся! ⚽",
        "Ошибаться - это нормально! Главное - учиться! 📚",
        "Сложное упражнение! Попробуй ещё раз позже! ⏳",
        "Не вешай нос! Даже лучшие ошибаются! 🌈",
        "Это всего лишь небольшая неудача! Встань и продолжай! 🚀",
        "Тренировка - это путь! Каждая ошибка - шаг вперёд! 🛣️",
        "Не переживай! Завтра получится лучше! ☀️",
        "Сконцентрируйся! Ты сможешь! 💫"
    ],
    'memory_instructions': [
        "Запомни последовательность как игроков на поле! 🧠",
        "Внимание! Запоминай порядок как тактику тренера! 📋",
        "Сфокусируйся! Это как запомнить расстановку команды! 🔍",
        "Запомни эту комбинацию как лучший пас! ⚽",
        "Держи в голове эту последовательность как схему атаки! 🧠",
        "Запоминай! Это твой ключ к успеху! 🔑",
        "Внимательно смотри! Эта комбинация принесет победу! 👀",
        "Запомни порядок как номера игроков! 🔢",
        "Сконцентрируйся! Это важно для твоей игры! 💡",
        "Запоминай быстро! Как настоящий профессионал! ⚡"
    ],
    'memory_success': [
        "Верно! Отличная память! 🧠",
        "Точно! Ты запомнил идеально! ✅",
        "Правильно! Память как у скаута! 🔍",
        "В яблочко! Отличная концентрация! 🎯",
        "Идеально! Твоя память не подводит! 💫",
        "Браво! Ты вспомнил всё точно! 👏",
        "Великолепно! Память работает на отлично! 🌟",
        "Супер! Ты не ошибся! 🚀",
        "Прекрасно! Следующий элемент? 💎",
        "Отлично! Двигаемся дальше! 🔥"
    ],
    'cooldown': [
        "Отлично поработал! Давай отдохнём немного! ☕",
        "Мышцы устали! Нужен перерыв! 🏖️",
        "Хорошая тренировка! Вернёмся к ней позже! ⏰",
        "Не перетруждайся! Отдых - часть тренировки! 😴",
        "Отличный прогресс! Давай передохнём! 🌿",
        "На сегодня хватит! Завтра продолжим! 🌙",
        "Усталость - признак хорошей работы! Отдохни! 💤",
        "Ты хорошо потрудился! Время восстановить силы! ⚡",
        "Тренировка завершена! Отличная работа! 🏆",
        "На сегодня достаточно! Горжусь твоими успехами! 🌟"
    ],
    'minesweeper_instructions': [
        "Найди футбольный мяч среди защитников! ⚽",
        "Будь осторожен! Один неверный шаг - и фол! 🚷",
        "Ищи мяч, избегая столкновений! 🔍",
        "Прояви тактическое мышление! 🧠",
        "Найди путь к воротам через защиту! 🥅"
    ],
    'minesweeper_success': [
        "Отличная работа! Ты нашёл мяч! ⚽",
        "Тактический гений! Ты избежал всех защитников! 🎯",
        "Идеальное зрение! Мяч найден! 👁️",
        "Блестяще! Ты обманул всю защиту! ✨",
        "Мастерский поиск! Ты заслужил награду! 🏆"
    ],
    'minesweeper_failure': [
        "Фол! Ты столкнулся с защитником! 🚷",
        "Осторожнее! Нужно лучше смотреть по сторонам! 👀",
        "Защита перехватила мяч! В следующий раз получится! 🔄",
        "Не расстраивайся! Тактику нужно отработать! 📚",
        "Повезёт в следующий раз! Учись читать игру! 🎮"
    ]
}

async def show_records_menu(callback: CallbackQuery):
    """Показать меню рекордов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Рекорды памяти", callback_data="show_memory_records")],
        [InlineKeyboardButton(text="🌀 Рекорды обводки", callback_data="show_dribbling_records")],
        [InlineKeyboardButton(text="🔙 Назад к тренировкам", callback_data="back_to_training")]
    ])
    
    await safe_edit_message(
        callback,
        "🏆 <b>ФУТБОЛЬНЫЕ РЕКОРДЫ</b>\n\n"
        "Здесь собраны лучшие достижения игроков!\n\n"
        "Выберите категорию для просмотра:",
        keyboard
    )

@router.callback_query(F.data == "training_records")
async def handle_training_records(callback: CallbackQuery):
    """Обработчик кнопки рекордов"""
    await show_records_menu(callback)

@router.callback_query(F.data == "show_memory_records")
async def show_memory_records(callback: CallbackQuery):
    """Показать рекорды памяти"""
    records = await get_memory_records(10)
    
    if not records:
        records_text = "🏆 <b>РЕКОРДЫ ФУТБОЛЬНОЙ ПАМЯТИ</b>\n\n📝 Пока нет рекордов. Стань первым!"
    else:
        records_text = "🏆 <b>РЕКОРДЫ ФУТБОЛЬНОЙ ПАМЯТИ</b>\n\n"
        records_text += "<i>Топ-10 самых быстрых прохождений (5 элементов):</i>\n\n"
        
        for i, record in enumerate(records, 1):
            username = record['username'] or f"Игрок {record['user_id']}"
            time_taken = record['time_taken']
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            records_text += f"{medal} {username} - {time_taken:.2f}с\n"

    
    records_text += "\n🏅 Рекорд игры: Кот - 6.49с"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌀 Рекорды обводки", callback_data="show_dribbling_records")],
        [InlineKeyboardButton(text="🔙 Назад к рекордам", callback_data="training_records")]
    ])
    
    await safe_edit_message(callback, records_text, keyboard)

@router.callback_query(F.data == "show_dribbling_records")
async def show_dribbling_records(callback: CallbackQuery):
    """Показать рекорды обводки"""
    records = await get_dribbling_records(10)
    
    if not records:
        records_text = "🏆 <b>РЕКОРДЫ ОБВОДКИ СОПЕРНИКОВ</b>\n\n📝 Пока нет рекордов. Стань первым!"
    else:
        records_text = "🏆 <b>РЕКОРДЫ ОБВОДКИ СОПЕРНИКОВ</b>\n\n"
        records_text += "<i>Топ-10 рекордсменов по количеству обведённых защитников:</i>\n\n"
        
        for i, record in enumerate(records, 1):
            username = record['username'] or f"Игрок {record['user_id']}"
            defenders = record['defenders_beaten']
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            records_text += f"{medal} {username} - {defenders} защитников\n"

    records_text += "\n🏅 Рекорд игры: Vesel4ak - 24 защитников"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Рекорды памяти", callback_data="show_memory_records")],
        [InlineKeyboardButton(text="🔙 Назад к рекордам", callback_data="training_records")]
    ])
    
    await safe_edit_message(callback, records_text, keyboard)

# Обновим меню тренировок - добавим кнопку рекордов
@router.callback_query(F.data == "open_training")
async def start_football_training(callback: CallbackQuery, state: FSMContext):
    """Начало футбольных тренировок"""
    user_id = callback.from_user.id
    user_info = await get_user_by_id(user_id)
    
    coach_phrase = random.choice(COACH_PHRASES['welcome'])
    
    # Создаем кнопки упражнений
    drill_buttons = []
    for drill_id, drill_info in TRAINING_DRILLS.items():
        cooldown_info = await check_training_cooldown(user_id, drill_id)
        
        if cooldown_info['available']:
            button_text = f"{drill_info['name']} - 🟢 Доступно"
        else:
            time_left = cooldown_info['time_left']
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            button_text = f"{drill_info['name']} - ⏳ {hours:02d}:{minutes:02d}"
        
        drill_buttons.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"start_drill:{drill_id}" if cooldown_info['available'] else "cooldown_info"
        )])
    
    # Добавляем кнопки статистики, рекордов и назад
    drill_buttons.append([
        # InlineKeyboardButton(text="📊 Статистика", callback_data="training_stats"),
        InlineKeyboardButton(text="🏆 Рекорды", callback_data="training_records")
    ])
    drill_buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=drill_buttons)
    
    await safe_edit_message(
        callback,
        f"⚽ <b>ФУТБОЛЬНЫЕ ТРЕНИРОВКИ</b>\n\n"
        f"👨‍🏫 <i>\"{coach_phrase}\"</i>\n\n"
        f"💪 <b>Зарабатывай монеты, улучшай навыки!</b>\n\n"
        f"🎯 <b>Доступные упражнения:</b>\n"
        f"<blockquote>🧠 Футбольная память - 150 монет\n"
        f"🌀 Обводка соперников - 150 монет\n"
        f"💣 Футбольный сапёр - до 135 монет</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user_info['balance']} монет\n\n"
        f"<i>Выберите упражнение для тренировки:</i>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.choosing_drill)

# ОБНОВЛЕННЫЙ ОБРАБОТЧИК УПРАЖНЕНИЙ С ПРОВЕРКОЙ ДОСТУПНОСТИ
@router.callback_query(F.data.startswith("start_drill:"))
async def start_drill(callback: CallbackQuery, state: FSMContext):
    """Начало выполнения упражнения с проверкой доступности"""
    drill_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # ПРОВЕРЯЕМ ДОСТУПНОСТЬ ТРЕНИРОВКИ ПЕРЕД НАЧАЛОМ
    cooldown_info = await check_training_cooldown(user_id, drill_id)
    
    if not cooldown_info['available']:
        time_left = cooldown_info['time_left']
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        
        await callback.answer(
            f"⏳ Эта тренировка ещё на перезарядке! Доступна через {hours:02d}:{minutes:02d}",
            show_alert=True
        )
        return
    
    # Если тренировка доступна, продолжаем
    await state.update_data(
        drill_id=drill_id,
        potential_reward=TRAINING_DRILLS[drill_id]['reward']
    )
    
    if drill_id == 'memory_challenge':
        await start_memory_challenge(callback, state)
    elif drill_id == 'dribbling_challenge':
        await start_dribbling_challenge(callback, state)
    elif drill_id == 'minesweeper':
        await start_minesweeper_challenge(callback, state)

# ОБНОВЛЕННАЯ ФУТБОЛЬНАЯ ПАМЯТЬ (5 элементов)
async def start_memory_challenge(callback: CallbackQuery, state: FSMContext):
    """Упражнение на футбольную память (5 элементов)"""
    football_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    sequence = random.sample(football_emojis, 5)  # Теперь 5 элементов
    
    await state.update_data(
        memory_sequence=sequence,
        memory_current_step=0,
        memory_start_time=datetime.now()
    )
    
    instruction_phrase = random.choice(COACH_PHRASES['memory_instructions'])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Начать тест", callback_data="memory_start_test")]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b>\n\n"
        f"🎯 <b>Задание:</b> Запомни последовательность из 5 элементов и повтори её!\n"
        f"💰 <b>Награда:</b> 150 монет\n\n"
        f"👨‍🏫 <i>\"{instruction_phrase}\"</i>\n\n"
        f"<b>Запомни последовательность:</b>\n"
        f"{' → '.join(sequence)}\n\n"
        f"<i>У тебя есть 15 секунд на запоминание. Нажми 'Начать тест' когда будешь готов!</i>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.memory_challenge)

@router.callback_query(F.data == "memory_start_test", FootballTrainingStates.memory_challenge)
async def start_memory_test(callback: CallbackQuery, state: FSMContext):
    """Начало теста памяти (5 элементов)"""
    state_data = await state.get_data()
    sequence = state_data['memory_sequence']
    
    all_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    wrong_emojis = [e for e in all_emojis if e != sequence[0]]
    random.shuffle(wrong_emojis)
    
    options = [sequence[0]] + wrong_emojis[:5]
    random.shuffle(options)
    
    buttons = []
    for emoji in options:
        is_correct = 1 if emoji == sequence[0] else 0
        buttons.append(InlineKeyboardButton(
            text=emoji, 
            callback_data=f"memory_guess:{is_correct}"
        ))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:3],
        buttons[3:]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b> | Шаг 1/5\n\n"
        f"⏰ <b>Время началось!</b> Вспоминай последовательность!\n\n"
        f"<b>Какой был первый элемент?</b>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.memory_challenge_playing)

@router.callback_query(F.data.startswith("memory_guess:"), FootballTrainingStates.memory_challenge_playing)
async def handle_memory_guess(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора в тесте памяти (5 элементов)"""
    state_data = await state.get_data()
    sequence = state_data['memory_sequence']
    current_step = state_data.get('memory_current_step', 0)
    is_correct = int(callback.data.split(":")[1])
    
    if not is_correct:
        await handle_training_failure(callback, state, "Неправильный выбор последовательности!")
        return
    
    current_step += 1
    await state.update_data(memory_current_step=current_step)
    
    success_phrase = random.choice(COACH_PHRASES['memory_success'])
    
    if current_step >= len(sequence):
        # Успешно завершили
        end_time = datetime.now()
        time_taken = (end_time - state_data['memory_start_time']).total_seconds()
        
        # Бонус за скорость
        time_bonus = max(0, int(40 - time_taken))  # Увеличили время для 5 элементов
        total_reward = state_data['potential_reward'] + time_bonus
        
        achievement = f"Отличная память! Время: {time_taken:.1f}с!"
        if time_bonus > 0:
            achievement += f" +{time_bonus} монет за скорость! ⚡"
        
        # Проверяем и обновляем рекорд
        user_info = await get_user_by_id(callback.from_user.id)
        username = user_info.get('username', callback.from_user.first_name)
        is_new_record = await check_and_update_memory_record(
            callback.from_user.id, username, time_taken, 5
        )
        
        if is_new_record:
            achievement += "\n🎉 Новый рекорд! Ты в топ-10!"
            
        await handle_training_success(callback, state, total_reward, achievement)
        return
    
    # Следующий шаг
    next_emoji = sequence[current_step]
    all_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    wrong_emojis = [e for e in all_emojis if e != next_emoji]
    random.shuffle(wrong_emojis)
    
    options = [next_emoji] + wrong_emojis[:5]
    random.shuffle(options)
    
    buttons = []
    for emoji in options:
        is_correct = 1 if emoji == next_emoji else 0
        buttons.append(InlineKeyboardButton(
            text=emoji, 
            callback_data=f"memory_guess:{is_correct}"
        ))
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:3],
        buttons[3:]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b> | Шаг {current_step + 1}/5\n\n"
        f"👨‍🏫 <i>\"{success_phrase}\"</i>\n\n"
        f"<b>Какой был следующий элемент?</b>",
        keyboard
    )

# ОБНОВЛЕННАЯ ОБВОДКА СОПЕРНИКОВ С РЕКОРДАМИ
async def start_dribbling_challenge(callback: CallbackQuery, state: FSMContext):
    """Упражнение на обводку соперников"""
    await state.update_data(
        dribble_round=1,
        dribble_reward=0
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Влево", callback_data="dribble:left"),
            InlineKeyboardButton(text="⬆️ Прямо", callback_data="dribble:straight"),
            InlineKeyboardButton(text="➡️ Вправо", callback_data="dribble:right")
        ]
    ])
    
    await safe_edit_message(
        callback,
        f"🌀 <b>ОБВОДКА СОПЕРНИКОВ</b>\n\n"
        f"🎯 <b>Задание:</b> Обведи защитника и заработай монеты!\n"
        f"💰 <b>Награда:</b> 15 монет за каждого обведённого защитника\n\n"
        f"<i>Выбери направление для обводки. Защитник попытается угадать твоё движение!</i>\n\n"
        f"<b>Раунд 1</b>\n"
        f"Выбери направление:",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.dribbling_challenge)

@router.callback_query(F.data.startswith("dribble:"), FootballTrainingStates.dribbling_challenge)
async def handle_dribble(callback: CallbackQuery, state: FSMContext):
    """Обработка движения в обводке"""
    state_data = await state.get_data()
    round_num = state_data['dribble_round']
    current_reward = state_data['dribble_reward']
    
    player_move = callback.data.split(":")[1]
    defender_move = random.choice(["left", "straight", "right"])
    
    if player_move == defender_move:
        # Защитник угадал - игра заканчивается
        total_reward = current_reward + 15
        
        # Проверяем и обновляем рекорд
        user_info = await get_user_by_id(callback.from_user.id)
        username = user_info.get('username', callback.from_user.first_name)
        is_new_record = await check_and_update_dribbling_record(
            callback.from_user.id, username, round_num
        )
        
        achievement = f"Обвёл {round_num} защитников! Но тебя перехватили."
        if is_new_record:
            achievement += "\n🎉 Новый рекорд! Ты в топ-10!"
            
        await handle_training_success(callback, state, total_reward, achievement)
        return
    
    # Успешная обводка
    round_num += 1
    current_reward += 15
    
    await state.update_data(
        dribble_round=round_num,
        dribble_reward=current_reward
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Влево", callback_data="dribble:left"),
            InlineKeyboardButton(text="⬆️ Прямо", callback_data="dribble:straight"),
            InlineKeyboardButton(text="➡️ Вправо", callback_data="dribble:right")
        ]
    ])
    
    move_translation = {
        "left": "влево",
        "straight": "прямо", 
        "right": "вправо"
    }
    
    await safe_edit_message(
        callback,
        f"🌀 <b>ОБВОДКА СОПЕРНИКОВ</b>\n\n"
        f"✅ Отлично! Ты пошёл {move_translation[player_move]}, "
        f"а защитник угадал {move_translation[defender_move]}!\n\n"
        f"💰 Заработано: {current_reward} монет\n"
        f"<b>Раунд {round_num}</b>\n"
        f"Выбери следующее направление:",
        keyboard
    )

# НОВЫЙ РЕЖИМ: ФУТБОЛЬНЫЙ САПЁР
async def start_minesweeper_challenge(callback: CallbackQuery, state: FSMContext):
    """Начало игры в футбольный сапёр"""
    # Создаем поле 3x3 с одной "миной" (защитником)
    positions = list(range(9))
    mine_position = random.choice(positions)
    safe_positions = [pos for pos in positions if pos != mine_position]
    
    await state.update_data(
        mine_position=mine_position,
        safe_positions=safe_positions,
        revealed_positions=[],
        current_reward=0,
        game_active=True
    )
    
    instruction_phrase = random.choice(COACH_PHRASES['minesweeper_instructions'])
    
    # Создаем клавиатуру 3x3
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:0"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:1"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:2")
        ],
        [
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:3"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:4"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:5")
        ],
        [
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:6"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:7"),
            InlineKeyboardButton(text="❓", callback_data=f"mine_reveal:8")
        ]
    ])
    
    await safe_edit_message(
        callback,
        f"💣 <b>ФУТБОЛЬНЫЙ САПЁР</b>\n\n"
        f"🎯 <b>Задание:</b> Найди футбольный мяч среди защитников!\n"
        f"💰 <b>Награда:</b> +15 монет за каждую безопасную клетку\n"
        f"🏆 <b>Максимум:</b> 135 монет (9 клеток)\n\n"
        f"👨‍🏫 <i>\"{instruction_phrase}\"</i>\n\n"
        f"<i>Выбери клетку. Если найдешь мяч - получишь награду!</i>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.minesweeper_challenge)

@router.callback_query(F.data.startswith("mine_reveal:"), FootballTrainingStates.minesweeper_challenge)
async def handle_mine_reveal(callback: CallbackQuery, state: FSMContext):
    """Обработка открытия клетки в сапёре"""
    state_data = await state.get_data()
    position = int(callback.data.split(":")[1])
    mine_position = state_data['mine_position']
    safe_positions = state_data['safe_positions']
    revealed_positions = state_data['revealed_positions']
    current_reward = state_data['current_reward']
    game_active = state_data['game_active']
    
    if not game_active or position in revealed_positions:
        await callback.answer("Эта клетка уже открыта!", show_alert=True)
        return
    
    # Добавляем позицию в открытые
    revealed_positions.append(position)
    
    if position == mine_position:
        # Наступили на мину - игра окончена
        await state.update_data(game_active=False)
        
        # Создаем финальную клавиатуру с результатом
        keyboard = create_minesweeper_keyboard(mine_position, revealed_positions, True)
        
        await safe_edit_message(
            callback,
            f"💣 <b>ФУТБОЛЬНЫЙ САПЁР</b>\n\n"
            f"💥 <b>ФОЛ!</b> Ты столкнулся с защитником!\n\n"
            f"💰 <b>Заработано:</b> {current_reward} монет\n\n"
            f"👨‍🏫 <i>\"{random.choice(COACH_PHRASES['minesweeper_failure'])}\"</i>",
            keyboard
        )
        
        # Сохраняем результат
        await save_training_result(
            user_id=callback.from_user.id,
            drill_type='minesweeper',
            success=False,
            reward_earned=current_reward,
            level=1
        )
        
        # НАЧИСЛЯЕМ НАГРАДУ ДАЖЕ ПРИ ПРОИГРЫШЕ
        if current_reward > 0:
            await update_user_balance(callback.from_user.id, current_reward)
        
        await asyncio.sleep(2)
        await show_minesweeper_continue_menu(callback, current_reward, False)
        return
    
    # Безопасная клетка - начисляем награду
    current_reward += 15
    await state.update_data(current_reward=current_reward, revealed_positions=revealed_positions)
    
    # Проверяем, остались ли безопасные клетки
    remaining_safe = [pos for pos in safe_positions if pos not in revealed_positions]
    
    if not remaining_safe:
        # Все безопасные клетки открыты - победа!
        await state.update_data(game_active=False)
        
        keyboard = create_minesweeper_keyboard(mine_position, revealed_positions, True)
        
        success_phrase = random.choice(COACH_PHRASES['minesweeper_success'])
        
        # НАЧИСЛЯЕМ НАГРАДУ ПЕРЕД СОХРАНЕНИЕМ РЕЗУЛЬТАТА
        await update_user_balance(callback.from_user.id, current_reward)
        
        await safe_edit_message(
            callback,
            f"💣 <b>ФУТБОЛЬНЫЙ САПЁР</b>\n\n"
            f"✅ <b>ПОБЕДА!</b> Ты нашёл мяч и избежал всех защитников!\n\n"
            f"💰 <b>Заработано:</b> {current_reward} монет\n\n"
            f"👨‍🏫 <i>\"{success_phrase}\"</i>",
            keyboard
        )
        
        # Сохраняем результат
        await save_training_result(
            user_id=callback.from_user.id,
            drill_type='minesweeper',
            success=True,
            reward_earned=current_reward,
            level=1
        )
        
        await asyncio.sleep(2)
        await show_minesweeper_continue_menu(callback, current_reward, True)
        return
    
    # Продолжаем игру
    keyboard = create_minesweeper_keyboard(mine_position, revealed_positions, False)
    
    await safe_edit_message(
        callback,
        f"💣 <b>ФУТБОЛЬНЫЙ САПЁР</b>\n\n"
        f"✅ <b>Безопасно!</b> Эта клетка пуста.\n\n"
        f"💰 <b>Текущий выигрыш:</b> {current_reward} монет\n"
        f"🎯 <b>Осталось безопасных клеток:</b> {len(remaining_safe)}\n\n"
        f"<i>Продолжай искать мяч!</i>",
        keyboard
    )

def create_minesweeper_keyboard(mine_position, revealed_positions, game_ended):
    """Создать клавиатуру для сапёра"""
    buttons = []
    for i in range(9):
        if i in revealed_positions:
            if i == mine_position:
                text = "🚷"  # Защитник
            else:
                text = "✅"  # Безопасная клетка
        elif game_ended and i == mine_position:
            text = "⚽"  # Мяч (показываем только в конце)
        else:
            text = "❓"
        
        if game_ended or i in revealed_positions:
            callback_data = "mine_ignored"
        else:
            callback_data = f"mine_reveal:{i}"
        
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    # Разбиваем на 3 строки по 3 кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[0:3],
        buttons[3:6],
        buttons[6:9]
    ])
    
    return keyboard

async def show_minesweeper_continue_menu(callback: CallbackQuery, reward: int, success: bool):
    """Показать меню продолжения после сапёра"""
    # Получаем ОБНОВЛЕННУЮ информацию о пользователе после начисления награды
    user_info = await get_user_by_id(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Тренироваться ещё", callback_data="open_training")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
    
    status = "УСПЕШНО" if success else "НЕ УДАЛОСЬ"
    
    await safe_edit_message(
        callback,
        f"💣 <b>ФУТБОЛЬНЫЙ САПЁР - ЗАВЕРШЕНО</b>\n\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"💰 <b>Заработано:</b> {reward} монет\n"
        f"🏦 <b>Текущий баланс:</b> {user_info['balance']} монет\n\n"  # Используем обновленный баланс
        f"<i>Выберите следующее действие:</i>",
        keyboard
    )

# Обновим функцию успешного завершения
async def handle_training_success(callback: CallbackQuery, state: FSMContext, reward: int, achievement: str):
    """Обработка успешного завершения тренировки"""
    state_data = await state.get_data()
    user_id = callback.from_user.id
    drill_id = state_data['drill_id']
    
    # Начисляем награду (для сапёра награда уже начислена)
    if drill_id != 'minesweeper':
        await update_user_balance(user_id, reward)
    
    # Сохраняем результат тренировки
    if drill_id != 'minesweeper':  # Для сапёра сохраняем отдельно
        await save_training_result(
            user_id=user_id,
            drill_type=drill_id,
            success=True,
            reward_earned=reward,
            level=1
        )
    
    user_info = await get_user_by_id(user_id)
    coach_phrase = random.choice(COACH_PHRASES['success'])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Тренироваться ещё", callback_data="open_training")],
        # [InlineKeyboardButton(text="📊 Статистика", callback_data="training_stats")],
        [InlineKeyboardButton(text="🏆 Рекорды", callback_data="training_records")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
    
    await safe_edit_message(
        callback,
        f"🎉 <b>ТРЕНИРОВКА ЗАВЕРШЕНА!</b>\n\n"
        f"👨‍🏫 <i>\"{coach_phrase}\"</i>\n\n"
        f"✅ <b>Достижение:</b> {achievement}\n"
        f"💰 <b>Заработано:</b> +{reward} монет\n"
        f"🏦 <b>Баланс:</b> {user_info['balance']} монет\n\n"
        f"<i>Отличная работа! Возвращайся на следующую тренировку!</i>",
        keyboard
    )
    
    await state.clear()

async def show_training_stats(callback: CallbackQuery):
    """Показать статистику тренировок"""
    user_id = callback.from_user.id
    stats = await get_training_stats(user_id)
    minesweeper_stats = await get_minesweeper_stats(user_id)
    
    # Обработка случая, когда статистика не найдена
    if not stats:
        stats = {
            'total_trainings': 0,
            'successful': 0,
            'success_rate': 0,
            'total_earned': 0
        }
    
    stats_text = (
        f"📊 <b>Статистика Тренировок</b>\n\n"
        f"<blockquote>🎯 Всего тренировок: {stats['total_trainings']}\n"
        f"✅ Успешных: {stats['successful']}\n"
        f"📈 Успешность: {stats['success_rate']}%\n"
        f"💰 Заработано: {stats['total_earned']} монет</blockquote>\n"
    )
    
    if minesweeper_stats:
        games_played = minesweeper_stats.get('games_played', 0)
        games_won = minesweeper_stats.get('games_won', 0)
        total_earned = minesweeper_stats.get('total_earned', 0)
        
        stats_text += (
            f"\n💣 <b>Футбольный сапёр:</b>\n"
            f"<blockquote>🎮 Игр: {games_played}\n"
            f"🏆 Побед: {games_won}\n"
            f"💰 Заработано: {total_earned} монет</blockquote>\n"
        )
    
    stats_text += "\n<i>Продолжай тренироваться для улучшения навыков!</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Рекорды", callback_data="training_records")],
        [InlineKeyboardButton(text="🔙 Назад к тренировкам", callback_data="back_to_training")]
    ])
    
    await safe_edit_message(callback, stats_text, keyboard)


async def safe_edit_message(
    callback: CallbackQuery, 
    text: str, 
    reply_markup=None, 
    parse_mode="HTML",
    disable_web_page_preview=True
):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        return True
    except Exception as e:
        error_type = type(e).__name__
        
        # Обработка специфических ошибок
        if "message is not modified" in str(e):
            # Сообщение не изменилось - это не критическая ошибка
            return True
        elif "message to edit not found" in str(e):
            # Сообщение было удалено - пытаемся отправить новое
            try:
                await callback.message.answer(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                return True
            except Exception as send_error:
                print(f"Failed to send new message: {send_error}")
                return False
        elif "message can't be edited" in str(e):
            # Сообщение нельзя редактировать (например, слишком старое)
            try:
                await callback.message.answer(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                return True
            except Exception as send_error:
                print(f"Failed to send new message: {send_error}")
                return False
        else:
            # Другие ошибки - логируем и пытаемся отправить новое сообщение
            print(f"Error editing message ({error_type}): {e}")
            try:
                await callback.message.answer(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                return True
            except Exception as send_error:
                print(f"Failed to send new message: {send_error}")
                return False
            
async def handle_training_failure(callback: CallbackQuery, state: FSMContext, reason: str):
    """Обработка неудачного завершения тренировки"""
    state_data = await state.get_data()
    user_id = callback.from_user.id
    drill_id = state_data.get('drill_id')
    
    # Определяем награду за усилия в зависимости от типа тренировки
    if drill_id == 'minesweeper':
        # Для сапёра награда уже начислена поэтапно
        effort_reward = state_data.get('current_reward', 0)
        # НО убедимся, что награда начислена
        if effort_reward > 0:
            await update_user_balance(user_id, effort_reward)
    else:
        # Для других тренировок - минимальная награда
        potential_reward = state_data.get('potential_reward', 150)
        effort_reward = max(10, potential_reward // 3)
        
        # Начисляем награду за усилия
        await update_user_balance(user_id, effort_reward)
        
        # Сохраняем результат тренировки
        await save_training_result(
            user_id=user_id,
            drill_type=drill_id,
            success=False,
            reward_earned=effort_reward,
            level=1
        )
    
    # Получаем ОБНОВЛЕННУЮ информацию о пользователе
    user_info = await get_user_by_id(user_id)
    coach_phrase = random.choice(COACH_PHRASES['failure'])
    
    # Создаем дополнительное сообщение в зависимости от типа тренировки
    additional_info = ""
    
    if drill_id == 'memory_challenge':
        current_step = state_data.get('memory_current_step', 0)
        sequence_length = len(state_data.get('memory_sequence', []))
        additional_info = f"\n📊 Пройдено шагов: {current_step}/{sequence_length}"
        
    elif drill_id == 'dribbling_challenge':
        round_num = state_data.get('dribble_round', 1)
        defenders_beaten = round_num - 1  # -1 потому что текущий раунд не завершен
        additional_info = f"\n🛡️ Обведено защитников: {defenders_beaten}"
        
        # Проверяем, может быть это все равно рекорд?
        if defenders_beaten > 0:
            username = user_info.get('username', callback.from_user.first_name)
            is_new_record = await check_and_update_dribbling_record(
                user_id, username, defenders_beaten
            )
            if is_new_record:
                additional_info += "\n🎉 Новый рекорд! Ты в топ-10!"
                
    elif drill_id == 'minesweeper':
        revealed_positions = state_data.get('revealed_positions', [])
        safe_positions_count = len([pos for pos in revealed_positions if pos != state_data.get('mine_position')])
        additional_info = f"\n✅ Открыто безопасных клеток: {safe_positions_count}/8"

    # Создаем клавиатуру в зависимости от типа тренировки
    if drill_id == 'minesweeper':
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 Играть снова", callback_data="start_drill:minesweeper")],
            [InlineKeyboardButton(text="💪 Другое упражнение", callback_data="open_training")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💪 Другое упражнение", callback_data="open_training")],
            [InlineKeyboardButton(text="🏆 Рекорды", callback_data="training_records")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])

    await safe_edit_message(
        callback,
        f"😢 <b>ТРЕНИРОВКА НЕ УДАЛАСЬ</b>\n\n"
        f"👨‍🏫 <i>\"{coach_phrase}\"</i>\n\n"
        f"❌ <b>Причина:</b> {reason}"
        f"{additional_info}\n\n"
        f"💰 <b>За усилия:</b> +{effort_reward} монет\n"
        f"🏦 <b>Текущий баланс:</b> {user_info['balance']} монет\n\n"  # Используем обновленный баланс
        f"<i>Не сдавайся! Практика ведёт к совершенству!</i>",
        keyboard
    )
    
    await state.clear()

# Добавьте эти обработчики в конец файла, после всех функций

@router.callback_query(F.data == "training_stats")
async def handle_training_stats(callback: CallbackQuery):
    """Обработчик кнопки статистики тренировок"""
    await show_training_stats(callback)

@router.callback_query(F.data == "back_to_training")
async def back_to_training_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад к тренировкам'"""
    await start_football_training(callback, state)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' в главное меню"""
    from handlers.main_menu import main_menu  # Импортируем главное меню
    await state.clear()
    await main_menu(callback.message)

@router.callback_query(F.data == "cooldown_info")
async def show_cooldown_info(callback: CallbackQuery):
    """Показать информацию о кд тренировок"""
    await callback.answer(
        "⏳ Это упражнение ещё на перезарядке! Попробуй позже или выбери другое.",
        show_alert=True
    )

@router.callback_query(F.data == "mine_ignored")
async def handle_mine_ignored(callback: CallbackQuery):
    """Обработчик для игнорирования нажатий на открытые клетки сапёра"""
    await callback.answer("Эта клетка уже открыта!", show_alert=False)