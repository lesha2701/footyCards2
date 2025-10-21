from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
import math

from db.user_queries import get_user_profile_stats, get_user_badges_with_collections

router = Router()

@router.callback_query(F.data == "profile")
async def show_user_profile(callback: CallbackQuery, state: FSMContext):
    """Показывает профиль пользователя"""
    try:
        user_id = callback.from_user.id
        
        # Получаем статистику профиля
        profile_stats = await get_user_profile_stats(user_id)
        
        if not profile_stats:
            await callback.answer("❌ Ошибка загрузки профиля", show_alert=True)
            return
        
        # Получаем значки пользователя
        badges = await get_user_badges_with_collections(user_id)
        
        # Рассчитываем дополнительные метрики
        win_rate = (profile_stats['wins'] / profile_stats['total_games'] * 100) if profile_stats['total_games'] > 0 else 0
        training_success_rate = (profile_stats['successful_trainings'] / profile_stats['total_trainings'] * 100) if profile_stats['total_trainings'] > 0 else 0
        collection_progress = (profile_stats['collections_with_cards'] / profile_stats['total_collections'] * 100) if profile_stats['total_collections'] > 0 else 0
        
        # Форматируем дату регистрации
        join_date = profile_stats['created_at'].strftime("%d.%m.%Y")
        
        # Безопасное вычисление дней в игре
        created_at = profile_stats['created_at']
        if created_at.tzinfo is None:
            # Если дата без часового пояса, добавляем UTC
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        now_utc = datetime.now(timezone.utc)
        days_in_game = (now_utc - created_at).days
        
        # Создаем текст профиля
        text = f"👤 <b>ПРОФИЛЬ ИГРОКА</b>\n\n"
        
        # Основная информация
        text += f"<b>📝 Игрок:</b> {profile_stats['username']}\n"
        text += f"<b>📅 В игре с:</b> {join_date} ({days_in_game} дней)\n\n"
        
        # Статистика карт и коллекций
        text += "<b>🎴 КОЛЛЕКЦИЯ</b>\n"
        text += "<blockquote>"
        text += f"<b>Карты:</b> {profile_stats['unique_cards']} уникальных / {profile_stats['total_cards']} всего\n"
        text += f"<b>Коллекции:</b> {profile_stats['collections_with_cards']}/{profile_stats['total_collections']} ({collection_progress:.1f}%)\n"
        text += f"<b>Завершено:</b> {profile_stats['completed_collections']} коллекций\n"
        text += "</blockquote>\n\n"
        
        # Игровая статистика
        text += "<b>🎮 СТАТИСТИКА ИГР</b>\n"
        text += "<blockquote>"
        text += f"<b>Игр сыграно:</b> {profile_stats['total_games']}\n"
        text += f"<b>Побед:</b> {profile_stats['wins']} ({win_rate:.1f}%)\n"
        text += f"<b>Выиграно:</b> {profile_stats['total_winnings']:,} монет\n"
        text += f"<b>Тренировок:</b> {profile_stats['total_trainings']}\n"
        text += f"<b>Успешных:</b> {profile_stats['successful_trainings']} ({training_success_rate:.1f}%)\n"
        text += "</blockquote>\n\n"
        
        # Экономика и достижения
        text += "<b>💰 ЭКОНОМИКА</b>\n"
        text += "<blockquote>"
        text += f"<b>Баланс:</b> {profile_stats['balance']:,} монет\n"
        text += f"<b>Очки рейтинга:</b> {profile_stats['score']:,}\n"
        text += f"<b>Рефералов:</b> {profile_stats['verified_referrals']}/{profile_stats['total_referrals']}\n"
        text += "</blockquote>\n"
        
        # Значки
        if badges:
            text += f"\n<b>🎖️ ЗНАЧКИ</b> ({len(badges)})\n"
            
            # Группируем значки по типам
            milestone_badges = [b for b in badges if b['badge_type'].startswith('milestone_')]
            collection_badges = [b for b in badges if b['badge_type'] == 'collection']
            other_badges = [b for b in badges if b['badge_type'] not in ['collection'] and not b['badge_type'].startswith('milestone_')]
            
            if milestone_badges:
                text += "<blockquote>"
                text += "<b>🏆 Достижения:</b>\n"
                for badge in sorted(milestone_badges, key=lambda x: x['badge_type']):
                    text += f"{badge['badge_emoji']} {badge['badge_name']}\n"
            
            if collection_badges:
                # Показываем только последние 5 коллекционных значков
                recent_collection_badges = collection_badges[:5]
                text += f"\n<b>📚 Коллекции:</b> ({len(collection_badges)})\n"
                for badge in recent_collection_badges:
                    text += f"{badge['badge_emoji']} {badge['badge_name']}\n"
                
                if len(collection_badges) > 5:
                    text += f"... и еще {len(collection_badges) - 5} коллекций\n"
                text += "</blockquote>"
            
            if other_badges:
                text += "<blockquote>"
                text += "<b>⭐ Прочие:</b>\n"
                for badge in other_badges:
                    text += f"{badge['badge_emoji']} {badge['badge_name']}\n"
                text += "</blockquote>"
        else:
            text += "\n🎖️ <i>Значков пока нет</i>\n"
            text += "<i>Собирайте коллекции, чтобы получать значки!</i>"
        
        # Создаем клавиатуру
        keyboard_buttons = []
        
        if badges:
            keyboard_buttons.append([
                InlineKeyboardButton(text="🎖️ Все значки", callback_data="view_all_badges")
            ])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="📚 Альбом коллекций", callback_data="album")],
            [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="show_leaderboard")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_user_profile: {e}")
        await callback.answer("❌ Ошибка загрузки профиля", show_alert=True)

