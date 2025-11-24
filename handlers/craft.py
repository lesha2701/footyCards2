from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import random
from typing import List, Dict, Any
from db.pool import get_db_pool
import os

router = Router()

# ========== КОНФИГУРАЦИЯ КРАФТОВ ==========
CRAFT_CONFIG = {
    # Базовый крафт (коллекция FootyCards2)
    'basic_craft': {
        'common_to_rare': {
            'required_cards': 10,
            'required_rarity': 'common',
            'result_rarity': 'rare',
            'collection_name': 'FootyCards2'
        },
        'rare_to_epic': {
            'required_cards': 10, 
            'required_rarity': 'rare',
            'result_rarity': 'epic',
            'collection_name': 'FootyCards2'
        },
        'epic_to_legendary': {
            'required_cards': 5,
            'required_rarity': 'epic', 
            'result_rarity': 'legendary',
            'collection_name': 'FootyCards2'
        }
    },
    
    # Премиум крафт (уникальная коллекция)
    'premium_craft': {
        'epic_craft': {
            'required_cards': {
                'common': 10,
                'rare': 10, 
                'epic': 5
            },
            'chances': {
                'regular_epic': 70,  # эпическая карта любой коллекции кроме базовой и уникальной
                'unique_epic': 30    # эпическая карта уникальной коллекции крафтов
            }
        },
        'legendary_craft': {
            'required_cards': {
                'common': 10,
                'rare': 10,
                'epic': 5, 
                'legendary': 1
            },
            'chances': {
                'regular_legendary': 70,  # легендарная карта любой коллекции кроме базовой и уникальной
                'unique_legendary': 25,   # легендарная карта уникальной коллекции крафтов
                'unique_epic': 5          # эпическая карта уникальной коллекции крафтов
            }
        }
    },
    
    # Название уникальной коллекции для крафтов
    'unique_craft_collection': 'Exclusive'
}

class CraftDesign:
    RARITY_STYLES = {
        'common': {'emoji': '⚪', 'name': 'Обычная', 'color': '⚪'},
        'rare': {'emoji': '🔵', 'name': 'Редкая', 'color': '🔵'},
        'epic': {'emoji': '🟣', 'name': 'Эпическая', 'color': '🟣'},
        'legendary': {'emoji': '🟡', 'name': 'Легендарная', 'color': '🟡'}
    }

# ========== СОСТОЯНИЯ ДЛЯ КРАФТА ==========
class CraftStates(StatesGroup):
    choosing_craft_type = State()
    basic_craft_selection = State()
    premium_craft_selection = State()
    selecting_cards = State()
    selecting_cards_tab = State()
    confirming_craft = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def get_user_cards_by_rarity(user_id: int, rarity: str, collection_name: str = None, exclude_locked: bool = True):
    """Получает карты пользователя по редкости и коллекции"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT uc.id, uc.card_id, c.player_name, c.rarity, c.uniq_name, col.name as collection_name,
               uc.serial_number, uc.is_locked, uc.is_favorite
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        JOIN collections col ON c.collection_id = col.id
        WHERE uc.user_id = $1 AND c.rarity = $2
        """
        params = [user_id, rarity]
        
        if collection_name:
            query += " AND col.name = $3"
            params.append(collection_name)
            
        if exclude_locked:
            query += " AND uc.is_locked = FALSE"
            
        query += " ORDER BY uc.obtained_at DESC"
        
        return await conn.fetch(query, *params)

async def get_user_cards_for_premium_craft(user_id: int, requirements: Dict):
    """Получает карты пользователя для премиум крафта - ТОЛЬКО ИЗ БАЗОВОЙ КОЛЛЕКЦИИ"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT uc.id, uc.card_id, c.player_name, c.rarity, c.uniq_name, col.name as collection_name,
               uc.serial_number, uc.is_locked, uc.is_favorite
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        JOIN collections col ON c.collection_id = col.id
        WHERE uc.user_id = $1 AND uc.is_locked = FALSE AND col.name = 'FootyCards2'
        ORDER BY 
            CASE c.rarity
                WHEN 'common' THEN 1
                WHEN 'rare' THEN 2
                WHEN 'epic' THEN 3
                WHEN 'legendary' THEN 4
            END,
            uc.obtained_at DESC
        """
        return await conn.fetch(query, user_id)

