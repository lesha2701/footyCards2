from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from db.user_queries import (
    get_user_penalty_stats, update_user_penalty_rating, can_play_penalty_today,
    update_user_balance, update_daily_penalty_games, create_penalty_invitation,
    get_penalty_invitation, update_penalty_invitation_status, get_user_by_id,
    create_penalty_match_v2, get_active_penalty_match_v2, update_penalty_match_actions_v2,
    process_penalty_match_v2, get_penalty_match_v2_by_id, cleanup_expired_matches_v2,
    get_card_by_user_card_id, get_user_cards_for_market, toggle_shadow_mode, save_penalty_result_v2
)
from db.pool import get_db_pool

router = Router()

# Состояния для новой системы пенальти
class PenaltyV2States(StatesGroup):
    main_menu = State()
    vs_bot_confirmation = State()
    vs_player_menu = State()
    waiting_opponent_username = State()
    selecting_card = State()
    selecting_actions = State()
    waiting_opponent_actions = State()
    viewing_results = State()

# Конфигурация
PENALTY_V2_CONFIG = {
    'kicks_count': 5,
    'time_limit_minutes': 5,
    # Рейтинг для игр с игроком
    'rating_change_win': 30,
    'rating_change_lose': -15,
    'rating_change_draw': 5,  # +5 за ничью
    # Рейтинг для игр с ботом (в 3 раза меньше)
    'rating_bot_multiplier': 0.33,
    # Монеты для игр с игроком
    'coins_win': 150,  # Увеличили с 100 до 150
    'coins_lose': 15,  # Увеличили с 10 до 15
    'coins_draw': 75,  # Увеличили с 50 до 75
    # Монеты для игр с ботом
    'coins_bot_win': 50,
    'coins_bot_lose': 5,
    'coins_bot_draw': 25
}

# Клавиатуры
def create_penalty_v2_main_menu(user_id: int = None, is_shadow_mode: bool = False) -> InlineKeyboardMarkup:
    """Главное меню с кнопкой Уйти в тень"""
    buttons = [
        [InlineKeyboardButton(text="🤖 Играть против бота", callback_data="penalty_v2_vs_bot")],
        [InlineKeyboardButton(text="👥 Играть против игрока", callback_data="penalty_v2_vs_player")],
        [InlineKeyboardButton(text="📚 Правила игры", callback_data="penalty_v2_rules")],
    ]
    
    # Кнопка Уйти в тень / Вернуться
    shadow_text = "👻 Вернуться" if is_shadow_mode else "👻 Уйти в тень"
    shadow_data = "penalty_v2_shadow_off" if is_shadow_mode else "penalty_v2_shadow_on"
    buttons.append([InlineKeyboardButton(text=shadow_text, callback_data=shadow_data)])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_kick_selection_keyboard(round_num: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Влево", callback_data=f"penalty_v2_kick:{round_num}:left"),
            InlineKeyboardButton(text="⬆️ Центр", callback_data=f"penalty_v2_kick:{round_num}:center"),
            InlineKeyboardButton(text="➡️ Вправо", callback_data=f"penalty_v2_kick:{round_num}:right")
        ]
    ])

def create_defense_selection_keyboard(round_num: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Влево", callback_data=f"penalty_v2_defense:{round_num}:left"),
            InlineKeyboardButton(text="⬆️ Центр", callback_data=f"penalty_v2_defense:{round_num}:center"),
            InlineKeyboardButton(text="➡️ Вправо", callback_data=f"penalty_v2_defense:{round_num}:right")
        ]
    ])

def create_actions_navigation_keyboard(current_round: int, total_rounds: int, completed_kicks: dict, completed_defenses: dict) -> InlineKeyboardMarkup:
    buttons = []
    
    # Кнопки навигации по раундам
    nav_buttons = []
    if current_round > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"penalty_v2_round:{current_round-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{current_round}/{total_rounds}", callback_data="noop"))
    
    if current_round < total_rounds:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"penalty_v2_round:{current_round+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопка завершения выбора
    all_completed = len(completed_kicks) == total_rounds and len(completed_defenses) == total_rounds
    if all_completed:
        buttons.append([InlineKeyboardButton(text="✅ Завершить выбор", callback_data="penalty_v2_finish_actions")])
    
    # Убрана кнопка "Назад" из процесса выбора действий
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_rules_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для меню правил"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="penalty_v2_main_menu")]
    ])

def create_active_match_confirmation() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения отмены активного матча"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, начать новый", callback_data="penalty_v2_confirm_new_match"),
            InlineKeyboardButton(text="❌ Нет, продолжить текущий", callback_data="penalty_v2_cancel_new_match")
        ]
    ])

