from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, FSInputFile
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import List, Dict, Any
import asyncio
import time
from handlers.main_menu import show_menu
from datetime import datetime, timedelta, timezone

from db.user_queries import (
    get_all_active_users, get_users_count, create_broadcast,
    get_pending_broadcasts, get_broadcast_by_id, update_broadcast_status,
    create_broadcast_status, get_broadcast_stats, get_recent_broadcasts, get_12h_stats
)

from db.pool import get_db_pool

router = Router()

# Состояния для создания рассылки
class BroadcastStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_message = State()
    waiting_for_confirmation = State()
    waiting_for_media = State()

# ID администраторов (замените на свои)
ADMIN_IDS = [5095749754, 6565814594, 1961932260, 6472956055]  # Ваши ID через запятую

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

@router.message(Command("broadcast"))
async def broadcast_command(message: Message, state: FSMContext):
    """Команда для начала создания рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    await message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "Введите заголовок рассылки:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(BroadcastStates.waiting_for_title)

@router.message(BroadcastStates.waiting_for_title)
async def process_broadcast_title(message: Message, state: FSMContext):
    """Обрабатывает заголовок рассылки"""
    await state.update_data(title=message.text)
    
    await message.answer(
        "📝 <b>Введите текст рассылки:</b>\n\n"
        "Вы можете использовать HTML-разметку для форматирования.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Обрабатывает текст рассылки"""
    await state.update_data(message_text=message.text, message_type='text')
    
    # Показываем предпросмотр и кнопки подтверждения
    data = await state.get_data()
    
    preview_text = (
        "👁️ <b>Предпросмотр рассылки</b>\n\n"
        f"<b>Заголовок:</b> {data['title']}\n\n"
        f"<b>Текст:</b>\n{data['message_text']}\n\n"
        f"📊 <b>Будет отправлено:</b> ~{await get_users_count()} пользователям\n\n"
        "<b>Подтверждаете отправку?</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отправить", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="📎 Добавить медиа", callback_data="broadcast_add_media")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
    ])
    
    await message.answer(preview_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(BroadcastStates.waiting_for_confirmation)

@router.message(F.photo, BroadcastStates.waiting_for_media)
async def process_broadcast_photo(message: Message, state: FSMContext):
    """Обрабатывает фото для рассылки"""
    largest_photo = message.photo[-1]
    file_id = largest_photo.file_id
    
    await state.update_data(media_file_id=file_id, message_type='photo')
    await process_broadcast_confirmation(message, state)

@router.message(F.video, BroadcastStates.waiting_for_media)
async def process_broadcast_video(message: Message, state: FSMContext):
    """Обрабатывает видео для рассылки"""
    file_id = message.video.file_id
    await state.update_data(media_file_id=file_id, message_type='video')
    await process_broadcast_confirmation(message, state)

@router.callback_query(F.data == "broadcast_add_media")
async def add_media_to_broadcast(callback: CallbackQuery, state: FSMContext):
    """Добавление медиа к рассылке"""
    await callback.message.edit_text(
        "📎 <b>Отправьте фото или видео для рассылки:</b>\n\n"
        "Или нажмите кнопку ниже чтобы продолжить без медиа.",
        parse_mode="HTML"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Продолжить без медиа", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
    ])
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await state.set_state(BroadcastStates.waiting_for_media)