async def get_craft_unique_collection_id():
    """Получает ID уникальной коллекции для крафтов"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT id FROM collections WHERE name = $1"
        return await conn.fetchval(query, CRAFT_CONFIG['unique_craft_collection'])

async def get_random_card_by_rarity(rarity: str, exclude_collections: List[str] = None):
    """Получает случайную карту по редкости, исключая указанные коллекции"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT c.id, c.player_name, c.rarity, c.uniq_name, c.weight, col.name as collection_name
        FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1
        """
        params = [rarity]
        
        if exclude_collections:
            placeholders = ', '.join([f'${i+2}' for i in range(len(exclude_collections))])
            query += f" AND col.name NOT IN ({placeholders})"
            params.extend(exclude_collections)
            
        query += " ORDER BY RANDOM() LIMIT 1"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

async def get_random_card_from_collection(collection_name: str, rarity: str = None):
    """Получает случайную карту из указанной коллекции"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT c.id, c.player_name, c.rarity, c.uniq_name, c.weight, col.name as collection_name
        FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE col.name = $1
        """
        params = [collection_name]
        
        if rarity:
            query += " AND c.rarity = $2"
            params.append(rarity)
            
        query += " ORDER BY RANDOM() LIMIT 1"
        result = await conn.fetchrow(query, *params)
        return dict(result) if result else None

async def add_card_to_user(user_id: int, card_id: int):
    """Добавляет карту пользователю"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем максимальный serial_number для этой карты
        max_serial_query = """
        SELECT COALESCE(MAX(serial_number), 0) as max_serial 
        FROM user_cards 
        WHERE card_id = $1
        """
        max_serial = await conn.fetchval(max_serial_query, card_id)
        
        # Добавляем карту
        insert_query = """
        INSERT INTO user_cards (user_id, card_id, serial_number, obtained_at)
        VALUES ($1, $2, $3, NOW())
        RETURNING id, serial_number
        """
        result = await conn.fetchrow(insert_query, user_id, card_id, max_serial + 1)
        return dict(result) if result else None

async def remove_user_cards(user_id: int, card_ids: List[int]):
    """Удаляет карты у пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "DELETE FROM user_cards WHERE user_id = $1 AND id = ANY($2)"
        await conn.execute(query, user_id, card_ids)

async def get_card_image_path(card_data: Dict) -> str:
    """Получает путь к изображению карты"""
    rarity = card_data.get('rarity', 'common')
    uniq_name = card_data.get('uniq_name', '')
    
    # Пробуем разные возможные пути
    possible_paths = [
        f"players/{rarity}/{uniq_name}.jpg",
        f"players/{rarity}/{uniq_name}.png",
        f"players/{uniq_name}.jpg",
        f"players/{uniq_name}.png",
        f"cards/{rarity}/{uniq_name}.jpg",
        f"cards/{rarity}/{uniq_name}.png",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@router.callback_query(F.data == "craft_menu")
async def craft_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню крафтов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Базовый крафт", callback_data="basic_craft")],
        [InlineKeyboardButton(text="💎 Премиум крафт", callback_data="premium_craft")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    text = (
        "<b>🛠️ МАСТЕРСКАЯ КРАФТА</b>\n\n"
        "<b>Доступно два режима:</b>\n\n"
        "<b>🔄 Базовый крафт:</b>\n"
        "<blockquote>• Обмен карт базовой коллекции 'FootyCards2'\n"
        "• Повышение редкости карт</blockquote>\n\n"
        "💎 <b>Премиум крафт:</b>\n"  
        "<blockquote>• Возможность обменять карты базовой коллекции на карты других доступных коллекций\n"
        "• Шанс получить карты эксклюзивной коллекции, которая доступна только в крафтах!</blockquote>\n\n"
        "<i>Выбери тип крафта:</i>"
    )
    
    # Пытаемся отредактировать сообщение, если это возможно
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        # Если сообщение с фото, отправляем новое сообщение и удаляем старое
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.set_state(CraftStates.choosing_craft_type)

@router.callback_query(F.data == "basic_craft")
async def basic_craft_menu(callback: CallbackQuery, state: FSMContext):
    """Меню базового крафта"""
    user_id = callback.from_user.id
    
    # Проверяем доступность каждого типа крафта
    common_cards = await get_user_cards_by_rarity(user_id, 'common', 'FootyCards2')
    rare_cards = await get_user_cards_by_rarity(user_id, 'rare', 'FootyCards2') 
    epic_cards = await get_user_cards_by_rarity(user_id, 'epic', 'FootyCards2')
    
    keyboard_buttons = []
    
    # Крафт из обычных в редкие
    common_to_rare_available = len(common_cards) >= CRAFT_CONFIG['basic_craft']['common_to_rare']['required_cards']
    common_btn_text = f"{'🎯' if common_to_rare_available else '🔒'}: ⚪ 10 обычных → 🔵 1 редкая"
    keyboard_buttons.append([InlineKeyboardButton(
        text=common_btn_text, 
        callback_data="craft_common_to_rare"
    )])
    
    # Крафт из редких в эпические
    rare_to_epic_available = len(rare_cards) >= CRAFT_CONFIG['basic_craft']['rare_to_epic']['required_cards']
    rare_btn_text = f"{'🎯' if rare_to_epic_available else '🔒'}: 🔵 10 редких → 🟣 1 эпическая"
    keyboard_buttons.append([InlineKeyboardButton(
        text=rare_btn_text,
        callback_data="craft_rare_to_epic" 
    )])
    
    # Крафт из эпических в легендарные
    epic_to_legendary_available = len(epic_cards) >= CRAFT_CONFIG['basic_craft']['epic_to_legendary']['required_cards']
    epic_btn_text = f"{'🎯' if epic_to_legendary_available else '🔒'}: 🟣 5 эпических → 🟡 1 легендарная"
    keyboard_buttons.append([InlineKeyboardButton(
        text=epic_btn_text,
        callback_data="craft_epic_to_legendary"
    )])
    
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="craft_back")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = (
        "🔄 <b> БАЗОВЫЙ КРАФТ</b>\n\n"
        "🎴 <i>Обмен карт коллекции FootyCards2</i>\n\n"
        f"📊 <b>Доступные обмены:</b>\n"
        f"<blockquote>⚪ <b>Обычные → Редкие:</b> 10 обычных = 1 редкая\n"
        f"🔵 <b>Редкие → Эпические:</b> 10 редких = 1 эпическая\n" 
        f"🟣 <b>Эпические → Легендарные:</b> 5 эпических = 1 легендарная</blockquote>\n\n"
        f"📦 <b>Ваши карты FootyCards2:</b>\n"
        f"<blockquote>⚪ Обычные: <b>{len(common_cards)}</b>/10\n"
        f"🔵 Редкие: <b>{len(rare_cards)}</b>/10\n"
        f"🟣 Эпические: <b>{len(epic_cards)}</b>/5</blockquote>\n\n"
        f"<i>Выбери тип обмена и улучши свою коллекцию! 🚀</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CraftStates.basic_craft_selection)

@router.callback_query(F.data.startswith("craft_"))
async def handle_craft_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа крафта"""
    craft_type = callback.data
    
    if craft_type in ["craft_common_to_rare", "craft_rare_to_epic", "craft_epic_to_legendary"]:
        await handle_basic_craft_selection(callback, state, craft_type)
    elif craft_type in ["craft_premium_epic", "craft_premium_legendary"]:
        await handle_premium_craft_selection(callback, state, craft_type)
    elif craft_type == "craft_back":
        await craft_menu(callback, state)