@router.callback_query(F.data == "penalty_mode")
async def penalty_v2_main_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню новой системы пенальти"""
    await cleanup_expired_matches_v2()
    
    user_id = callback.from_user.id
    user_data = await get_user_by_id(user_id)
    stats = await get_user_penalty_stats(user_id)
    
    if not stats:
        stats = {
            'penalty_rating': 0,
            'total_games': 0,
            'wins': 0,
            'losses': 0,
            'total_coins_earned': 0
        }
    
    win_rate = (stats['wins'] / stats['total_games'] * 100) if stats['total_games'] > 0 else 0
    
    shadow_status = "👻 <b>Режим невидимки:</b> ВКЛЮЧЕН\n" if user_data.get('is_shadow_mode') else ""
    
    text = (
        f"🎯 <b>Пенальти</b>\n\n"
        f"📊 <b>Ваша статистика:</b>\n"
        f"<blockquote>🏆 Рейтинг: {stats['penalty_rating']}\n"
        f"🎮 Игр: {stats['total_games']}\n"
        f"✅ Побед: {stats['wins']}\n"
        f"❌ Поражения: {stats['losses']}\n"
        f"📈 Винрейт: {win_rate:.1f}%</blockquote>\n\n"
        f"⚡ <b>Если вы играете впервые, то советуем ознакомиться с правилами!</b>\n\n"
        f"<i>Выберите тип игры:</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=create_penalty_v2_main_menu(user_id, user_data.get('is_shadow_mode', False)))
    await state.set_state(PenaltyV2States.main_menu)

@router.callback_query(F.data == "penalty_v2_vs_bot")
async def penalty_v2_vs_bot(callback: CallbackQuery, state: FSMContext):
    """Начало игры против бота v2"""
    user_id = callback.from_user.id
    
    # Проверяем активный матч
    active_match = await get_active_penalty_match_v2(user_id)
    if active_match:
        # Сохраняем информацию о попытке начать новый матч
        await state.update_data(pending_new_match=True)
        
        text = (
            "⚠️ <b>У вас есть активный матч!</b>\n\n"
            "Вы уже участвуете в незавершенном матче. Если вы начнете новый матч, "
            "текущий будет автоматически засчитан как поражение.\n\n"
            "Вы уверены, что хотите начать новый матч?"
        )
        
        await callback.message.edit_text(text, reply_markup=create_active_match_confirmation())
        return
    
    # Проверяем лимит игр
    can_play, message = await can_play_penalty_today(user_id)
    if not can_play:
        await callback.answer(message, show_alert=True)
        return
    
    text = (
        "🤖 <b>Игра против бота</b>\n\n"
        "🎯 <b>Правила:</b>\n"
        "<blockquote>• Определите 5 ударов и 5 защит заранее\n"
        "• Бот случайно выберет свои действия\n"
        "• Результат вычисляется автоматически\n"
        "• Лимит: 3 минуты на выбор действий</blockquote>\n\n"
        "<b>Начинаем матч?</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать", callback_data="penalty_v2_start_bot")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="penalty_v2_main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PenaltyV2States.vs_bot_confirmation)

@router.callback_query(F.data == "penalty_v2_confirm_new_match")
async def penalty_v2_confirm_new_match(callback: CallbackQuery, state: FSMContext):
    """Подтверждение начала нового матча при наличии активного"""
    user_id = callback.from_user.id
    
    # Получаем активный матч
    active_match = await get_active_penalty_match_v2(user_id)
    if active_match:
        # Помечаем активный матч как завершенный с поражением для пользователя
        await process_abandoned_match(active_match, user_id, callback.bot)
    
    # Очищаем состояние и переходим к выбору типа игры
    await state.clear()
    await penalty_v2_vs_bot(callback, state)

@router.callback_query(F.data == "penalty_v2_cancel_new_match")
async def penalty_v2_cancel_new_match(callback: CallbackQuery, state: FSMContext):
    """Отмена начала нового матча"""
    await state.clear()
    await penalty_v2_main_menu(callback, state)

async def process_abandoned_match(match: dict, user_id: int, bot: Bot = None):
    """Обрабатывает брошенный матч как поражение"""
    try:
        # Определяем, кто является оппонентом
        if match['player1_id'] == user_id:
            winner_id = match['player2_id']
            loser_id = user_id
            player1_score = 0
            player2_score = 5
            opponent_id = match['player2_id']
        else:
            winner_id = match['player1_id']
            loser_id = user_id
            player1_score = 5
            player2_score = 0
            opponent_id = match['player1_id']
        
        # Определяем награды в зависимости от типа матча
        if match['is_vs_bot']:
            rating_change = int(PENALTY_V2_CONFIG['rating_change_lose'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
            coins_earned = PENALTY_V2_CONFIG['coins_bot_lose']
        else:
            rating_change = PENALTY_V2_CONFIG['rating_change_lose']
            coins_earned = PENALTY_V2_CONFIG['coins_lose']
        
        # Обновляем статистику для проигравшего
        if rating_change != 0:
            await update_user_penalty_rating(loser_id, rating_change)
        
        if coins_earned > 0:
            await update_user_balance(loser_id, coins_earned)
        
        await update_daily_penalty_games(loser_id)
        
        # Помечаем матч как завершенный
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
            UPDATE penalty_matches_v2 
            SET match_state = 'finished', winner_id = $1, completed_at = NOW(),
                player1_score = $2, player2_score = $3
            WHERE id = $4
            """, winner_id, player1_score, player2_score, match['id'])
        
        # СОХРАНЯЕМ РЕЗУЛЬТАТ В БАЗУ ДАННЫХ
        result_data = {
            'player1_score': player1_score,
            'player2_score': player2_score,
            'winner_id': winner_id
        }
        await save_penalty_result_v2(match, result_data, rating_change, coins_earned, user_id)
        
        # УВЕДОМЛЯЕМ ОППОНЕНТА О ПОБЕДЕ (если это PvP и бот доступен)
        if not match['is_vs_bot'] and opponent_id and bot:
            try:
                opponent_name = match['player1_username'] if opponent_id == match['player1_id'] else match['player2_username']
                await bot.send_message(
                    chat_id=opponent_id,
                    text=f"🏆 <b>Противник сдался!</b>\n\n"
                         f"Ваш оппонент покинул матч.\n"
                         f"Вам засчитана победа со счетом 5:0\n\n"
                         f"🏆 +{PENALTY_V2_CONFIG['rating_change_win']} рейтинг\n"
                         f"💰 +{PENALTY_V2_CONFIG['coins_win']} монет",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Ошибка уведомления оппонента: {e}")
            
    except Exception as e:
        print(f"Error processing abandoned match: {e}")

@router.callback_query(F.data == "penalty_v2_start_bot")
async def penalty_v2_start_bot(callback: CallbackQuery, state: FSMContext):
    """Запуск матча с ботом"""
    user_id = callback.from_user.id
    
    # Создаем матч с ботом
    match = await create_penalty_match_v2(user_id, is_vs_bot=True)
    await state.update_data(match_id=match['id'])
    
    # Переходим к выбору действий
    await start_actions_selection(callback, state)

@router.callback_query(F.data == "penalty_v2_vs_player")
async def penalty_v2_vs_player_menu(callback: CallbackQuery, state: FSMContext):
    """Меню игры против игрока v2"""
    user_id = callback.from_user.id
    
    # Проверяем активный матч
    active_match = await get_active_penalty_match_v2(user_id)
    if active_match:
        # Сохраняем информацию о попытке начать новый матч
        await state.update_data(pending_new_match=True)
        
        text = (
            "⚠️ <b>У вас есть активный матч!</b>\n\n"
            "Вы уже участвуете в незавершенном матче. Если вы начнете новый матч, "
            "текущий будет автоматически засчитан как поражение.\n\n"
            "Вы уверены, что хотите начать новый матч?"
        )
        
        await callback.message.edit_text(text, reply_markup=create_active_match_confirmation())
        return
    
    # Проверяем лимит игр
    can_play, message = await can_play_penalty_today(user_id)
    if not can_play:
        await callback.answer(message, show_alert=True)
        return
    
    text = (
        "👥 <b>Игра против игрока</b>\n\n"
        "🎯 <b>Правила:</b>\n"
        "<blockquote>• Оба игрока заранее выбирают действия\n"
        "• Результат вычисляется автоматически\n"
        "• Максимально честно и без задержек\n"
        "• Лимит: 3 минуты на выбор действий</blockquote>\n\n"
        "В <a href='https://t.me/FootycardChat'>нашем чате</a> вы можете найти соперника для игры\n\n"
        "<i>Выберите действие:</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Пригласить игрока", callback_data="penalty_v2_invite_player")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="penalty_v2_main_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PenaltyV2States.vs_player_menu)

@router.callback_query(F.data == "penalty_v2_shadow_on")
async def penalty_v2_enable_shadow_mode(callback: CallbackQuery, state: FSMContext):
    """Включение режима невидимки"""
    user_id = callback.from_user.id
    
    await toggle_shadow_mode(user_id, True)
    await callback.answer("👻 Режим невидимки включен! Теперь другие игроки не могут приглашать вас.", show_alert=True)
    await penalty_v2_main_menu(callback, state)

@router.callback_query(F.data == "penalty_v2_shadow_off")
async def penalty_v2_disable_shadow_mode(callback: CallbackQuery, state: FSMContext):
    """Выключение режима невидимки"""
    user_id = callback.from_user.id
    
    await toggle_shadow_mode(user_id, False)
    await callback.answer("👤 Режим невидимки выключен! Теперь другие игроки могут приглашать вас.", show_alert=True)
    await penalty_v2_main_menu(callback, state)

@router.callback_query(F.data == "penalty_v2_rules")
async def penalty_v2_show_rules(callback: CallbackQuery, state: FSMContext):
    """Показ правил игры"""
    text = (
        "📚 <b>Правила игры в Пенальти</b>\n\n"
        
        "🎯 <b>Основные принципы:</b>\n"
        "<blockquote>• Каждый матч состоит из 5 раундов\n"
        "• В каждом раунде оба игрока выполняют по одному удару\n"
        "• Побеждает игрок, забивший больше голов</blockquote>\n\n"
        
        "⚽ <b>Как играть:</b>\n"
        "<blockquote>1. <b>Выбор действий:</b> Заранее определите 5 ударов и 5 защит\n"
        "2. <b>Направления:</b> Влево ⬅️, Центр ⬆️, Вправо ➡️\n"
        "3. <b>Гол засчитывается</b>, если удар и защита в разных направлениях\n"
        "4. <b>Гол не засчитывается</b>, если удар и защита в одном направлении</blockquote>\n\n"
        
        "🎮 <b>Пример раунда:</b>\n"
        "<blockquote>• Вы бьете ⬅️ Влево\n"
        "• Оппонент защищает ➡️ Вправо\n"
        "→ <b>Результат:</b> ✅ ГОЛ!\n\n"
        
        "• Вы бьете ⬆️ Центр  \n"
        "• Оппонент защищает ⬆️ Центр\n"
        "→ <b>Результат:</b> ❌ Отбил</blockquote>\n\n"
        
        "🏆 <b>Награды за игру с ИГРОКОМ:</b>\n"
        f"<blockquote>• Победа: +{PENALTY_V2_CONFIG['rating_change_win']} рейтинг, +{PENALTY_V2_CONFIG['coins_win']} монет\n"
        f"• Ничья: +{PENALTY_V2_CONFIG['rating_change_draw']} рейтинг, +{PENALTY_V2_CONFIG['coins_draw']} монет\n"
        f"• Поражение: {PENALTY_V2_CONFIG['rating_change_lose']} рейтинг, +{PENALTY_V2_CONFIG['coins_lose']} монет</blockquote>\n\n"
        
        "🤖 <b>Награды за игру с БОТОМ:</b>\n"
        f"<blockquote>• Победа: +{int(PENALTY_V2_CONFIG['rating_change_win'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])} рейтинг, +{PENALTY_V2_CONFIG['coins_bot_win']} монет\n"
        f"• Ничья: +{int(PENALTY_V2_CONFIG['rating_change_draw'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])} рейтинг, +{PENALTY_V2_CONFIG['coins_bot_draw']} монет\n"
        f"• Поражение: {int(PENALTY_V2_CONFIG['rating_change_lose'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])} рейтинг, +{PENALTY_V2_CONFIG['coins_bot_lose']} монет</blockquote>\n\n"
        
        "⏰ <b>Лимиты:</b>\n"
        "<blockquote>• 3 минуты на выбор действий\n"
        "• 5 матча в час\n"
        "• Приглашения действуют 2 минуты</blockquote>"
    )
    
    await callback.message.edit_text(text, reply_markup=create_rules_keyboard())

async def start_actions_selection(callback: CallbackQuery, state: FSMContext):
    """Начало выбора действий"""
    state_data = await state.get_data()
    match_id = state_data.get('match_id')
    
    if not match_id:
        await callback.answer("Ошибка: матч не найден", show_alert=True)
        return
    
    # Инициализируем данные для выбора действий
    await state.update_data(
        current_round=1,
        kicks={},
        defenses={}
    )
    
    await show_actions_interface(callback, state)

async def show_actions_interface(callback: CallbackQuery, state: FSMContext):
    """Показывает интерфейс выбора действий"""
    state_data = await state.get_data()
    current_round = state_data.get('current_round', 1)
    kicks = state_data.get('kicks', {})
    defenses = state_data.get('defenses', {})
    
    current_kick = kicks.get(str(current_round))
    current_defense = defenses.get(str(current_round))
    
    text = (
        f"🎯 <b>Выбор действий - Раунд {current_round}</b>\n\n"
        f"Определите ваши действия для всех 5 раундов заранее.\n\n"
    )
    
    if current_kick:
        text += f"⚽ Удар {current_round}: {get_direction_emoji(current_kick)} {current_kick}\n"
    else:
        text += f"⚽ Удар {current_round}: ❌ не выбран\n"
    
    if current_defense:
        text += f"🧤 Защита {current_round}: {get_direction_emoji(current_defense)} {current_defense}\n"
    else:
        text += f"🧤 Защита {current_round}: ❌ не выбрана\n"
    
    text += f"\n⏰ Лимит времени: 3 минуты\n"
    
    # Создаем клавиатуру
    kick_keyboard = create_kick_selection_keyboard(current_round)
    defense_keyboard = create_defense_selection_keyboard(current_round)
    nav_keyboard = create_actions_navigation_keyboard(current_round, 5, kicks, defenses)
    
    # Комбинируем клавиатуры
    combined_keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    combined_keyboard.inline_keyboard.extend(kick_keyboard.inline_keyboard)
    combined_keyboard.inline_keyboard.extend(defense_keyboard.inline_keyboard)
    combined_keyboard.inline_keyboard.extend(nav_keyboard.inline_keyboard)
    
    try:
        await callback.message.edit_text(text, reply_markup=combined_keyboard)
    except Exception as e:
        # Игнорируем ошибку "message is not modified"
        if "message is not modified" not in str(e):
            print(f"Error editing message: {e}")
    
    await state.set_state(PenaltyV2States.selecting_actions)

@router.callback_query(F.data == "penalty_v2_invite_player")
async def penalty_v2_invite_player(callback: CallbackQuery, state: FSMContext):
    """Начало процесса приглашения игрока v2"""
    await callback.message.edit_text(
        "👤 <b>Приглашение игрока</b>\n\n"
        "Введите username или ID игрока:\n\n"
        "<i>Примеры:</i>\n"
        "• <code>@username</code>\n"
        "• <code>username</code> (без @)\n"
        "• <code>123456789</code> (ID пользователя)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="penalty_v2_vs_player")]
        ])
    )
    await state.set_state(PenaltyV2States.waiting_opponent_username)

