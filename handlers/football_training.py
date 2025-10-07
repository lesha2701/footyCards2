from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
from datetime import datetime, timedelta
import re

from db.user_queries import get_user_by_id, update_user_balance, update_user_trophies
from db.game_queries import save_training_result, get_training_stats, check_training_cooldown

router = Router()

class FootballTrainingStates(StatesGroup):
    choosing_drill = State()
    memory_challenge = State()
    memory_challenge_playing = State()
    dribbling_challenge = State()

# Тренировочные упражнения с наградами
TRAINING_DRILLS = {
    'memory_challenge': {
        'name': '🧠 Футбольная память',
        'description': 'Запомни последовательность и повтори её',
        'reward': 150,  # Фиксированная награда
        'cooldown': timedelta(minutes=10)
    },
    'dribbling_challenge': {
        'name': '🌀 Обводка соперников',
        'description': 'Проведи мяч мимо защитников',
        'reward': 150,
        'cooldown': timedelta(minutes=10)
    }
}

# Футбольные фразы тренера
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
    ]
}

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except:
        pass

async def show_training_stats(callback: CallbackQuery):
    """Показать статистику тренировок"""
    user_id = callback.from_user.id
    stats = await get_training_stats(user_id)
    
    stats_text = (
        f"📊 <b>Статистика Тренировок</b>\n\n"
        f"<blockquote>🎯 Всего тренировок: {stats['total_trainings']}\n"
        f"✅ Успешных: {stats['successful']}\n"
        f"📈 Успешность: {stats['success_rate']}%\n"
        f"💰 Заработано: {stats['total_earned']} монет</blockquote>\n\n"
        f"<i>Продолжай тренироваться для улучшения навыков!</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к тренировкам", callback_data="back_to_training")]
    ])
    
    await safe_edit_message(callback, stats_text, keyboard)

@router.callback_query(F.data == "training_stats")
async def handle_training_stats(callback: CallbackQuery):
    """Обработчик кнопки статистики тренировок"""
    await show_training_stats(callback)

@router.callback_query(F.data == "back_to_training")
async def back_to_training(callback: CallbackQuery, state: FSMContext):
    """Возврат к тренировкам из статистики"""
    await start_football_training(callback, state)