async def handle_basic_craft_selection(callback: CallbackQuery, state: FSMContext, craft_type: str):
    """Обработка выбора базового крафта"""
    user_id = callback.from_user.id
    
    # Определяем параметры крафта
    if craft_type == "craft_common_to_rare":
        config = CRAFT_CONFIG['basic_craft']['common_to_rare']
        required_rarity = 'common'
    elif craft_type == "craft_rare_to_epic":
        config = CRAFT_CONFIG['basic_craft']['rare_to_epic'] 
        required_rarity = 'rare'
    else:  # craft_epic_to_legendary
        config = CRAFT_CONFIG['basic_craft']['epic_to_legendary']
        required_rarity = 'epic'
    
    # Получаем доступные карты
    available_cards = await get_user_cards_by_rarity(
        user_id, required_rarity, config['collection_name']
    )
    
    if len(available_cards) < config['required_cards']:
        await callback.answer(
            f"❌ Недостаточно карт! Нужно {config['required_cards']} {required_rarity} карт коллекции {config['collection_name']}",
            show_alert=True
        )
        return
    
    # Сохраняем данные в состоянии
    await state.update_data({
        'craft_type': 'basic',
        'craft_config': config,
        'available_cards': [dict(card) for card in available_cards],
        'selected_cards': [],
        'required_rarity': required_rarity
    })
    
    await show_card_selection(callback, state, config['required_cards'])

async def handle_premium_craft_selection(callback: CallbackQuery, state: FSMContext, craft_type: str):
    """Обработка выбора премиум крафта"""
    user_id = callback.from_user.id
    
    # Определяем параметры крафта
    if craft_type == "craft_premium_epic":
        config = CRAFT_CONFIG['premium_craft']['epic_craft']
        craft_name = "Эпический крафт"
    else:  # craft_premium_legendary
        config = CRAFT_CONFIG['premium_craft']['legendary_craft'] 
        craft_name = "Легендарный крафт"
    
    # Получаем все доступные карты
    all_cards = await get_user_cards_for_premium_craft(user_id, config['required_cards'])
    all_cards = [dict(card) for card in all_cards]
    
    # Группируем по редкости
    cards_by_rarity = {
        'common': [card for card in all_cards if card['rarity'] == 'common'],
        'rare': [card for card in all_cards if card['rarity'] == 'rare'],
        'epic': [card for card in all_cards if card['rarity'] == 'epic'],
        'legendary': [card for card in all_cards if card['rarity'] == 'legendary']
    }
    
    # Проверяем доступность
    can_craft = True
    for rarity, count in config['required_cards'].items():
        if len(cards_by_rarity[rarity]) < count:
            can_craft = False
            break
    
    if not can_craft:
        await callback.answer("❌ Недостаточно карт для этого крафта!", show_alert=True)
        return
    
    # Сохраняем данные в состоянии
    await state.update_data({
        'craft_type': 'premium',
        'craft_config': config,
        'craft_name': craft_name,
        'available_cards': all_cards,
        'cards_by_rarity': cards_by_rarity,
        'selected_cards': [],
        'requirements': config['required_cards'],
        'current_tab': 'common'
    })
    
    await show_premium_card_selection(callback, state, config['required_cards'])