async def process_broadcast_confirmation(message: Message, state: FSMContext):
    """Показывает финальный предпросмотр перед отправкой"""
    data = await state.get_data()
    
    # Создаем клавиатуру для предпросмотра
    preview_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Меню", callback_data="preview_menu")]
    ])
    
    # Клавиатура для подтверждения отправки
    confirmation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Да, начать рассылку", callback_data="broadcast_start")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
    ])
    
    preview_text = (
        "👁️ <b>Финальный предпросмотр</b>\n\n"
        f"<b>Заголовок:</b> {data['title']}\n\n"
        f"<b>Текст:</b>\n{data['message_text']}\n\n"
    )
    
    if data.get('media_file_id'):
        preview_text += f"<b>Медиа:</b> {'📷 Фото' if data['message_type'] == 'photo' else '🎥 Видео'}\n\n"
    
    preview_text += f"📊 <b>Будет отправлено:</b> ~{await get_users_count()} пользователям\n\n"
    preview_text += "🔘 <i>В каждом сообщении будет кнопка 'Меню' для удаления поста и перехода в меню</i>\n\n"
    preview_text += "<b>Подтверждаете отправку?</b>"
    
    if isinstance(message, Message):
        # Для фото
        if data.get('message_type') == 'photo' and data.get('media_file_id'):
            # Сначала отправляем предпросмотр с кнопкой "Меню"
            await message.answer_photo(
                photo=data['media_file_id'],
                caption=preview_text,
                reply_markup=preview_keyboard,
                parse_mode="HTML"
            )
            # Затем отправляем отдельное сообщение с кнопками подтверждения
            await message.answer(
                "📋 <b>Подтверждение отправки</b>\n\n"
                "Выберите действие:",
                reply_markup=confirmation_keyboard,
                parse_mode="HTML"
            )
        # Для видео
        elif data.get('message_type') == 'video' and data.get('media_file_id'):
            await message.answer_video(
                video=data['media_file_id'],
                caption=preview_text,
                reply_markup=preview_keyboard,
                parse_mode="HTML"
            )
            await message.answer(
                "📋 <b>Подтверждение отправки</b>\n\n"
                "Выберите действие:",
                reply_markup=confirmation_keyboard,
                parse_mode="HTML"
            )
        # Для текста
        else:
            await message.answer(preview_text, reply_markup=preview_keyboard, parse_mode="HTML")
            await message.answer(
                "📋 <b>Подтверждение отправки</b>\n\n"
                "Выберите действие:",
                reply_markup=confirmation_keyboard,
                parse_mode="HTML"
            )
    else:
        # Для CallbackQuery (когда без медиа) - редактируем существующее сообщение
        await message.message.edit_text(preview_text, reply_markup=confirmation_keyboard, parse_mode="HTML")

@router.callback_query(F.data == "preview_menu")
async def preview_menu_handler(callback: CallbackQuery):
    """Обработчик кнопки меню в предпросмотре (демо)"""
    await callback.answer("✅ В реальной рассылке эта кнопка удалит пост и откроет меню!", show_alert=True)