@router.callback_query(F.data == "view_all_badges")
async def show_all_badges(callback: CallbackQuery, state: FSMContext):
    """Показывает все значки пользователя с пагинацией"""
    try:
        user_id = callback.from_user.id
        page = 0
        items_per_page = 8
        
        badges = await get_user_badges_with_collections(user_id)
        
        if not badges:
            await callback.answer("❌ У вас пока нет значков", show_alert=True)
            return
        
        await show_badges_page(callback, badges, page, items_per_page)
        
    except Exception as e:
        print(f"Error in show_all_badges: {e}")
        await callback.answer("❌ Ошибка загрузки значков", show_alert=True)

async def show_badges_page(callback: CallbackQuery, badges: list, page: int, items_per_page: int):
    """Показывает страницу со значками"""
    total_pages = math.ceil(len(badges) / items_per_page)
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_badges = badges[start_idx:end_idx]
    
    text = f"🎖️ <b>ВСЕ ЗНАЧКИ</b> ({len(badges)})\n\n"
    text += f"<i>Страница {page + 1}/{total_pages}</i>\n\n"

    text += "<blockquote>"
    
    # Отображаем значки сеткой 2x2 или 2x3
    for i in range(0, len(page_badges), 2):
        row_badges = page_badges[i:i+2]
        for badge in row_badges:        
            # Безопасное форматирование даты
            unlocked_at = badge['unlocked_at']
            if unlocked_at.tzinfo is None:
                unlocked_at = unlocked_at.replace(tzinfo=timezone.utc)
            unlock_date = unlocked_at.strftime("%d.%m.%Y")
            
            text += f"{badge['badge_emoji']} <b>{badge['badge_name']}</b>\n   📅 {unlock_date}\n\n"

    text += "</blockquote>"
    
    # Создаем клавиатуру
    keyboard_buttons = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"badges_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="badges_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"badges_page_{page+1}"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="👤 Назад к профилю", callback_data="profile")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("badges_page_"))
async def navigate_badges_page(callback: CallbackQuery, state: FSMContext):
    """Навигация по страницам значков"""
    try:
        user_id = callback.from_user.id
        page = int(callback.data.split("_")[2])
        items_per_page = 8
        
        badges = await get_user_badges_with_collections(user_id)
        await show_badges_page(callback, badges, page, items_per_page)
        await callback.answer()
        
    except Exception as e:
        print(f"Error in navigate_badges_page: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)