async def show_card_selection(callback: CallbackQuery, state: FSMContext, required_count: int):
    """Показывает интерфейс выбора карт для базового крафта"""
    data = await state.get_data()
    available_cards = data['available_cards']
    selected_cards = data.get('selected_cards', [])
    
    text = (
        f"🎴 <b>ВЫБОР КАРТ ДЛЯ КРАФТА</b>\n\n"
        f"📋 Выбери <b>{required_count}</b> карт:\n"
        f"✅ Выбрано: <b>{len(selected_cards)}</b>/{required_count}\n\n"
        "<i>🎯 Нажми на карту чтобы выбрать/отменить выбор</i>"
    )
    
    # Создаем кнопки для карт
    keyboard_buttons = []
    
    # Кнопка выбора случайных карт
    if len(available_cards) >= required_count:
        keyboard_buttons.append([InlineKeyboardButton(
            text="🎲 Выбрать случайные карты", 
            callback_data="select_random_cards"
        )])
    
    # Разбиваем карты на страницы по 10 штук
    page_size = 10
    total_pages = (len(available_cards) + page_size - 1) // page_size
    
    # Получаем текущую страницу из состояния или устанавливаем первую
    current_page = data.get('current_page', 0)
    start_idx = current_page * page_size
    end_idx = min(start_idx + page_size, len(available_cards))
    
    # Кнопки карт для текущей страницы
    for card in available_cards[start_idx:end_idx]:
        is_selected = any(c['id'] == card['id'] for c in selected_cards)
        emoji = "✅" if is_selected else "⚪"
        btn_text = f"{emoji} {card['player_name']} (#{card['serial_number']:06d})"
        keyboard_buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"toggle_card_{card['id']}"
        )])
    
    # Навигация по страницам
    if total_pages > 1:
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"page_{current_page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {current_page+1}/{total_pages}", callback_data="page_info"))
        
        if current_page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"page_{current_page+1}"))
        
        keyboard_buttons.append(nav_buttons)
    
    # Кнопки управления
    action_buttons = []
    if selected_cards:
        action_buttons.append(InlineKeyboardButton(
            text="🔄 Выполнить крафт", 
            callback_data="confirm_craft"
        ))
    
    action_buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data="craft_back"))
    keyboard_buttons.append(action_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CraftStates.selecting_cards)

async def show_premium_card_selection(callback: CallbackQuery, state: FSMContext, requirements: Dict):
    """Показывает интерфейс выбора карт для премиум крафта с вкладками"""
    data = await state.get_data()
    selected_cards = data.get('selected_cards', [])
    cards_by_rarity = data['cards_by_rarity']
    current_tab = data.get('current_tab', 'common')
    
    # Подсчитываем выбранные карты по редкости
    selected_by_rarity = {
        'common': len([c for c in selected_cards if c['rarity'] == 'common']),
        'rare': len([c for c in selected_cards if c['rarity'] == 'rare']),
        'epic': len([c for c in selected_cards if c['rarity'] == 'epic']),
        'legendary': len([c for c in selected_cards if c['rarity'] == 'legendary'])
    }
    
    text = (
        f"💎 <b>ВЫБОР КАРТ ДЛЯ ПРЕМИУМ КРАФТА</b>\n\n"
        f"📊 <b>Требуется:</b>\n"
        f"<blockquote>⚪ Обычные: <b>{selected_by_rarity['common']}</b>/{requirements['common']}\n"
        f"🔵 Редкие: <b>{selected_by_rarity['rare']}</b>/{requirements['rare']}\n"
        f"🟣 Эпические: <b>{selected_by_rarity['epic']}</b>/{requirements['epic']}</blockquote>\n"
    )
    
    if 'legendary' in requirements:
        text += f"🟡 Легендарные: <b>{selected_by_rarity['legendary']}</b>/{requirements['legendary']}\n"
    
    text += f"\n🎴 <b>Текущая вкладка:</b> {get_rarity_display_name(current_tab)}\n"
    text += "\n<i>🎯 Нажми на карту чтобы выбрать/отменить выбор</i>"
    
    # Создаем кнопки для карт
    keyboard_buttons = []
    
    # Кнопка автоматического выбора
    keyboard_buttons.append([InlineKeyboardButton(
        text="🎲 Автоматический выбор", 
        callback_data="auto_select_premium"
    )])
    
    # Вкладки по редкостям
    tab_buttons = []
    for rarity in ['common', 'rare', 'epic', 'legendary']:
        if rarity in requirements and cards_by_rarity[rarity]:
            emoji = "⚪" if rarity == 'common' else "🔵" if rarity == 'rare' else "🟣" if rarity == 'epic' else "🟡"
            is_active = "🔘" if current_tab == rarity else "○"
            tab_buttons.append(InlineKeyboardButton(
                text=f"{is_active}{emoji}",
                callback_data=f"tab_{rarity}"
            ))
    
    if tab_buttons:
        # Разбиваем табы на строки по 2-3 кнопки
        for i in range(0, len(tab_buttons), 3):
            keyboard_buttons.append(tab_buttons[i:i+3])
    
    # Карты текущей вкладки с пагинацией
    current_cards = cards_by_rarity.get(current_tab, [])
    page_size = 8
    total_pages = (len(current_cards) + page_size - 1) // page_size
    current_page = data.get('current_page', 0)
    start_idx = current_page * page_size
    end_idx = min(start_idx + page_size, len(current_cards))
    
    # Показываем карты текущей вкладки
    if current_cards:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"━━━━ {get_rarity_display_name(current_tab).upper()} ━━━━",
            callback_data="ignore"
        )])
        
        for card in current_cards[start_idx:end_idx]:
            is_selected = any(c['id'] == card['id'] for c in selected_cards)
            emoji = "✅" if is_selected else "⚪"
            remaining = requirements[current_tab] - selected_by_rarity[current_tab]
            can_select = remaining > 0 or is_selected
            
            if can_select:
                btn_text = f"{emoji} {card['player_name']} (#{card['serial_number']:06d})"
                keyboard_buttons.append([InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"toggle_card_{card['id']}"
                )])
    
    # Навигация по страницам
    if total_pages > 1:
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"page_{current_page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {current_page+1}/{total_pages}", callback_data="page_info"))
        
        if current_page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"page_{current_page+1}"))
        
        keyboard_buttons.append(nav_buttons)
    
    # Кнопки управления
    action_buttons = []
    all_requirements_met = all(
        selected_by_rarity[rarity] >= count 
        for rarity, count in requirements.items()
    )
    
    if all_requirements_met:
        action_buttons.append(InlineKeyboardButton(
            text="🎯 Выполнить крафт", 
            callback_data="confirm_craft"
        ))
    
    action_buttons.append(InlineKeyboardButton(text="🔙 Назад", callback_data="craft_back"))
    keyboard_buttons.append(action_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CraftStates.selecting_cards_tab)

