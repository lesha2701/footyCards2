from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import List, Dict, Any
import math

from db.user_queries import *

router = Router()

# Конфигурация наград за коллекции
COLLECTION_REWARDS = {
    'default': 1000,  # Базовая награда за коллекцию
}

COLLECTION_BADGES = {
    'default': {
        'emoji': '🏆',
        'name': 'Собиратель'
    },
    'milestones': {
        1: {'emoji': '🥉', 'name': 'Новичок коллекционер'},
        3: {'emoji': '🥈', 'name': 'Коллекционер любитель'}, 
        5: {'emoji': '🥇', 'name': 'Оптыный коллекционер'},
        10: {'emoji': '😎', 'name': 'Мастер коллекций'},
        15: {'emoji': '👑', 'name': 'Король коллекций'},
    },
    'special_collections': {
        # Можно добавить специальные значки для конкретных коллекций
        # 1: {'emoji': '⭐', 'name': 'Звезда первой коллекции'}
    }
}

# Состояния для альбома
class AlbumStates(StatesGroup):
    viewing_collections = State()
    viewing_collection_details = State()

@router.callback_query(F.data == "album")
async def show_album_main(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню альбома"""
    await show_album_collections(callback, state)

async def show_album_collections(callback: CallbackQuery, state: FSMContext, page: int = 0):
    """Показывает список коллекций с пагинацией"""
    try:
        user_id = callback.from_user.id
        
        # Получаем прогресс по коллекциям
        collections = await get_user_collections_progress(user_id)
        
        if not collections:
            text = (
                "📚 <b>АЛЬБОМ КОЛЛЕКЦИЙ</b>\n\n"
                "😴 <i>Пока нет доступных коллекций</i>\n\n"
                "🎯 Открывайте паки, чтобы начать собирать карты!"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Открыть паки", callback_data="show_shop_packs")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # Настройки пагинации
        items_per_page = 5
        total_pages = math.ceil(len(collections) / items_per_page)
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        page_collections = collections[start_idx:end_idx]
        
        # Статистика
        total_collections = len(collections)
        completed_collections = sum(1 for c in collections if c['user_cards_count'] == c['actual_cards_count'])
        total_user_cards = sum(c['user_cards_count'] for c in collections)
        total_actual_cards = sum(c['actual_cards_count'] for c in collections)
        total_progress = (total_user_cards / total_actual_cards * 100) if total_actual_cards > 0 else 0
        
        text = (
            "📚 <b>АЛЬБОМ КОЛЛЕКЦИЙ</b>\n\n"
            "<b>📊 Общая статистика:</b>\n"
            "<blockquote>"
            f"<b>Коллекций:</b> {total_collections}\n"
            f"<b>Завершено:</b> {completed_collections}\n"
            f"<b>Общий прогресс:</b> {total_progress:.1f}%"
            "</blockquote>\n\n"
            f"<b>🏆 Коллекции:</b> (стр. {page + 1}/{total_pages})\n\n"
        )
        
        # Отображаем коллекции текущей страницы
        for collection in page_collections:
            # Используем actual_cards_count вместо total_cards
            actual_cards = collection['actual_cards_count']
            user_cards = collection['user_cards_count']
            progress_percent = (user_cards / actual_cards * 100) if actual_cards > 0 else 0
            progress_bar = create_progress_bar(user_cards, actual_cards)
            
            status_emoji = "🟢" if collection['is_active'] else "🔴"
            reward_status = "✅" if collection['reward_claimed'] else "💰"
            
            # Получаем значок коллекции
            badge_emoji = collection['badge_emoji'] or COLLECTION_BADGES['default']['emoji']
            
            text += (
                f"{status_emoji} <b>{collection['name']}</b> {badge_emoji} {reward_status}\n"
                f"<blockquote>{progress_bar} {progress_percent:.1f}%\n"
                f"🎴 {user_cards}/{actual_cards} карт</blockquote>\n\n"
            )
        
        # Создаем клавиатуру
        keyboard_buttons = []
        
        # Кнопки коллекций текущей страницы
        for collection in page_collections:
            btn_text = f"📁 {collection['name']}"
            if collection['user_cards_count'] == collection['actual_cards_count']:
                btn_text = f"⭐ {collection['name']}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"collection_{collection['id']}"
                )
            ])
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"album_page_{page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="album_info"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"album_page_{page+1}"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        # Основные кнопки
        keyboard_buttons.append([
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await state.set_state(AlbumStates.viewing_collections)
        await state.update_data(current_page=page, collections=collections)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_album_collections: {e}")
        await callback.answer("❌ Ошибка загрузки альбома", show_alert=True)

@router.callback_query(F.data.startswith("album_page_"))
async def navigate_album_page(callback: CallbackQuery, state: FSMContext):
    """Навигация по страницам альбома"""
    try:
        page = int(callback.data.split("_")[2])
        await show_album_collections(callback, state, page)
        await callback.answer()
    except Exception as e:
        print(f"Error in navigate_album_page: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)

@router.callback_query(F.data.startswith("collection_"))
async def show_collection_details(callback: CallbackQuery, state: FSMContext):
    """Показывает детали коллекции"""
    try:
        user_id = callback.from_user.id
        
        # Исправляем парсинг collection_id - берем только число после "collection_"
        callback_data = callback.data
        if callback_data.startswith("collection_"):
            collection_id_str = callback_data.replace("collection_", "")
            # Убираем все нечисловые символы на случай, если есть что-то еще
            collection_id = int(''.join(filter(str.isdigit, collection_id_str)))
        else:
            await callback.answer("❌ Неверный формат запроса", show_alert=True)
            return
        
        # Получаем информацию о коллекции
        collections = await get_user_collections_progress(user_id)
        collection = next((c for c in collections if c['id'] == collection_id), None)
        
        if not collection:
            await callback.answer("❌ Коллекция не найдена", show_alert=True)
            return
        
        # Получаем карты коллекции с прогрессом пользователя
        cards = await get_collection_cards_with_user_progress(collection_id, user_id)
        
        # Статистика коллекции
        collected_cards = sum(1 for card in cards if card['user_has_card'])
        total_cards = len(cards)
        progress_percent = (collected_cards / total_cards * 100) if total_cards > 0 else 0
        
        # Редкости карт
        rarity_stats = {}
        for card in cards:
            rarity = card['rarity']
            if rarity not in rarity_stats:
                rarity_stats[rarity] = {'total': 0, 'collected': 0}
            rarity_stats[rarity]['total'] += 1
            if card['user_has_card']:
                rarity_stats[rarity]['collected'] += 1
        
        # Получаем настройки значка
        badge_emoji = collection['badge_emoji'] or COLLECTION_BADGES['default']['emoji']
        badge_name = collection['badge_name'] or COLLECTION_BADGES['default']['name']
        
        # Формируем текст
        status_emoji = "🟢" if collection['is_active'] else "🔴"
        reward_status = "✅ Награда получена" if collection['reward_claimed'] else "💰 Награда доступна"
        
        text = (
            f"{status_emoji} <b>{collection['name']}</b>\n\n"
        )
        
        if collection['description']:
            text += f"📝 <i>{collection['description']}</i>\n\n"
        
        text += (
            f"<b>📊 Прогресс коллекции:</b>\n"
            f"<blockquote>{create_progress_bar(collected_cards, total_cards, 15)} {progress_percent:.1f}%\n"
            f"🎴 {collected_cards}/{total_cards}</blockquote>\n\n"
        )
        
        # Статистика по редкостям
        text += "<b>🎯 По редкостям:</b>\n"
        rarity_display = {
            'common': '⚪ Обычные',
            'rare': '🔵 Редкие', 
            'epic': '🟣 Эпические',
            'legendary': '🟡 Легендарные'
        }
        
        text += "<blockquote>"
        for rarity in ['legendary', 'epic', 'rare', 'common']:
            if rarity in rarity_stats:
                stats = rarity_stats[rarity]
                rarity_progress = (stats['collected'] / stats['total'] * 100) if stats['total'] > 0 else 0
                text += f"{rarity_display[rarity]}: {stats['collected']}/{stats['total']} ({rarity_progress:.1f}%)\n"
        text += "</blockquote>"
        
        text += f"\n\n<b>🎁 Награда за завершение:</b> {COLLECTION_REWARDS['default']} монет\n"
        text += f"<b>🎖️ Значок:</b> {badge_emoji} {badge_name}\n"
        text += f"<b>📌 Статус:</b> {reward_status}\n"
        
        # Проверяем возможность получения награды
        can_claim = (collected_cards == total_cards and 
                    not collection['reward_claimed'] and 
                    collection['is_active'])
        
        if can_claim:
            text += f"\n🎉 <b>Вы собрали всю коллекцию! Получите награду и значок {badge_emoji}!</b>"
        
        # Создаем клавиатуру
        keyboard_buttons = []
        
        # Кнопка получения награды
        if can_claim:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"🎁 Получить {COLLECTION_REWARDS['default']} монет и {badge_emoji}",
                    callback_data=f"claim_reward_{collection_id}"
                )
            ])
        
        # Кнопки карт по редкостям
        rarity_buttons = []
        for rarity in ['legendary', 'epic', 'rare', 'common']:
            if rarity in rarity_stats:
                collected = rarity_stats[rarity]['collected']
                total = rarity_stats[rarity]['total']
                rarity_buttons.append(
                    InlineKeyboardButton(
                        text=f"{rarity_display[rarity]} ({collected}/{total})",
                        callback_data=f"view_cards_{collection_id}_{rarity}"
                    )
                )
        
        # Разбиваем кнопки редкостей на ряды по 2
        for i in range(0, len(rarity_buttons), 2):
            keyboard_buttons.append(rarity_buttons[i:i+2])
        
        # Основные кнопки
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="🔙 Назад к альбому", callback_data="album")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await state.set_state(AlbumStates.viewing_collection_details)
        await state.update_data(current_collection_id=collection_id)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_collection_details: {e}")
        await callback.answer("❌ Ошибка загрузки коллекции", show_alert=True)

@router.callback_query(F.data.startswith("view_cards_"))
async def show_collection_cards_by_rarity(callback: CallbackQuery, state: FSMContext):
    """Показывает карты коллекции по редкости"""
    try:
        user_id = callback.from_user.id
        parts = callback.data.split("_")
        collection_id = int(parts[2])
        rarity = parts[3]
        
        # Получаем карты
        cards = await get_collection_cards_with_user_progress(collection_id, user_id)
        filtered_cards = [card for card in cards if card['rarity'] == rarity]
        
        if not filtered_cards:
            await callback.answer("❌ Нет карт этой редкости", show_alert=True)
            return
        
        rarity_display = {
            'common': '⚪ Обычные',
            'rare': '🔵 Редкие',
            'epic': '🟣 Эпические', 
            'legendary': '🟡 Легендарные'
        }
        
        collected = sum(1 for card in filtered_cards if card['user_has_card'])
        total = len(filtered_cards)
        progress_percent = (collected / total * 100) if total > 0 else 0
        
        text = (
            f"🎴 <b>{rarity_display[rarity]} карты</b>\n"
            f"<blockquote>📊 {collected}/{total} собрано ({progress_percent:.1f}%)</blockquote>\n\n"
        )
        
        # Группируем карты по статусу
        collected_cards = [card for card in filtered_cards if card['user_has_card']]
        missing_cards = [card for card in filtered_cards if not card['user_has_card']]
        
        if collected_cards:
            text += "<b>✅ Собраны:</b>\n<blockquote>"
            for card in collected_cards:
                copies_text = f" (x{card['copies_count']})" if card['copies_count'] > 1 else ""
                text += f"• {card['player_name']}{copies_text}\n"
            text += "</blockquote>\n"
        
        if missing_cards:
            text += "<b>❌ Отсутствуют:</b>\n<blockquote>"
            for card in missing_cards:
                text += f"• {card['player_name']}\n"
            text += "</blockquote>"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к коллекции", callback_data=f"collection_{collection_id}")],
            [InlineKeyboardButton(text="📚 К альбому", callback_data="album")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_collection_cards_by_rarity: {e}")
        await callback.answer("❌ Ошибка загрузки карт", show_alert=True)

@router.callback_query(F.data.startswith("claim_reward_"))
async def claim_collection_reward_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик получения награды за коллекцию"""
    try:
        user_id = callback.from_user.id
        collection_id = int(callback.data.split("_")[2])
        
        # Проверяем возможность получения награды
        collections = await get_user_collections_progress(user_id)
        collection = next((c for c in collections if c['id'] == collection_id), None)
        
        if not collection:
            await callback.answer("❌ Коллекция не найдена", show_alert=True)
            return
        
        if collection['reward_claimed']:
            await callback.answer("❌ Награда уже получена", show_alert=True)
            return
        
        # Проверяем завершенность коллекции по actual_cards_count
        if collection['user_cards_count'] != collection['actual_cards_count']:
            await callback.answer("❌ Коллекция не завершена", show_alert=True)
            return
        
        if not collection['is_active']:
            await callback.answer("❌ Коллекция неактивна", show_alert=True)
            return
        
        # Выдаем награду
        reward_amount = COLLECTION_REWARDS['default']
        await claim_collection_reward(user_id, collection_id, reward_amount)
        await update_user_balance(user_id, reward_amount)
        
        # Выдаем значок за коллекцию (используем настройки из БД)
        badge_emoji = collection['badge_emoji'] or COLLECTION_BADGES['default']['emoji']
        badge_name = collection['badge_name'] or COLLECTION_BADGES['default']['name']
        
        await unlock_user_badge(
            user_id=user_id,
            badge_type='collection',
            badge_emoji=badge_emoji,
            badge_name=f"{badge_name}: {collection['name']}",
            collection_id=collection_id
        )
        
        # Проверяем и выдаем milestone значки (только если еще не выданы)
        completed_count = await get_user_completed_collections_count(user_id)
        
        # Получаем уже выданные milestone значки пользователя
        user_badges = await get_user_badges(user_id)
        existing_milestone_badges = {
            badge['badge_type'] for badge in user_badges 
            if badge['badge_type'].startswith('milestone_')
        }
        
        # Выдаем только те milestone значки, которых еще нет у пользователя
        new_milestone_badges = []
        for milestone, badge_info in COLLECTION_BADGES['milestones'].items():
            milestone_badge_type = f'milestone_{milestone}'
            
            # Проверяем, достиг ли пользователь milestone и нет ли у него уже этого значка
            if (completed_count >= milestone and 
                milestone_badge_type not in existing_milestone_badges):
                
                await unlock_user_badge(
                    user_id=user_id,
                    badge_type=milestone_badge_type,
                    badge_emoji=badge_info['emoji'],
                    badge_name=badge_info['name']
                )
                new_milestone_badges.append(badge_info['emoji'])
        
        # Формируем сообщение о наградах
        reward_message = f"🎉 Получено {reward_amount} монет и значок {badge_emoji}!"
        
        if new_milestone_badges:
            milestone_text = ", ".join(new_milestone_badges)
            reward_message += f"\n\n🏆 Новые достижения: {milestone_text}"
        
        # Обновляем сообщение
        await callback.answer(reward_message, show_alert=True)
        await show_collection_details(callback, state)
        
    except Exception as e:
        print(f"Error in claim_collection_reward_handler: {e}")
        await callback.answer("❌ Ошибка получения награды", show_alert=True)

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Создает текстовый прогресс-бар"""
    if total == 0:
        return "░" * length
    
    filled = round((current / total) * length)
    empty = length - filled
    return "█" * filled + "░" * empty