@router.message(PenaltyV2States.waiting_opponent_username)
async def process_opponent_username_v2(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного username или ID оппонента v2"""
    identifier = message.text.strip()
    
    if not identifier:
        await message.answer("Пожалуйста, введите корректный username или ID:")
        return
    
    # Убираем @ если есть
    if identifier.startswith('@'):
        identifier = identifier[1:]
    
    # Создаем приглашение
    invitation, result_message = await create_penalty_invitation(message.from_user.id, identifier, bot)
    
    if invitation:
        text = (
            f"✅ <b>Приглашение отправлено!</b>\n\n"
            f"Игроку отправлено приглашение на матч.\n"
            f"Ожидайте подтверждения..."
        )
    else:
        text = f"❌ <b>Ошибка:</b> {result_message}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к меню", callback_data="penalty_v2_vs_player")]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()

# Обработчики принятия/отклонения приглашений для v2
@router.callback_query(F.data.startswith("accept_invite:"))
async def accept_invitation_v2(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Принятие приглашения на матч v2"""
    invitation_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    invitation = await get_penalty_invitation(invitation_id)
    
    if not invitation or invitation['invitee_id'] != user_id:
        await callback.answer("Приглашение не найдено или устарело", show_alert=True)
        return
    
    if invitation['status'] != 'pending':
        await callback.answer("Это приглашение уже обработано", show_alert=True)
        return
    
    # Проверяем лимит игр для обоих игроков
    can_play, message = await can_play_penalty_today(user_id)
    if not can_play:
        await callback.answer(message, show_alert=True)
        return
    
    can_play_inviter, message_inviter = await can_play_penalty_today(invitation['inviter_id'])
    if not can_play_inviter:
        await callback.answer("У приглашающего игрока исчерпан лимит игр", show_alert=True)
        return
    
    # Создаем матч v2
    match = await create_penalty_match_v2(invitation['inviter_id'], user_id, is_vs_bot=False)
    await update_penalty_invitation_status(invitation_id, 'accepted')
    
    # Сохраняем ID матча для текущего пользователя (приглашенного)
    await state.update_data(match_id=match['id'])
    
    await callback.message.edit_text(
        "✅ <b>Приглашение принято!</b>\n\n"
        "Матч создан. Теперь определите ваши действия:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Начать выбор действий", callback_data="penalty_v2_start_after_invite")]
        ])
    )
    
    # Уведомляем приглашающего о принятии приглашения
    try:
        inviter_message = (
            f"✅ <b>Игрок принял ваше приглашение!</b>\n\n"
            f"Игрок {callback.from_user.username or callback.from_user.first_name} принял ваше приглашение на матч.\n\n"
            f"Матч создан. Теперь определите ваши действия:"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Начать выбор действий", callback_data=f"penalty_v2_start_inviter:{match['id']}")]
        ])
        
        await bot.send_message(
            chat_id=invitation['inviter_id'],
            text=inviter_message,
            reply_markup=keyboard
        )
        
    except Exception as e:
        print(f"Ошибка уведомления приглашающего: {e}")