def get_rarity_display_name(rarity: str) -> str:
    """Возвращает отображаемое название редкости"""
    names = {
        'common': 'Обычные',
        'rare': 'Редкие',
        'epic': 'Эпические',
        'legendary': 'Легендарные'
    }
    return names.get(rarity, rarity)

@router.callback_query(F.data.startswith("toggle_card_"))
async def toggle_card_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора/отмены выбора карты"""
    card_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected_cards = data.get('selected_cards', [])
    available_cards = data['available_cards']
    
    # Находим карту
    card = next((c for c in available_cards if c['id'] == card_id), None)
    if not card:
        await callback.answer("❌ Карта не найдена")
        return
    
    # Проверяем выбрана ли уже карта
    is_selected = any(c['id'] == card_id for c in selected_cards)
    
    if data['craft_type'] == 'basic':
        # Базовый крафт - простая логика
        required_count = data['craft_config']['required_cards']
        
        if is_selected:
            # Убираем из выбранных
            selected_cards = [c for c in selected_cards if c['id'] != card_id]
        else:
            # Добавляем если есть место
            if len(selected_cards) < required_count:
                selected_cards.append(card)
            else:
                await callback.answer(f"❌ Можно выбрать только {required_count} карт")
                return
                
    else:
        # Премиум крафт - сложная логика по редкостям
        requirements = data['requirements']
        selected_by_rarity = {
            'common': len([c for c in selected_cards if c['rarity'] == 'common']),
            'rare': len([c for c in selected_cards if c['rarity'] == 'rare']),
            'epic': len([c for c in selected_cards if c['rarity'] == 'epic']),
            'legendary': len([c for c in selected_cards if c['rarity'] == 'legendary'])
        }
        
        if is_selected:
            # Убираем из выбранных
            selected_cards = [c for c in selected_cards if c['id'] != card_id]
        else:
            # Проверяем можно ли добавить карту этой редкости
            if selected_by_rarity[card['rarity']] < requirements[card['rarity']]:
                selected_cards.append(card)
            else:
                await callback.answer(f"❌ Достаточно карт редкости {card['rarity']}")
                return
    
    # Обновляем состояние
    await state.update_data({'selected_cards': selected_cards})
    
    # Обновляем интерфейс
    if data['craft_type'] == 'basic':
        await show_card_selection(callback, state, data['craft_config']['required_cards'])
    else:
        await show_premium_card_selection(callback, state, data['requirements'])
    
    await callback.answer()

@router.callback_query(F.data.startswith("page_"))
async def handle_page_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по страницам"""
    page_num = int(callback.data.split("_")[1])
    await state.update_data({'current_page': page_num})
    
    data = await state.get_data()
    if data['craft_type'] == 'basic':
        await show_card_selection(callback, state, data['craft_config']['required_cards'])
    else:
        await show_premium_card_selection(callback, state, data['requirements'])
    
    await callback.answer()

@router.callback_query(F.data.startswith("tab_"))
async def handle_tab_switch(callback: CallbackQuery, state: FSMContext):
    """Обработка переключения вкладок"""
    tab_name = callback.data.split("_")[1]
    await state.update_data({'current_tab': tab_name, 'current_page': 0})
    
    data = await state.get_data()
    await show_premium_card_selection(callback, state, data['requirements'])
    await callback.answer(f"📁 Переключено на {get_rarity_display_name(tab_name)}")