@router.callback_query(F.data == "broadcast_confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рассылки без медиа"""
    await process_broadcast_confirmation(callback, state)

@router.callback_query(F.data == "broadcast_start")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Запуск рассылки"""
    data = await state.get_data()
    
    # Создаем запись о рассылке
    broadcast = await create_broadcast(
        title=data['title'],
        message_text=data['message_text'],
        message_type=data.get('message_type', 'text'),
        media_file_id=data.get('media_file_id')
    )
    
    await callback.message.edit_text(
        "🔄 <b>Запуск рассылки...</b>\n\n"
        "Это может занять несколько минут в зависимости от количества пользователей.",
        parse_mode="HTML"
    )
    
    # Запускаем рассылку в фоне
    asyncio.create_task(send_broadcast(bot, broadcast['id'], callback.from_user.id))
    
    await state.clear()

@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена.")

async def send_broadcast(bot: Bot, broadcast_id: int, admin_id: int):
    """Отправляет рассылку всем пользователям"""
    try:
        broadcast = await get_broadcast_by_id(broadcast_id)
        if not broadcast:
            await bot.send_message(admin_id, "❌ Рассылка не найдена.")
            return
        
        users = await get_all_active_users()
        total_users = len(users)
        sent_count = 0
        failed_count = 0
        
        # Статус сообщение для админа
        status_message = await bot.send_message(
            admin_id,
            f"📤 <b>Начата рассылка:</b> {broadcast['title']}\n"
            f"👥 <b>Всего пользователей:</b> {total_users}\n"
            f"✅ <b>Отправлено:</b> 0\n"
            f"❌ <b>Ошибок:</b> 0\n"
            f"📊 <b>Прогресс:</b> 0%",
            parse_mode="HTML"
        )
        
        start_time = time.time()
        
        for i, user in enumerate(users):
            try:
                # Создаем клавиатуру с кнопкой "Меню"
                menu_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Меню", callback_data="delete_broadcast_and_menu")]
                ])
                
                # Отправляем сообщение в зависимости от типа
                if broadcast['message_type'] == 'photo' and broadcast['media_file_id']:
                    message = await bot.send_photo(
                        chat_id=user['user_id'],
                        photo=broadcast['media_file_id'],
                        caption=broadcast['message_text'],
                        reply_markup=menu_keyboard,
                        parse_mode="HTML"
                    )
                elif broadcast['message_type'] == 'video' and broadcast['media_file_id']:
                    message = await bot.send_video(
                        chat_id=user['user_id'],
                        video=broadcast['media_file_id'],
                        caption=broadcast['message_text'],
                        reply_markup=menu_keyboard,
                        parse_mode="HTML"
                    )
                else:
                    message = await bot.send_message(
                        chat_id=user['user_id'],
                        text=broadcast['message_text'],
                        reply_markup=menu_keyboard,
                        parse_mode="HTML"
                    )
                
                # Сохраняем message_id для возможности удаления
                await create_broadcast_status(
                    broadcast_id, 
                    user['user_id'], 
                    'sent', 
                    message_id=message.message_id  # Сохраняем ID сообщения
                )
                
                sent_count += 1
                
                # Обновляем статус каждые 10 отправок или 10%
                if i % 10 == 0 or i == total_users - 1:
                    progress = (i + 1) / total_users * 100
                    elapsed_time = time.time() - start_time
                    estimated_total = elapsed_time / (i + 1) * total_users
                    remaining_time = estimated_total - elapsed_time
                    
                    try:
                        await bot.edit_message_text(
                            chat_id=admin_id,
                            message_id=status_message.message_id,
                            text=(
                                f"📤 <b>Рассылка:</b> {broadcast['title']}\n"
                                f"👥 <b>Всего пользователей:</b> {total_users}\n"
                                f"✅ <b>Отправлено:</b> {sent_count}\n"
                                f"❌ <b>Ошибок:</b> {failed_count}\n"
                                f"📊 <b>Прогресс:</b> {progress:.1f}%\n"
                                f"⏱️ <b>Осталось:</b> {remaining_time:.0f} сек"
                            ),
                            parse_mode="HTML"
                        )
                    except:
                        pass  # Игнорируем ошибки редактирования сообщения
                
                # Задержка чтобы не превысить лимиты Telegram
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)[:100]  # Обрезаем длинные сообщения об ошибках
                await create_broadcast_status(broadcast_id, user['user_id'], 'failed', error_msg)
        
        # Обновляем статус рассылки
        await update_broadcast_status(broadcast_id, sent_count, failed_count)
        
        # Финальное сообщение
        total_time = time.time() - start_time
        await bot.edit_message_text(
            chat_id=admin_id,
            message_id=status_message.message_id,
            text=(
                f"✅ <b>Рассылка завершена!</b>\n\n"
                f"📝 <b>Заголовок:</b> {broadcast['title']}\n"
                f"👥 <b>Всего пользователей:</b> {total_users}\n"
                f"✅ <b>Успешно отправлено:</b> {sent_count}\n"
                f"❌ <b>Ошибок:</b> {failed_count}\n"
                f"⏱️ <b>Время выполнения:</b> {total_time:.1f} сек\n"
                f"📈 <b>Эффективность:</b> {(sent_count/total_users*100):.1f}%"
            ),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await bot.send_message(admin_id, f"❌ Ошибка при рассылке: {str(e)}")

@router.message(Command("broadcast_stats"))
async def broadcast_stats(message: Message):
    """Показывает статистику рассылок"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    broadcasts = await get_recent_broadcasts(5)
    total_users = await get_users_count()
    
    text = "📊 <b>Статистика рассылок</b>\n\n"
    text += f"👥 <b>Всего пользователей в боте:</b> {total_users}\n\n"
    
    if broadcasts:
        text += "<b>Последние рассылки:</b>\n"
        for broadcast in broadcasts:
            stats = await get_broadcast_stats(broadcast['id'])
            status_emoji = "✅" if broadcast['is_sent'] else "🔄"
            text += (
                f"\n{status_emoji} <b>{broadcast['title']}</b>\n"
                f"   📅 {broadcast['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            )
            
            if broadcast['is_sent']:
                text += (
                    f"   ✅ {stats['sent']} | ❌ {stats['failed']} | "
                    f"📊 {(stats['sent']/total_users*100):.1f}%\n"
                )
    else:
        text += "📭 <i>Рассылок еще не было</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Новая рассылка", callback_data="broadcast_new")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="broadcast_refresh_stats")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "broadcast_new")