@router.callback_query(F.data.startswith("penalty_v2_start_inviter:"))
async def penalty_v2_start_as_inviter(callback: CallbackQuery, state: FSMContext):
    """Начало выбора действий для приглашающего"""
    match_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    # Проверяем, что матч существует и пользователь является участником
    match = await get_penalty_match_v2_by_id(match_id)
    if not match or match['player1_id'] != user_id:
        await callback.answer("Матч не найден или устарел", show_alert=True)
        return
    
    # Сохраняем match_id в состоянии
    await state.update_data(match_id=match_id)
    
    # Переходим к выбору действий
    await start_actions_selection(callback, state)

@router.callback_query(F.data == "penalty_v2_start_after_invite")
async def penalty_v2_start_after_invite(callback: CallbackQuery, state: FSMContext):
    """Начало выбора действий после принятия приглашения"""
    await start_actions_selection(callback, state)

@router.callback_query(F.data.startswith("decline_invite:"))
async def decline_invitation_v2(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отклонение приглашения на матч v2"""
    invitation_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    invitation = await get_penalty_invitation(invitation_id)
    
    if invitation and invitation['invitee_id'] == user_id and invitation['status'] == 'pending':
        await update_penalty_invitation_status(invitation_id, 'declined')
        
        # Уведомляем приглашающего об отклонении
        try:
            invitee_name = callback.from_user.username or callback.from_user.first_name
            await bot.send_message(
                chat_id=invitation['inviter_id'],
                text=f"❌ <b>Приглашение отклонено</b>\n\n"
                     f"Игрок <b>{invitee_name}</b> отклонил ваше приглашение на матч в пенальти.",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка уведомления приглашающего об отклонении: {e}")
    
    await callback.message.edit_text(
        "❌ <b>Приглашение отклонено</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="penalty_v2_main_menu")]
        ])
    )

def get_direction_emoji(direction: str) -> str:
    """Возвращает эмодзи для направления"""
    emojis = {
        'left': '⬅️',
        'center': '⬆️',
        'right': '➡️'
    }
    return emojis.get(direction, '❓')

@router.callback_query(F.data.startswith("penalty_v2_kick:"))
async def penalty_v2_select_kick(callback: CallbackQuery, state: FSMContext):
    """Выбор удара"""
    try:
        parts = callback.data.split(":")
        round_num = parts[1]
        direction = parts[2]
        
        state_data = await state.get_data()
        kicks = state_data.get('kicks', {})
        kicks[round_num] = direction
        
        await state.update_data(kicks=kicks)
        await show_actions_interface(callback, state)
    except Exception as e:
        if "message is not modified" not in str(e):
            print(f"Error in penalty_v2_select_kick: {e}")

@router.callback_query(F.data.startswith("penalty_v2_defense:"))
async def penalty_v2_select_defense(callback: CallbackQuery, state: FSMContext):
    """Выбор защиты"""
    try:
        parts = callback.data.split(":")
        round_num = parts[1]
        direction = parts[2]
        
        state_data = await state.get_data()
        defenses = state_data.get('defenses', {})
        defenses[round_num] = direction
        
        await state.update_data(defenses=defenses)
        await show_actions_interface(callback, state)
    except Exception as e:
        if "message is not modified" not in str(e):
            print(f"Error in penalty_v2_select_defense: {e}")

@router.callback_query(F.data.startswith("penalty_v2_round:"))
async def penalty_v2_change_round(callback: CallbackQuery, state: FSMContext):
    """Смена раунда"""
    round_num = int(callback.data.split(":")[1])
    await state.update_data(current_round=round_num)
    await show_actions_interface(callback, state)

@router.callback_query(F.data == "penalty_v2_finish_actions")
async def penalty_v2_finish_actions(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора действий"""
    user_id = callback.from_user.id
    state_data = await state.get_data()
    
    match_id = state_data.get('match_id')
    kicks = state_data.get('kicks', {})
    defenses = state_data.get('defenses', {})
    
    if not match_id:
        await callback.answer("Ошибка: матч не найден", show_alert=True)
        return
    
    # Проверяем, что выбраны все действия
    if len(kicks) != 5 or len(defenses) != 5:
        await callback.answer("Нужно выбрать все 5 ударов и 5 защит!", show_alert=True)
        return
    
    # Сохраняем действия в БД
    await update_penalty_match_actions_v2(match_id, user_id, kicks, defenses)
    
    # Получаем обновленную информацию о матче
    match = await get_penalty_match_v2_by_id(match_id)
    
    if not match:
        await callback.answer("Ошибка: матч не найден", show_alert=True)
        return
    
    if match['is_vs_bot']:
        # Против бота - сразу обрабатываем матч
        await process_and_show_results_v2(
            callback.bot,
            callback.message.chat.id,
            callback.message.message_id,
            state,
            match_id,
            user_id
        )
    else:
        # Против игрока - проверяем, готов ли уже оппонент
        if match['player1_kicks'] and match['player1_defenses'] and \
           match['player2_kicks'] and match['player2_defenses']:
            # Оба игрока готовы - сразу обрабатываем
            await process_and_show_results_v2(
                callback.bot,
                callback.message.chat.id,
                callback.message.message_id,
                state,
                match_id,
                user_id
            )
        else:
            # Ждем оппонента (С ТАЙМЕРОМ)
            match_created = match['created_at']
            if match_created.tzinfo is None:
                match_created = match_created.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            time_passed = now - match_created
            time_left = timedelta(minutes=3) - time_passed
            
            minutes_left = int(time_left.total_seconds() // 60)
            seconds_left = int(time_left.total_seconds() % 60)
            
            await callback.message.edit_text(
                f"✅ <b>Действия выбраны!</b>\n\n"
                f"Ожидаем, пока оппонент выберет свои действия...\n\n"
                f"⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}\n"
                f"<i>Автообновление каждые 10 секунд</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить", callback_data="penalty_v2_check_opponent")]
                ])
            )
            await state.set_state(PenaltyV2States.waiting_opponent_actions)
            
            # Запускаем автообновление
            asyncio.create_task(auto_check_opponent(callback, state, match_id))