@router.callback_query(F.data == "select_random_cards")
async def select_random_cards(callback: CallbackQuery, state: FSMContext):
    """Выбор случайных карт для базового крафта"""
    data = await state.get_data()
    available_cards = data['available_cards']
    required_count = data['craft_config']['required_cards']
    
    # Выбираем случайные карты
    selected_cards = random.sample(available_cards, required_count)
    
    await state.update_data({'selected_cards': selected_cards})
    await show_card_selection(callback, state, required_count)
    await callback.answer("🎲 Карты выбраны случайным образом")

@router.callback_query(F.data == "auto_select_premium")
async def auto_select_premium(callback: CallbackQuery, state: FSMContext):
    """Автоматический выбор карт для премиум крафта"""
    data = await state.get_data()
    cards_by_rarity = data['cards_by_rarity']
    requirements = data['requirements']
    
    selected_cards = []
    
    # Для каждой редкости выбираем нужное количество самых старых карт
    for rarity, count in requirements.items():
        if rarity in cards_by_rarity and len(cards_by_rarity[rarity]) >= count:
            # Берем самые старые карты (первые в списке, т.к. они отсортированы по дате получения)
            selected_cards.extend(cards_by_rarity[rarity][:count])
    
    await state.update_data({'selected_cards': selected_cards})
    await show_premium_card_selection(callback, state, requirements)
    await callback.answer("🎲 Карты выбраны автоматически")

@router.callback_query(F.data == "confirm_craft")
async def confirm_craft(callback: CallbackQuery, state: FSMContext):
    """Подтверждение крафта"""
    data = await state.get_data()
    selected_cards = data.get('selected_cards', [])
    
    if not selected_cards:
        await callback.answer("❌ Не выбрано ни одной карты!", show_alert=True)
        return
    
    # ДОБАВЬТЕ ПРОВЕРКУ ПЕРЕД ПОКАЗОМ ПОДТВЕРЖДЕНИЯ
    if data['craft_type'] == 'basic':
        required_count = data['craft_config']['required_cards']
        if len(selected_cards) != required_count:
            await callback.answer(f"❌ Нужно выбрать ровно {required_count} карт", show_alert=True)
            await show_card_selection(callback, state, required_count)
            return
    else:
        requirements = data['requirements']
        selected_by_rarity = {
            'common': len([c for c in selected_cards if c['rarity'] == 'common']),
            'rare': len([c for c in selected_cards if c['rarity'] == 'rare']),
            'epic': len([c for c in selected_cards if c['rarity'] == 'epic']),
            'legendary': len([c for c in selected_cards if c['rarity'] == 'legendary'])
        }
        
        all_requirements_met = all(
            selected_by_rarity[rarity] == count 
            for rarity, count in requirements.items()
        )
        
        if not all_requirements_met:
            await callback.answer("❌ Не выполнены все требования по картам", show_alert=True)
            await show_premium_card_selection(callback, state, requirements)
            return
    
    if data['craft_type'] == 'basic':
        config = data['craft_config']
        text = (
            f"🔄 <b>ПОДТВЕРЖДЕНИЕ БАЗОВОГО КРАФТА</b>\n\n"
            f"🎯 <b>Обмен:</b> {config['required_cards']} {config['required_rarity']} → 1 {config['result_rarity']}\n"
            f"🏆 <b>Коллекция:</b> {config['collection_name']}\n\n"
            f"📋 <b>Используемые карты:</b>\n"
        )

        text += "<blockquote>"
        
        for card in selected_cards:
            text += f"• {card['player_name']} (#{card['serial_number']:06d})\n"

        text += "</blockquote>"
            
    else:
        config = data['craft_config']
        craft_name = data['craft_name']
        
        text = (
            f"💎 <b>ПОДТВЕРЖДЕНИЕ ПРЕМИУМ КРАФТА</b>\n\n"
            f"🔮 <b>Тип:</b> {craft_name}\n\n"
            f"📋 <b>Используемые карты:</b>\n"
        )
        
        # Группируем по редкости
        by_rarity = {}
        for card in selected_cards:
            if card['rarity'] not in by_rarity:
                by_rarity[card['rarity']] = []
            by_rarity[card['rarity']].append(card)
        
        for rarity, cards in by_rarity.items():
            text += f"\n🎴 {rarity.upper()} ({len(cards)}):\n"

            text += "<blockquote>"
            for card in cards:
                text += f"• {card['player_name']} (#{card['serial_number']:06d})\n"
            text += "</blockquote>"
        
        # Информация о шансах
        text += f"\n🎲 <b>Шансы результата:</b>\n"
        for outcome, chance in config['chances'].items():
            text += f"• {get_outcome_description(outcome)}: <b>{chance}%</b>\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить крафт", callback_data="execute_craft")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_craft")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CraftStates.confirming_craft)