@router.callback_query(F.data == "open_training")
async def start_football_training(callback: CallbackQuery, state: FSMContext):
    """Начало футбольных тренировок"""
    user_id = callback.from_user.id
    user_info = await get_user_by_id(user_id)
    
    coach_phrase = random.choice(COACH_PHRASES['welcome'])
    
    # Создаем кнопки упражнений
    drill_buttons = []
    for drill_id, drill_info in TRAINING_DRILLS.items():
        # Проверяем кд для каждого упражнения
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
    
    # Добавляем кнопку статистики и назад
    drill_buttons.append([
        InlineKeyboardButton(text="📊 Статистика", callback_data="training_stats"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=drill_buttons)
    
    await safe_edit_message(
        callback,
        f"⚽ <b>ФУТБОЛЬНЫЕ ТРЕНИРОВКИ</b>\n\n"
        f"👨‍🏫 <i>\"{coach_phrase}\"</i>\n\n"
        f"💪 <b>Зарабатывай монеты, улучшай навыки!</b>\n\n"
        f"🎯 <b>Доступные упражнения:</b>\n"
        f"<blockquote>🧠 Футбольная память - 120 монет\n"
        f"🌀 Обводка соперников - 150 монет</blockquote>\n\n"
        f"💰 <b>Ваш баланс:</b> {user_info['balance']} монет\n\n"
        f"<i>Выберите упражнение для тренировки:</i>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.choosing_drill)

@router.callback_query(F.data.startswith("start_drill:"))
async def start_drill(callback: CallbackQuery, state: FSMContext):
    """Начало выполнения упражнения"""
    drill_id = callback.data.split(":")[1]
    
    await state.update_data(
        drill_id=drill_id,
        potential_reward=TRAINING_DRILLS[drill_id]['reward']
    )
    
    if drill_id == 'memory_challenge':
        await start_memory_challenge(callback, state)
    elif drill_id == 'dribbling_challenge':
        await start_dribbling_challenge(callback, state)

# 1. Упражнение: Футбольная память (улучшенная версия)
async def start_memory_challenge(callback: CallbackQuery, state: FSMContext):
    """Упражнение на футбольную память"""
    # Создаем случайную последовательность из 4 emoji
    football_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    sequence = random.sample(football_emojis, 4)
    
    await state.update_data(
        memory_sequence=sequence,
        memory_current_step=0,
        memory_start_time=datetime.now()
    )
    
    instruction_phrase = random.choice(COACH_PHRASES['memory_instructions'])
    
    # Показываем последовательность для запоминания
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Начать тест", callback_data="memory_start_test")]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b>\n\n"
        f"🎯 <b>Задание:</b> Запомни последовательность из 4 элементов и повтори её!\n"
        f"💰 <b>Награда:</b> 120 монет\n\n"
        f"👨‍🏫 <i>\"{instruction_phrase}\"</i>\n\n"
        f"<b>Запомни последовательность:</b>\n"
        f"{' → '.join(sequence)}\n\n"
        f"<i>У тебя есть 10 секунд на запоминание. Нажми 'Начать тест' когда будешь готов!</i>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.memory_challenge)

@router.callback_query(F.data == "memory_start_test", FootballTrainingStates.memory_challenge)
async def start_memory_test(callback: CallbackQuery, state: FSMContext):
    """Начало теста памяти"""
    state_data = await state.get_data()
    sequence = state_data['memory_sequence']
    
    # Создаем 6 кнопок с разными emoji (одна правильная)
    all_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    wrong_emojis = [e for e in all_emojis if e != sequence[0]]
    random.shuffle(wrong_emojis)
    
    # Берем 5 неправильных emoji
    options = [sequence[0]] + wrong_emojis[:5]
    random.shuffle(options)
    
    buttons = []
    for emoji in options:
        is_correct = 1 if emoji == sequence[0] else 0
        buttons.append(InlineKeyboardButton(
            text=emoji, 
            callback_data=f"memory_guess:{is_correct}"
        ))
    
    # Разбиваем на 2 строки по 3 кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:3],
        buttons[3:]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b> | Шаг 1/4\n\n"
        f"⏰ <b>Время началось!</b> Вспоминай последовательность!\n\n"
        f"<b>Какой был первый элемент?</b>",
        keyboard
    )
    
    await state.set_state(FootballTrainingStates.memory_challenge_playing)

@router.callback_query(F.data.startswith("memory_guess:"), FootballTrainingStates.memory_challenge_playing)
async def handle_memory_guess(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора в тесте памяти"""
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
        
        # Бонус за скорость (чем быстрее, тем больше бонус)
        time_bonus = max(0, int(30 - time_taken))
        total_reward = state_data['potential_reward'] + time_bonus
        
        achievement = f"Отличная память! Время: {time_taken:.1f}с!"
        if time_bonus > 0:
            achievement += f" +{time_bonus} монет за скорость! ⚡"
            
        await handle_training_success(callback, state, total_reward, achievement)
        return
    
    # Следующий шаг
    next_emoji = sequence[current_step]
    all_emojis = ["⚽", "🥅", "👟", "🏆", "🎯", "🧤", "⭐", "👕", "🩳", "🥾"]
    wrong_emojis = [e for e in all_emojis if e != next_emoji]
    random.shuffle(wrong_emojis)
    
    # Берем 5 неправильных emoji
    options = [next_emoji] + wrong_emojis[:5]
    random.shuffle(options)
    
    buttons = []
    for emoji in options:
        is_correct = 1 if emoji == next_emoji else 0
        buttons.append(InlineKeyboardButton(
            text=emoji, 
            callback_data=f"memory_guess:{is_correct}"
        ))
    
    # Разбиваем на 2 строки по 3 кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:3],
        buttons[3:]
    ])
    
    await safe_edit_message(
        callback,
        f"🧠 <b>ФУТБОЛЬНАЯ ПАМЯТЬ</b> | Шаг {current_step + 1}/4\n\n"
        f"👨‍🏫 <i>\"{success_phrase}\"</i>\n\n"
        f"<b>Какой был следующий элемент?</b>",
        keyboard
    )

# 2. Упражнение: Обводка соперников
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
        total_reward = current_reward + 15  # +15 за текущий успешный раунд
        await handle_training_success(
            callback, state, total_reward, 
            f"Обвёл {round_num} защитников! Но тебя перехватили."
        )
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

async def handle_training_success(callback: CallbackQuery, state: FSMContext, reward: int, achievement: str):
    """Обработка успешного завершения тренировки"""
    state_data = await state.get_data()
    user_id = callback.from_user.id
    drill_id = state_data['drill_id']
    
    # Начисляем награду
    await update_user_balance(user_id, reward)
    
    # Сохраняем результат тренировки
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
        [InlineKeyboardButton(text="📊 Статистика", callback_data="training_stats")],
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

async def handle_training_failure(callback: CallbackQuery, state: FSMContext, reason: str):
    """Обработка неудачного завершения тренировки"""
    state_data = await state.get_data()
    user_id = callback.from_user.id
    drill_id = state_data['drill_id']
    
    # Минимальная награда за усилия
    effort_reward = max(10, state_data['potential_reward'] // 3)
    await update_user_balance(user_id, effort_reward)
    
    # Сохраняем результат тренировки
    await save_training_result(
        user_id=user_id,
        drill_type=drill_id,
        success=False,
        reward_earned=effort_reward,
        level=1
    )
    
    user_info = await get_user_by_id(user_id)
    coach_phrase = random.choice(COACH_PHRASES['failure'])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💪 Другое упражнение", callback_data="open_training")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
    
    await safe_edit_message(
        callback,
        f"😢 <b>ТРЕНИРОВКА НЕ УДАЛАСЬ</b>\n\n"
        f"👨‍🏫 <i>\"{coach_phrase}\"</i>\n\n"
        f"❌ <b>Причина:</b> {reason}\n"
        f"💰 <b>За усилия:</b> +{effort_reward} монет\n"
        f"🏦 <b>Баланс:</b> {user_info['balance']} монет\n\n"
        f"<i>Не сдавайся! Практика ведёт к совершенству!</i>",
        keyboard
    )
    
    await state.clear()

@router.callback_query(F.data == "cooldown_info")
async def show_cooldown_info(callback: CallbackQuery):
    """Показать информацию о кд тренировок"""
    await callback.answer(
        "⏳ Это упражнение ещё на перезарядке! Попробуй позже или выбери другое.",
        show_alert=True
    )