async def new_broadcast_from_stats(callback: CallbackQuery, state: FSMContext):
    """Новая рассылка из меню статистики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Введите заголовок рассылки:",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_title)

@router.callback_query(F.data == "broadcast_refresh_stats")
async def refresh_broadcast_stats(callback: CallbackQuery):
    """Обновление статистики рассылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    await broadcast_stats(callback.message)
    await callback.answer("✅ Статистика обновлена")

@router.callback_query(F.data == "delete_broadcast_and_menu")
async def delete_broadcast_and_show_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Удаляет сообщение рассылки и показывает меню"""
    try:
        # Удаляем сообщение с рассылкой
        await callback.message.delete()
        
        # Показываем меню
        from handlers.main_menu import show_menu
        await show_menu(callback, state)
        
        # Подтверждаем callback чтобы убрать часики
        await callback.answer()
        
    except Exception as e:
        print(f"Error deleting broadcast message: {e}")
        # Если не удалось удалить сообщение, все равно показываем меню
        try:
            from handlers.main_menu import show_menu
            await show_menu(callback, state)
        except Exception as menu_error:
            await callback.answer("❌ Ошибка загрузки меню", show_alert=True)

@router.message(Command("stats"))
async def show_stats_command(message: Message):
    """Команда для показа статистики за последние 12 часов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    await message.answer("📊 <b>Сбор статистики...</b>", parse_mode="HTML")
    
    try:
        stats = await get_12h_stats()
        stats_text = format_stats_message(stats)
        
        await message.answer(stats_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ <b>Ошибка при получении статистики:</b>\n{str(e)}", parse_mode="HTML")

def format_stats_message(stats):
    """Форматирует статистику в читаемое сообщение"""
    text = "📊 <b>Статистика за последние 12 часов</b>\n\n"
    
    # Статистика пользователей
    user_stats = stats.get('user_stats', {})
    text += f"👥 <b>Новые пользователи:</b> {user_stats.get('new_users', 0)}\n"
    text += f"💰 <b>Добавлено баланса:</b> {user_stats.get('total_balance_added', 0)} монет\n"
    text += f"🏆 <b>Добавлено очков:</b> {user_stats.get('total_score_added', 0)}\n\n"
    
    # Статистика паков
    pack_stats = stats.get('pack_stats', {})
    text += f"🎁 <b>Открыто паков:</b> {pack_stats.get('total_packs_opened', 0)}\n"
    text += f"👤 <b>Уникальных пользователей:</b> {pack_stats.get('unique_users_opened_packs', 0)}\n"
    text += f"🃏 <b>Получено карт:</b> {pack_stats.get('total_cards_from_packs', 0)}\n\n"
    
    # Статистика по редкостям карт
    rarity_stats = stats.get('rarity_stats', {})
    text += "🎯 <b>Карты по редкостям:</b>\n"
    rarities = ['legendary', 'epic', 'rare', 'common']
    rarity_names = {'legendary': '⚡ Легендарные', 'epic': '💜 Эпические', 'rare': '🔷 Редкие', 'common': '⚪ Обычные'}
    
    for rarity in rarities:
        count = rarity_stats.get(rarity, 0)
        text += f"   {rarity_names.get(rarity, rarity)}: {count}\n"
    text += "\n"
    
    # Статистика тренировок
    training_stats = stats.get('training_stats', {})
    text += f"🏋️ <b>Тренировок проведено:</b> {training_stats.get('total_trainings', 0)}\n"
    text += f"👤 <b>Уникальных пользователей:</b> {training_stats.get('unique_users_trained', 0)}\n"
    text += f"✅ <b>Успешных:</b> {training_stats.get('successful_trainings', 0)}\n"
    text += f"❌ <b>Проваленных:</b> {training_stats.get('failed_trainings', 0)}\n"
    text += f"💰 <b>Заработано:</b> {training_stats.get('total_rewards_earned', 0)} монет\n"
    text += f"📈 <b>Средний уровень:</b> {training_stats.get('average_level', 0):.1f}\n"
    text += f"🚀 <b>Макс. уровень:</b> {training_stats.get('max_level', 0)}\n\n"
    
    # Статистика по типам тренировок
    drill_stats = stats.get('drill_type_stats', [])
    if drill_stats:
        text += "🎯 <b>Типы тренировок:</b>\n"
        for drill in drill_stats[:3]:  # Показываем топ-3
            success_rate = (drill['success_count'] / drill['count'] * 100) if drill['count'] > 0 else 0
            text += f"   {drill['drill_type']}: {drill['count']} ({success_rate:.1f}% успеха)\n"
        text += "\n"
    
    # Статистика игр
    game_stats = stats.get('game_stats', {})
    total_games = game_stats.get('total_games', 0)
    if total_games > 0:
        win_rate = (game_stats.get('wins', 0) / total_games * 100)
        text += f"🎮 <b>Сыграно игр:</b> {total_games}\n"
        text += f"👤 <b>Уникальных игроков:</b> {game_stats.get('unique_users_played', 0)}\n"
        text += f"✅ <b>Побед:</b> {game_stats.get('wins', 0)} ({win_rate:.1f}%)\n"
        text += f"❌ <b>Поражений:</b> {game_stats.get('losses', 0)}\n"
        text += f"🤝 <b>Ничьих:</b> {game_stats.get('draws', 0)}\n"
        text += f"💰 <b>Общие ставки:</b> {game_stats.get('total_bets', 0)} монет\n"
        text += f"🏆 <b>Общий выигрыш:</b> {game_stats.get('total_winnings', 0)} монет\n\n"
    
    # Финансовая статистика
    financial_stats = stats.get('financial_stats', {})
    text += f"💸 <b>Финансовая статистика:</b>\n"
    text += f"   🎮 Выиграно в играх: {financial_stats.get('total_won_in_games', 0)} монет\n"
    text += f"   🏋️ Заработано в тренировках: {financial_stats.get('total_earned_in_trainings', 0)} монет\n"
    text += f"   ⚡ Поставлено в играх: {financial_stats.get('total_bet_in_games', 0)} монет\n\n"
    
    # Реферальная статистика
    referral_stats = stats.get('referral_stats', {})
    text += f"🤝 <b>Реферальная статистика:</b>\n"
    text += f"   Новые рефералы: {referral_stats.get('new_referrals', 0)}\n"
    text += f"   Верифицировано: {referral_stats.get('verified_referrals', 0)}\n"
    text += f"   Выдано наград: {referral_stats.get('rewarded_referrals', 0)}\n"
    text += f"   Всего выдано: {referral_stats.get('total_rewards_given', 0)} монет\n"
    
    text += f"\n⏰ <i>Статистика собрана: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    
    return text