def get_outcome_description(outcome: str) -> str:
    """Возвращает описание исхода крафта"""
    descriptions = {
        'regular_epic': '🎴 Эпическая карта (регулярная)',
        'unique_epic': '💎 Эпическая карта (уникальная)',
        'regular_legendary': '🎴 Легендарная карта (регулярная)', 
        'unique_legendary': '💎 Легендарная карта (уникальная)',
        'unique_epic_from_legendary': '💎 Эпическая карта (уникальная)'
    }
    return descriptions.get(outcome, outcome)

@router.callback_query(F.data == "execute_craft")
async def execute_craft(callback: CallbackQuery, state: FSMContext):
    """Выполнение крафта"""
    data = await state.get_data()
    selected_cards = data.get('selected_cards', [])
    user_id = callback.from_user.id
    
    if not selected_cards:
        await callback.answer("❌ Ошибка: не выбраны карты для крафта", show_alert=True)
        await state.clear()
        return
    
    try:
        # ДОБАВЬТЕ ПРОВЕРКУ КОЛИЧЕСТВА КАРТ
        if data['craft_type'] == 'basic':
            required_count = data['craft_config']['required_cards']
            if len(selected_cards) != required_count:
                await callback.answer(f"❌ Ошибка: нужно выбрать ровно {required_count} карт", show_alert=True)
                await show_card_selection(callback, state, required_count)
                return
        else:
            # Для премиум крафта проверяем требования по редкостям
            requirements = data['requirements']
            selected_by_rarity = {
                'common': len([c for c in selected_cards if c['rarity'] == 'common']),
                'rare': len([c for c in selected_cards if c['rarity'] == 'rare']),
                'epic': len([c for c in selected_cards if c['rarity'] == 'epic']),
                'legendary': len([c for c in selected_cards if c['rarity'] == 'legendary'])
            }
            
            all_requirements_met = all(
                selected_by_rarity[rarity] == count 
                for rarity, count in requirements.items()
            )
            
            if not all_requirements_met:
                await callback.answer("❌ Ошибка: не выполнены все требования по картам", show_alert=True)
                await show_premium_card_selection(callback, state, requirements)
                return
        
        # Если проверки пройдены, выполняем крафт
        if data['craft_type'] == 'basic':
            result = await execute_basic_craft(user_id, selected_cards, data['craft_config'])
        else:
            result = await execute_premium_craft(user_id, selected_cards, data['craft_config'])
        
        if result['success']:
            # Удаляем использованные карты
            card_ids = [card['id'] for card in selected_cards]
            await remove_user_cards(user_id, card_ids)
            
            # Показываем результат
            await show_craft_result(callback, result)
        else:
            await callback.answer(f"❌ Ошибка крафта: {result['error']}", show_alert=True)
            
    except Exception as e:
        print(f"Ошибка при выполнении крафта: {e}")
        await callback.answer("❌ Произошла ошибка при выполнении крафта", show_alert=True)
    
    await state.clear()