async def auto_check_opponent(callback: CallbackQuery, state: FSMContext, match_id: int):
    """Автопроверка готовности оппонента с таймером"""
    user_id = callback.from_user.id
    bot = callback.bot
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    
    # Получаем время создания матча
    match = await get_penalty_match_v2_by_id(match_id)
    if not match:
        return
    
    match_created = match['created_at']
    if match_created.tzinfo is None:
        match_created = match_created.replace(tzinfo=timezone.utc)
    
    time_limit = timedelta(minutes=3)
    
    for i in range(18):  # 3 минуты с проверками каждые 10 секунд
        await asyncio.sleep(10)
        
        # Получаем актуальную информацию о матче
        match = await get_penalty_match_v2_by_id(match_id)
        if not match:
            break
        
        # Если матч уже завершен, показываем результаты
        if match['match_state'] == 'finished':
            print(f"DEBUG: Матч {match_id} завершен в auto_check_opponent")
            await show_results_for_finished_match(bot, chat_id, message_id, state, match, user_id)
            return
        
        # Проверяем готовность матча
        if match['player1_kicks'] and match['player1_defenses'] and \
           match['player2_kicks'] and match['player2_defenses']:
            # Матч готов - обрабатываем
            await process_and_show_results_v2(bot, chat_id, message_id, state, match_id, user_id)
            return
        
        # Рассчитываем оставшееся время
        now = datetime.now(timezone.utc)
        time_passed = now - match_created
        time_left = time_limit - time_passed
        
        if time_left.total_seconds() <= 0:
            # Время вышло - завершаем матч с победой ожидающего игрока
            await process_timeout_match(match_id, user_id, bot, chat_id, message_id, state)
            return
        
        # Обновляем сообщение о ожидании С ТАЙМЕРОМ
        minutes_left = int(time_left.total_seconds() // 60)
        seconds_left = int(time_left.total_seconds() % 60)
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ <b>Действия выбраны!</b>\n\n"
                     f"Ожидаем, пока оппонент выберет свои действия...\n\n"
                     f"⏰ Осталось времени: {minutes_left:02d}:{seconds_left:02d}\n"
                     f"<i>Автообновление каждые 10 секунд</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить", callback_data="penalty_v2_check_opponent")]
                ]),
                parse_mode="HTML"
            )
        except Exception as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" not in str(e):
                print(f"Error updating waiting message: {e}")
    
    # Если время вышло (резервный вариант)
    await process_timeout_match(match_id, user_id, bot, chat_id, message_id, state)