async def execute_basic_craft(user_id: int, used_cards: List[Dict], config: Dict):
    """Выполняет базовый крафт"""
    try:
        # Получаем случайную карту нужной редкости и коллекции
        result_card = await get_random_card_from_collection(
            config['collection_name'], 
            config['result_rarity']
        )
        
        if not result_card:
            return {'success': False, 'error': 'Карта для результата не найдена. Убедитесь, что в коллекции есть карты нужной редкости.'}
        
        # Добавляем карту пользователю
        add_result = await add_card_to_user(user_id, result_card['id'])
        
        if not add_result:
            return {'success': False, 'error': 'Не удалось добавить карту'}
        
        return {
            'success': True,
            'result_card': result_card,
            'used_cards': used_cards,
            'craft_type': 'basic',
            'serial_number': add_result['serial_number']
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def execute_premium_craft(user_id: int, used_cards: List[Dict], config: Dict):
    """Выполняет премиум крафт"""
    try:
        # Определяем результат по шансам
        outcome = determine_craft_outcome(config['chances'])
        
        # Получаем карту в зависимости от исхода
        if outcome == 'regular_epic':
            result_card = await get_random_card_by_rarity(
                'epic', 
                ['FootyCards2', CRAFT_CONFIG['unique_craft_collection']]
            )
        elif outcome == 'unique_epic':
            result_card = await get_random_card_from_collection(
                CRAFT_CONFIG['unique_craft_collection'],
                'epic'
            )
        elif outcome == 'regular_legendary':
            result_card = await get_random_card_by_rarity(
                'legendary',
                ['FootyCards2', CRAFT_CONFIG['unique_craft_collection']]
            )
        elif outcome == 'unique_legendary':
            result_card = await get_random_card_from_collection(
                CRAFT_CONFIG['unique_craft_collection'], 
                'legendary'
            )
        elif outcome == 'unique_epic_from_legendary':
            result_card = await get_random_card_from_collection(
                CRAFT_CONFIG['unique_craft_collection'],
                'epic'
            )
        else:
            return {'success': False, 'error': 'Неизвестный исход крафта'}
        
        if not result_card:
            return {'success': False, 'error': 'Карта для результата не найдена. Возможно, в базе данных нет подходящих карт.'}
        
        # Добавляем карту пользователю
        add_result = await add_card_to_user(user_id, result_card['id'])
        
        if not add_result:
            return {'success': False, 'error': 'Не удалось добавить карту'}
        
        return {
            'success': True,
            'result_card': result_card,
            'used_cards': used_cards,
            'craft_type': 'premium', 
            'outcome': outcome,
            'serial_number': add_result['serial_number']
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def determine_craft_outcome(chances: Dict) -> str:
    """Определяет исход крафта на основе шансов"""
    rand = random.randint(1, 100)
    cumulative = 0
    
    for outcome, chance in chances.items():
        cumulative += chance
        if rand <= cumulative:
            return outcome
    
    return list(chances.keys())[-1]  # fallback

async def show_craft_result(callback: CallbackQuery, result: Dict):
    """Показывает результат крафта с изображением карты"""
    result_card = result['result_card']
    
    # Стили для редкостей
    style = CraftDesign.RARITY_STYLES.get(result_card['rarity'], CraftDesign.RARITY_STYLES['common'])
    
    # Получаем путь к изображению карты
    image_path = await get_card_image_path(result_card)
    
    text = (
        f"🎉 <b>КРАФТ УСПЕШНО ВЫПОЛНЕН! </b>\n\n"
        f"🎴 <b>Вы получили новую карту:</b>\n\n"
        f"{style['color']} <b>🏷️ Игрок:</b> {result_card['player_name']}\n"
        f"{style['color']} <b>⭐ Редкость:</b> {style['name']}\n"
        f"{style['color']} <b>🔢 Номер:</b> #{result['serial_number']:06d}\n"
        f"{style['color']} <b>🎯 Рейтинг:</b> {int(result_card['weight'])}\n"
        f"{style['color']} <b>🏆 Коллекция:</b> {result_card['collection_name']}\n"
    )
    
    if result['craft_type'] == 'premium':
        outcome_emoji = "💎" if "unique" in result['outcome'] else "🎴"
        text += f"\n{outcome_emoji} <b>Исход:</b> {get_outcome_description(result['outcome'])}\n"
    
    text += f"\n<i>🎨 Продолжай творить и собирай уникальные карты!</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ Еще крафты", callback_data="craft_menu")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
    ])
    
    # Удаляем предыдущее сообщение (сообщение с выбором карт)
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем сообщение с изображением или без
    try:
        if image_path and os.path.exists(image_path):
            photo = FSInputFile(image_path)
            await callback.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Ошибка при отправке результата крафта: {e}")
        # Fallback - отправляем просто текст
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "cancel_craft")
async def cancel_craft(callback: CallbackQuery, state: FSMContext):
    """Отмена крафта"""
    await state.clear()
    await craft_menu(callback, state)

@router.callback_query(F.data == "craft_back")
async def craft_back(callback: CallbackQuery, state: FSMContext):
    """Назад в меню крафтов"""
    await state.clear()
    await craft_menu(callback, state)

@router.callback_query(F.data == "premium_craft")
async def premium_craft_menu(callback: CallbackQuery, state: FSMContext):
    """Меню премиум крафта"""
    epic_config = CRAFT_CONFIG['premium_craft']['epic_craft']
    legendary_config = CRAFT_CONFIG['premium_craft']['legendary_craft']
    
    text = (
        "💎 <b>ПРЕМИУМ КРАФТ</b>\n\n"        
        f"🎯 <b>Эпический крафт:</b>\n"
        f"<blockquote>⚪ Обычные: <b>{epic_config['required_cards']['common']}</b>\n"
        f"🔵 Редкие: <b>{epic_config['required_cards']['rare']}</b>\n" 
        f"🟣 Эпические: <b>{epic_config['required_cards']['epic']}</b>\n\n"
        f"🎲 Шансы: <b>{epic_config['chances']['regular_epic']}%</b> коллекционная эпическая, "
        f"<b>{epic_config['chances']['unique_epic']}%</b> эксклюзивная эпическая</blockquote>\n\n"
        
        f"🌟 <b>Легендарный крафт:</b>\n"
        f"<blockquote>⚪ Обычные: <b>{legendary_config['required_cards']['common']}</b>\n"
        f"🔵 Редкие: <b>{legendary_config['required_cards']['rare']}</b>\n"
        f"🟣 Эпические: <b>{legendary_config['required_cards']['epic']}</b>\n"
        f"🟡 Легендарные: <b>{legendary_config['required_cards']['legendary']}</b>\n\n"
        f"🎲 Шансы: <b>{legendary_config['chances']['regular_legendary']}%</b> коллекционная легендарная, "
        f"<b>{legendary_config['chances']['unique_legendary']}%</b> эксклюзивная легендарная, "
        f"<b>{legendary_config['chances']['unique_epic']}%</b> эксклюзивная эпическая</blockquote>\n\n"
        
        f"<i>🎰 Испытай удачу и получи эксклюзивные карты!</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟣 Эпический крафт", callback_data="craft_premium_epic")],
        [InlineKeyboardButton(text="🟡 Легендарный крафт", callback_data="craft_premium_legendary")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="craft_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CraftStates.premium_craft_selection)