async def process_timeout_match(match_id: int, user_id: int, bot: Bot, chat_id: int, message_id: int, state: FSMContext):
    """Обрабатывает матч при истечении времени"""
    match = await get_penalty_match_v2_by_id(match_id)
    if not match:
        return
    
    # Определяем кто ожидал, а кто не успел
    if match['player1_kicks'] and match['player1_defenses']:
        # Игрок 1 готов, игрок 2 не успел
        winner_id = match['player1_id']
        loser_id = match['player2_id']
        player1_score = 5
        player2_score = 0
        waiting_user_id = match['player1_id']
    else:
        # Игрок 2 готов, игрок 1 не успел
        winner_id = match['player2_id']
        loser_id = match['player1_id']
        player1_score = 0
        player2_score = 5
        waiting_user_id = match['player2_id']
    
    # Обновляем матч в БД
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE penalty_matches_v2 
        SET match_state = 'finished', winner_id = $1, completed_at = NOW(),
            player1_score = $2, player2_score = $3
        WHERE id = $4
        """, winner_id, player1_score, player2_score, match_id)
    
    # Создаем результат
    result_data = {
        'player1_score': player1_score,
        'player2_score': player2_score,
        'winner_id': winner_id
    }
    
    # Награды для победителя
    winner_rating_change = PENALTY_V2_CONFIG['rating_change_win']
    winner_coins_earned = PENALTY_V2_CONFIG['coins_win']
    
    # Награды для проигравшего
    loser_rating_change = PENALTY_V2_CONFIG['rating_change_lose']
    loser_coins_earned = PENALTY_V2_CONFIG['coins_lose']
    
    # Сохраняем результаты для обоих игроков
    await save_penalty_result_v2(match, result_data, winner_rating_change, winner_coins_earned, winner_id)
    
    # Уведомляем проигравшего о таймауте
    try:
        
        await bot.send_message(
            chat_id=loser_id,
            text="⏰ <b>Время вышло!</b>\n\n"
                 "Вы не успели выбрать действия за отведенное время.\n"
                 "Матч засчитан как поражение.\n\n"
                 f"📊 Счет: 0:5\n"
                 f"🏆 Рейтинг: {loser_rating_change}\n"
                 f"💰 Монеты: +{loser_coins_earned}",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка уведомления проигравшего: {e}")
    
    # Показываем результаты ожидающему игроку
    if user_id == waiting_user_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="🏆 <b>Победа по таймауту!</b>\n\n"
                     "Оппонент не успел выбрать действия за отведенное время.\n"
                     "Вам засчитана победа!\n\n"
                     f"📊 Счет: 5:0\n"
                     f"🏆 Рейтинг: +{winner_rating_change}\n"
                     f"💰 Монеты: +{winner_coins_earned}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Сыграть еще", callback_data="penalty_v2_main_menu")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                ]),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error editing timeout message: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text="🏆 <b>Победа по таймауту!</b>\n\n"
                     "Оппонент не успел выбрать действия за отведенное время.\n"
                     "Вам засчитана победа!\n\n"
                     f"📊 Счет: 5:0\n"
                     f"🏆 Рейтинг: +{winner_rating_change}\n"
                     f"💰 Монеты: +{winner_coins_earned}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎯 Сыграть еще", callback_data="penalty_v2_main_menu")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
                ]),
                parse_mode="HTML"
            )
    
    await state.clear()

async def process_and_show_results_v2(bot: Bot, chat_id: int, message_id: int, state: FSMContext, match_id: int, user_id: int):
    """Обрабатывает матч и показывает результаты (версия для автообновления)"""
    try:
        # Получаем информацию о матче
        match = await get_penalty_match_v2_by_id(match_id)
        if not match:
            await bot.send_message(chat_id, "❌ Матч не найден")
            return
        
        # Если матч уже завершен, просто показываем результаты
        if match['match_state'] == 'finished':
            print(f"DEBUG: Матч {match_id} уже завершен, показываем результаты")
            await show_results_for_finished_match(bot, chat_id, message_id, state, match, user_id)
            return
        
        # Проверяем, готов ли матч к обработке
        if not match['player1_kicks'] or not match['player1_defenses']:
            await bot.send_message(chat_id, "❌ Игрок 1 еще не завершил выбор")
            return
        
        if not match['is_vs_bot'] and (not match['player2_kicks'] or not match['player2_defenses']):
            # Если это PvP и второй игрок не готов, продолжаем ждать
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="✅ <b>Действия выбраны!</b>\n\n"
                     "Ожидаем, пока оппонент выберет свои действия...\n\n"
                     "<i>Автообновление каждые 10 секунд</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Проверить", callback_data="penalty_v2_check_opponent")]
                ]),
                parse_mode="HTML"
            )
            return
        
        print(f"DEBUG: Обрабатываем матч {match_id}")
        # Обрабатываем матч
        result = await process_penalty_match_v2(match_id)
        
        if not result:
            # Если матч уже был обработан другим игроком, получаем результаты из БД
            match_updated = await get_penalty_match_v2_by_id(match_id)
            if match_updated and match_updated['match_state'] == 'finished':
                print(f"DEBUG: Матч {match_id} был обработан другим игроком")
                await show_results_for_finished_match(bot, chat_id, message_id, state, match_updated, user_id)
                return
            else:
                await bot.send_message(chat_id, "❌ Ошибка обработки матча")
                return
        
        # СОХРАНЯЕМ РЕЗУЛЬТАТ В БАЗУ ДАННЫХ ДЛЯ КАЖДОГО ИГРОКА ОТДЕЛЬНО
        # Функция save_penalty_result_v2 теперь сама обновляет рейтинг и баланс
        await save_penalty_result_v2(match, result, 0, 0, user_id)
        
        # Получаем актуальные данные о наградах из БД
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            penalty_result = await conn.fetchrow("""
            SELECT rating_change, coins_earned, is_winner 
            FROM penalty_results 
            WHERE match_id = $1 AND user_id = $2
            """, match_id, user_id)
            
            if penalty_result:
                rating_change = penalty_result['rating_change'] or 0
                coins_earned = penalty_result['coins_earned'] or 0
                is_winner = penalty_result['is_winner']
            else:
                # Если записи нет, используем стандартные награды
                is_winner = result['winner_id'] == user_id
                is_draw = result['winner_id'] is None
                
                if match['is_vs_bot']:
                    if is_winner:
                        rating_change = int(PENALTY_V2_CONFIG['rating_change_win'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                        coins_earned = PENALTY_V2_CONFIG['coins_bot_win']
                    elif is_draw:
                        rating_change = int(PENALTY_V2_CONFIG['rating_change_draw'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                        coins_earned = PENALTY_V2_CONFIG['coins_bot_draw']
                    else:
                        rating_change = int(PENALTY_V2_CONFIG['rating_change_lose'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                        coins_earned = PENALTY_V2_CONFIG['coins_bot_lose']
                else:
                    if is_winner:
                        rating_change = PENALTY_V2_CONFIG['rating_change_win']
                        coins_earned = PENALTY_V2_CONFIG['coins_win']
                    elif is_draw:
                        rating_change = PENALTY_V2_CONFIG['rating_change_draw']
                        coins_earned = PENALTY_V2_CONFIG['coins_draw']
                    else:
                        rating_change = PENALTY_V2_CONFIG['rating_change_lose']
                        coins_earned = PENALTY_V2_CONFIG['coins_lose']
        
        # Показываем результаты ТОЛЬКО для текущего пользователя
        await show_match_results_v2(bot, chat_id, message_id, state, match, result, rating_change, coins_earned, user_id)
        
    except Exception as e:
        print(f"Error in process_and_show_results_v2: {e}")
        await bot.send_message(chat_id, f"❌ Произошла ошибка: {str(e)}")

async def show_results_for_finished_match(bot: Bot, chat_id: int, message_id: int, state: FSMContext, match: dict, user_id: int):
    """Показывает результаты уже завершенного матча"""
    try:
        # Создаем результат из данных матча
        result = {
            'player1_score': match['player1_score'],
            'player2_score': match['player2_score'],
            'winner_id': match['winner_id']
        }
        
        # Получаем запись результата для этого пользователя
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            penalty_result = await conn.fetchrow("""
            SELECT rating_change, coins_earned, is_winner
            FROM penalty_results 
            WHERE match_id = $1 AND user_id = $2
            """, match['id'], user_id)
            
            if penalty_result:
                rating_change = penalty_result['rating_change'] or 0
                coins_earned = penalty_result['coins_earned'] or 0
                is_winner = penalty_result['is_winner']
            else:
                # Если записи нет, создаем ее
                await save_penalty_result_v2(match, result, 0, 0, user_id)
                
                # Повторно получаем данные
                penalty_result = await conn.fetchrow("""
                SELECT rating_change, coins_earned, is_winner
                FROM penalty_results 
                WHERE match_id = $1 AND user_id = $2
                """, match['id'], user_id)
                
                if penalty_result:
                    rating_change = penalty_result['rating_change'] or 0
                    coins_earned = penalty_result['coins_earned'] or 0
                    is_winner = penalty_result['is_winner']
                else:
                    # Если все еще нет, используем стандартные награды
                    is_winner = result['winner_id'] == user_id
                    is_draw = result['winner_id'] is None
                    
                    if match['is_vs_bot']:
                        if is_winner:
                            rating_change = int(PENALTY_V2_CONFIG['rating_change_win'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                            coins_earned = PENALTY_V2_CONFIG['coins_bot_win']
                        elif is_draw:
                            rating_change = int(PENALTY_V2_CONFIG['rating_change_draw'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                            coins_earned = PENALTY_V2_CONFIG['coins_bot_draw']
                        else:
                            rating_change = int(PENALTY_V2_CONFIG['rating_change_lose'] * PENALTY_V2_CONFIG['rating_bot_multiplier'])
                            coins_earned = PENALTY_V2_CONFIG['coins_bot_lose']
                    else:
                        if is_winner:
                            rating_change = PENALTY_V2_CONFIG['rating_change_win']
                            coins_earned = PENALTY_V2_CONFIG['coins_win']
                        elif is_draw:
                            rating_change = PENALTY_V2_CONFIG['rating_change_draw']
                            coins_earned = PENALTY_V2_CONFIG['coins_draw']
                        else:
                            rating_change = PENALTY_V2_CONFIG['rating_change_lose']
                            coins_earned = PENALTY_V2_CONFIG['coins_lose']
        
        # Показываем результаты
        await show_match_results_v2(bot, chat_id, message_id, state, match, result, rating_change, coins_earned, user_id)
        
    except Exception as e:
        print(f"Error in show_results_for_finished_match: {e}")
        await bot.send_message(chat_id, f"❌ Ошибка при показе результатов: {str(e)}")

async def show_match_results_v2(bot: Bot, chat_id: int, message_id: int, state: FSMContext, match: dict, result: dict, rating_change: int, coins_earned: int, user_id: int):
    """Показывает результаты матча для конкретного пользователя"""
    
    # Получаем актуальную информацию о результате для этого пользователя
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        penalty_result = await conn.fetchrow("""
        SELECT is_winner 
        FROM penalty_results 
        WHERE match_id = $1 AND user_id = $2
        """, match['id'], user_id)
        
        if penalty_result:
            is_winner = penalty_result['is_winner']
            # ПРАВИЛЬНОЕ ОПРЕДЕЛЕНИЕ НИЧЬИ: winner_id IS NULL
            is_draw = result['winner_id'] is None
        else:
            # Резервная логика
            is_winner = result['winner_id'] == user_id
            is_draw = result['winner_id'] is None
    
    # Создаем детализацию по раундам
    details_text = await generate_round_details(match, result, user_id)
    
    # Улучшенный вывод результатов
    if is_winner:
        result_text = "🎉 <b>ПОБЕДА!</b> 🎉"
        result_emoji = "✅"
    elif is_draw:
        result_text = "🤝 <b>НИЧЬЯ!</b>"
        result_emoji = "⚖️"
    else:
        result_text = "😢 <b>ПОРАЖЕНИЕ</b>"
        result_emoji = "❌"
    
    rating_symbol = "+" if rating_change > 0 else ""
    coins_symbol = "+" if coins_earned > 0 else ""
    
    # Показываем счет с правильной перспективой
    # Определяем, является ли пользователь player1
    is_player1 = match['player1_id'] == user_id
    if is_player1:
        score_display = f"{result['player1_score']} : {result['player2_score']}"
    else:
        score_display = f"{result['player2_score']} : {result['player1_score']}"
    
    text = (
        f"🏁 <b>МАТЧ ЗАВЕРШЕН</b> 🏁\n\n"
        f"{result_emoji} {result_text}\n\n"
        f"📊 <b>Финальный счет:</b> {score_display}\n"
    )
    
    if rating_change != 0:
        text += f"🏆 <b>Изменение рейтинга:</b> {rating_symbol}{rating_change}\n"
    
    text += f"💰 <b>Монеты:</b> {coins_symbol}{coins_earned}\n\n"
    text += details_text
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Сыграть еще", callback_data="penalty_v2_main_menu")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
    
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error editing message in show_match_results_v2: {e}")
        # Если не удалось изменить сообщение, отправляем новое
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.clear()

@router.callback_query(F.data == "penalty_v2_check_opponent")
async def penalty_v2_check_opponent(callback: CallbackQuery, state: FSMContext):
    """Проверка готовности оппонента с отображением времени"""
    state_data = await state.get_data()
    match_id = state_data.get('match_id')
    
    if not match_id:
        await callback.answer("Ошибка: матч не найден", show_alert=True)
        return
    
    # Получаем актуальную информацию о матче
    match = await get_penalty_match_v2_by_id(match_id)
    
    if not match:
        await callback.answer("Матч не найден", show_alert=True)
        return
    
    # Если матч уже завершен, показываем результаты
    if match['match_state'] == 'finished':
        await process_and_show_results_v2(
            callback.bot, 
            callback.message.chat.id, 
            callback.message.message_id, 
            state, 
            match_id, 
            callback.from_user.id
        )
        return
    
    # Проверяем готовность матча
    if match['player1_kicks'] and match['player1_defenses'] and \
       match['player2_kicks'] and match['player2_defenses']:
        # Матч готов - обрабатываем
        await process_and_show_results_v2(
            callback.bot, 
            callback.message.chat.id, 
            callback.message.message_id, 
            state, 
            match_id, 
            callback.from_user.id
        )
    else:
        # Рассчитываем оставшееся время
        match_created = match['created_at']
        if match_created.tzinfo is None:
            match_created = match_created.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        time_passed = now - match_created
        time_left = timedelta(minutes=3) - time_passed
        
        if time_left.total_seconds() <= 0:
            await callback.answer("Время вышло! Ожидайте результатов...", show_alert=True)
        else:
            minutes_left = int(time_left.total_seconds() // 60)
            seconds_left = int(time_left.total_seconds() % 60)
            await callback.answer(f"Осталось времени: {minutes_left:02d}:{seconds_left:02d}", show_alert=True)

async def generate_round_details(match: dict, result: dict, user_id: int) -> str:
    """Генерирует детализацию по раундам"""
    is_player1 = match['player1_id'] == user_id
    
    if match['is_vs_bot']:
        player_kicks = json.loads(match['player1_kicks'])
        player_defenses = json.loads(match['player1_defenses'])
        opponent_kicks = result.get('bot_kicks', {})
        opponent_defenses = result.get('bot_defenses', {})
    else:
        player_kicks = json.loads(match['player1_kicks'] if is_player1 else match['player2_kicks'])
        player_defenses = json.loads(match['player1_defenses'] if is_player1 else match['player2_defenses'])
        opponent_kicks = json.loads(match['player2_kicks'] if is_player1 else match['player1_kicks'])
        opponent_defenses = json.loads(match['player2_defenses'] if is_player1 else match['player1_defenses'])
    
    details = "🔍 <b>Детали по раундам:</b>\n\n"
    
    player_score = 0
    opponent_score = 0
    
    for i in range(1, 6):
        round_num = str(i)
        player_kick = player_kicks.get(round_num)
        opponent_defense = opponent_defenses.get(round_num)
        opponent_kick = opponent_kicks.get(round_num)
        player_defense = player_defenses.get(round_num)
        
        player_goal = player_kick != opponent_defense
        opponent_goal = opponent_kick != player_defense
        
        if player_goal:
            player_score += 1
        if opponent_goal:
            opponent_score += 1
        
        details += f"<b>Раунд {i}:</b> {player_score}-{opponent_score}\n"
        details += "<blockquote>"
        details += f"⚽ Ваш удар: {get_direction_emoji(player_kick)} → {get_direction_emoji(opponent_defense)} "
        details += "✅ ГОЛ!\n" if player_goal else "❌ Отбил\n"
        
        details += f"🧤 Защита: {get_direction_emoji(opponent_kick)} → {get_direction_emoji(player_defense)} "
        details += "❌ Пропустил\n" if opponent_goal else "✅ Отбил\n"
        details += "</blockquote>"
        
        details += "\n"
    
    return details

# Обработчики навигации
@router.callback_query(F.data == "penalty_v2_main_menu")
async def back_to_penalty_v2_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню пенальти v2"""
    await penalty_v2_main_menu(callback, state)