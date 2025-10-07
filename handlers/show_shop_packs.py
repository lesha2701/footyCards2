from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile  
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
from typing import List, Dict, Any
from datetime import datetime
import traceback

from db.pack_queries import *
from db.user_queries import *
from db.card_queries import *

from handlers.main_menu import show_menu
import os
import asyncio

router = Router()

# Стили для оформления
class PackDesign:
    PACK_STYLES = {
        'standard': {
            'icon': '📦',
            'color': '🔵',
            'name': 'Стандартный',
            'header': '🛍️ СТАНДАРТНЫЕ ПАКИ'
        }
    }
    
    RARITY_STYLES = {
        'common': {'emoji': '⚪', 'name': 'Обычная', 'color': '⚪'},
        'rare': {'emoji': '🔵', 'name': 'Редкая', 'color': '🔵'},
        'epic': {'emoji': '🟣', 'name': 'Эпическая', 'color': '🟣'},
        'legendary': {'emoji': '🟡', 'name': 'Легендарная', 'color': '🟡'}
    }

class PackStates(StatesGroup):
    viewing_packs = State()
    viewing_cards = State()
    confirm_purchase = State()

async def create_pack_card(pack: Dict, user_balance: int, user_id: int = None) -> str:
    """Создает красивую карточку пака"""
    try:
        print(f"[{datetime.now()}] Начало создания карточки пака {pack.get('id', 'unknown')} для пользователя {user_id}")
        
        style = PackDesign.PACK_STYLES.get(pack['pack_type'], PackDesign.PACK_STYLES['standard'])
        
        # Заголовок пака
        header = f"{style['icon']} <b>{pack['name']}</b>\n"
        
        # Описание
        description = f"<i>{pack['description']}</i>\n\n" if pack.get('description') else "\n"
        
        # Информация о картах
        content = f"🎴 <b>Карт в паке:</b> {pack['cards_amount']}\n"
        
        # Шансы редкостей в виде прогресс-баров
        chances = "🎲 <b>Шансы редкостей:</b>\n"
        rarity_chances = [
            ('common', pack['common_chance']),
            ('rare', pack['rare_chance']), 
            ('epic', pack['epic_chance']),
            ('legendary', pack['legendary_chance'])
        ]
        
        for rarity, chance in rarity_chances:
            if chance > 0:
                bar = "█" * max(1, round(chance / 10))
                spaces = " " * (10 - len(bar))
                chances += f"{PackDesign.RARITY_STYLES[rarity]['emoji']} {bar}{spaces} {chance}%\n"
        
        # Стоимость и доступность
        price_section = ""
        if pack['cost'] == 0:
            price_section = "💸 <b>Стоимость:</b> БЕСПЛАТНО\n"
            if user_id:
                can_open, time_left = await can_open_free_pack(user_id)
                if can_open:
                    status = "🟢 <b>Готов к открытию!</b>"
                else:
                    hours = int(time_left // 3600)
                    mins = int((time_left % 3600) // 60)
                    status = f"⏰ <b>Доступно через:</b> {hours}ч {mins}м"
            else:
                status = "🟢 <b>Готов к открытию!</b>"
        else:
            price_section = f"💰 <b>Стоимость:</b> {pack['cost']} монет\n"
            can_afford = user_balance >= pack['cost']
            status = "🟢 <b>Доступно для покупки</b>" if can_afford else "🔴 <b>Недостаточно монет</b>"
        
        # Собираем карточку
        card_text = (
            f"{header}"
            f"{description}"
            f"{content}\n"
            f"{chances}\n"
            f"{price_section}\n"
            f"{status}"
        )
        return card_text
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА создания карточки пака: {e}")
        traceback.print_exc()
        return "❌ Ошибка создания карточки пака"

async def create_packs_keyboard(
    packs: List[Dict], 
    current_index: int,
    user_id: int = None,
    show_collections: bool = False
) -> InlineKeyboardMarkup:
    """Создает интерактивную клавиатуру для паков"""
    try:
        
        current_pack = packs[current_index]
        user = await get_user_by_id(user_id) if user_id else None
        
        # Кнопки навигации
        navigation_buttons = []
        if len(packs) > 1:
            navigation_buttons = [
                InlineKeyboardButton(text="◀️", callback_data=f"pack_prev_{current_index}"),
                InlineKeyboardButton(text=f"📄 {current_index + 1}/{len(packs)}", callback_data="pack_info"),
                InlineKeyboardButton(text="▶️", callback_data=f"pack_next_{current_index}")
            ]
        
        # Основная кнопка действия
        if current_pack['cost'] == 0:
            can_open, _ = await can_open_free_pack(user_id) if user_id else (True, 0)
            action_text = "🎁 Открыть пак" if can_open else "⏳ Недоступно"
            callback_data = f"pack_open_{current_pack['id']}" if can_open else "pack_cant_open"
        else:
            can_afford = user and user['balance'] >= current_pack['cost']
            action_text = "💎 Купить пак" if can_afford else "💸 Недостаточно"
            callback_data = f"pack_confirm_{current_pack['id']}" if can_afford else "pack_cant_buy"
        
        action_button = [InlineKeyboardButton(text=action_text, callback_data=callback_data)]
        
        # Кнопка возврата
        back_button = [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
        
        # Собираем клавиатуру
        keyboard_rows = []
        if navigation_buttons:
            keyboard_rows.append(navigation_buttons)
        keyboard_rows.append(action_button)
        keyboard_rows.append(back_button)

        return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА создания клавиатуры паков: {e}")
        traceback.print_exc()
        # Возвращаем простую клавиатуру при ошибке
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
        ])

async def create_confirmation_keyboard(pack_id) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения покупки"""
    try:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, покупаю!", callback_data=f"pack_buy_{pack_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="pack_cancel")
            ],
            [
                InlineKeyboardButton(text="↩️ Назад к пакам", callback_data="back_to_packs")
            ]
        ])
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА создания клавиатуры подтверждения: {e}")
        raise

@router.callback_query(F.data == "show_shop_packs")
async def show_packs_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню паков"""
    user_id = callback.from_user.id
    
    try:
        user = await get_user_by_id(user_id)
        
        # Получаем все доступные паки
        all_packs = await get_available_packs(user_id)
        print(f"[{datetime.now()}] Получено {len(all_packs)} доступных паков для пользователя {user_id}")
        
        # Разделяем на обычные и коллекционные
        standard_packs = [p for p in all_packs if p['pack_type'] == 'standard']
        collection_packs = [p for p in all_packs if p['pack_type'] == 'collection']
        
        await state.update_data(
            standard_packs=standard_packs,
            collection_packs=collection_packs,
            current_view='standard',
            current_index=0
        )
        
        # Всегда отправляем новое сообщение для магазина
        try:
            # Пытаемся удалить предыдущее сообщение если это callback
            if hasattr(callback, 'message'):
                await callback.message.delete()
                print(f"[{datetime.now()}] Предыдущее сообщение удалено")
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось удалить предыдущее сообщение: {e}")
        
        # Создаем временное сообщение для редактирования
        temp_message = await callback.message.answer("🔄 Загрузка магазина...")
        
        # Используем это сообщение для отображения паков
        await display_current_pack(callback, state, temp_message)
        
    except Exception as e:
        print(f"[{datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА в show_packs_menu: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка загрузки магазина", show_alert=True)

async def display_current_pack(callback: CallbackQuery, state: FSMContext, message_to_edit=None):
    """Отображает текущий пак"""
    user_id = callback.from_user.id
    
    try:
        data = await state.get_data()
        user = await get_user_by_id(user_id)
        
        current_view = data.get('current_view', 'standard')
        current_index = data.get('current_index', 0)
        
        packs = data['standard_packs'] if current_view == 'standard' else data['collection_packs']
        style = PackDesign.PACK_STYLES.get(current_view, PackDesign.PACK_STYLES['standard'])
        
        print(f"[{datetime.now()}] Отображение пака {current_index} типа {current_view} для пользователя {user_id}")
        
        if not packs:
            message = (
                f"{style['icon']} <b>{style['header']}</b>\n\n"
                "📭 <b>Паков не найдено</b>\n\n"
                "В данный момент нет доступных паков этого типа.\n"
                "Новые паки появятся скоро! 🎯"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К стандартным пакам", callback_data="toggle_collections")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
            ])
            
            if message_to_edit:
                await message_to_edit.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
            else:
                await callback.message.edit_text(message, reply_markup=keyboard, parse_mode="HTML")
            return
        
        current_pack = packs[current_index]
        
        # Создаем карточку пака
        pack_card = await create_pack_card(current_pack, user['balance'], user_id)
        
        # Полное сообщение с красивым заголовком
        full_message = (
            f"{style['icon']} <b>{style['header']}</b>\n\n"
            f"💰 <b>Ваш баланс:</b> {user['balance']} монет\n\n"
            f"{pack_card}"
        )
        
        keyboard = await create_packs_keyboard(
            packs, current_index, user_id, 
            show_collections=(current_view == 'collection')
        )
        
        if message_to_edit:
            await message_to_edit.edit_text(
                text=full_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=full_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА отображения пака: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка отображения пака", show_alert=True)

@router.callback_query(F.data.startswith("pack_confirm_"))
async def confirm_pack_purchase(callback: CallbackQuery, state: FSMContext):
    """Подтверждение покупки пака"""
    user_id = callback.from_user.id
    
    try:
        pack_id_str = callback.data.split("_")[2]
        print(f"[{datetime.now()}] Подтверждение покупки пака {pack_id_str} для пользователя {user_id}")
        
        # Определяем тип pack_id
        if pack_id_str.startswith('collection'):
            pack_id = pack_id_str
        else:
            pack_id = int(pack_id_str)
            
        user = await get_user_by_id(user_id)
        pack = await get_pack_by_id(pack_id)
        
        if not pack:
            print(f"[{datetime.now()}] Пак {pack_id} не найден")
            await callback.answer("❌ Пак не найден", show_alert=True)
            return
        
        confirmation_text = (
            f"🛒 <b>Подтверждение покупки</b>\n\n"
            f"📦 <b>Пак:</b> {pack['name']}\n"
            f"💳 <b>Стоимость:</b> {pack['cost']} монет\n"
            f"🎴 <b>Карт в паке:</b> {pack['cards_amount']}\n\n"
            f"💰 <b>Текущий баланс:</b> {user['balance']} монет\n"
            f"💸 <b>Баланс после покупки:</b> {user['balance'] - pack['cost']} монет\n\n"
            f"<i>Вы уверены, что хотите купить этот пак?</i>"
        )
        
        keyboard = await create_confirmation_keyboard(pack_id)
        
        await callback.message.edit_text(
            text=confirmation_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(PackStates.confirm_purchase)
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в confirm_pack_purchase: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка подтверждения", show_alert=True)

@router.callback_query(F.data.startswith("pack_buy_"))
async def process_pack_purchase(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки пака"""
    user_id = callback.from_user.id
    
    try:
        pack_id_str = callback.data.split("_")[2]
        print(f"[{datetime.now()}] Обработка покупки пака {pack_id_str} для пользователя {user_id}")
        
        # Определяем тип pack_id
        if pack_id_str.startswith('collection'):
            pack_id = pack_id_str
        else:
            pack_id = int(pack_id_str)
            
        await open_pack(callback, state, pack_id)
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в process_pack_purchase: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка при покупке", show_alert=True)
        await state.clear()

@router.callback_query(F.data == "pack_cancel")
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    """Отмена покупки"""
    user_id = callback.from_user.id
    print(f"[{datetime.now()}] Отмена покупки пользователем {user_id}")
    
    await callback.answer("❌ Покупка отменена")
    await state.set_state(PackStates.viewing_packs)
    await display_current_pack(callback, state)

@router.callback_query(F.data.startswith("pack_"))
async def handle_pack_actions(callback: CallbackQuery, state: FSMContext):
    """Обработка действий с паками"""
    user_id = callback.from_user.id
    action = callback.data.split("_")[1]
    
    print(f"[{datetime.now()}] Обработка действия пака: {callback.data} для пользователя {user_id}")
    
    try:
        data = await state.get_data()
        current_view = data.get('current_view', 'standard')
        current_index = data.get('current_index', 0)
        
        packs = data['standard_packs'] if current_view == 'standard' else data['collection_packs']
        
        if action == "prev":
            new_index = (current_index - 1) % len(packs)
            await state.update_data(current_index=new_index)
            await display_current_pack(callback, state)
            print(f"[{datetime.now()}] Переход к предыдущему паку: {new_index}")
            
        elif action == "next":
            new_index = (current_index + 1) % len(packs)
            await state.update_data(current_index=new_index)
            await display_current_pack(callback, state)
            print(f"[{datetime.now()}] Переход к следующему паку: {new_index}")
            
        elif action == "open":
            pack_id = int(callback.data.split("_")[2])
            print(f"[{datetime.now()}] Запрос на открытие пака {pack_id}")
            await open_pack(callback, state, pack_id)
            
        elif action == "cant":
            if callback.data == "pack_cant_open":
                print(f"[{datetime.now()}] Пользователь {user_id} пытается открыть недоступный бесплатный пак")
                await callback.answer("⏳ Бесплатный пак будет доступен позже!", show_alert=True)
            else:
                print(f"[{datetime.now()}] Пользователь {user_id} пытается купить пак без средств")
                await callback.answer("💸 Недостаточно монет для покупки!", show_alert=True)
        
        await callback.answer()
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА обработки действия пака: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка обработки действия", show_alert=True)

@router.callback_query(F.data == "toggle_collections")
async def toggle_collections_view(callback: CallbackQuery, state: FSMContext):
    """Переключение между стандартными и коллекционными паками"""
    user_id = callback.from_user.id
    
    try:
        data = await state.get_data()
        current_view = data.get('current_view', 'standard')
        
        new_view = 'collection' if current_view == 'standard' else 'standard'
        await state.update_data(current_view=new_view, current_index=0)
        
        print(f"[{datetime.now()}] Пользователь {user_id} переключил вид паков с {current_view} на {new_view}")
        
        await display_current_pack(callback, state)
        await callback.answer(f"📦 Переключено на {new_view} паки")
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА переключения вида паков: {e}")
        await callback.answer("❌ Ошибка переключения", show_alert=True)

@router.callback_query(F.data == "back_to_packs")
async def back_to_packs_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат к меню паков"""
    user_id = callback.from_user.id
    print(f"[{datetime.now()}] Возврат к меню паков пользователем {user_id}")
    
    await state.set_state(PackStates.viewing_packs)
    await display_current_pack(callback, state)

async def open_pack(callback: CallbackQuery, state: FSMContext, pack_id: int):
    """Процесс открытия пака с начислением очков"""
    user_id = callback.from_user.id
    
    print(f"[{datetime.now()}] Начало открытия пака {pack_id} для пользователя {user_id}")
    
    try:
        user = await get_user_by_id(user_id)
        pack = await get_pack_by_id(pack_id)
        
        if not pack:
            print(f"[{datetime.now()}] Пак {pack_id} не найден при открытии")
            await callback.answer("❌ Пак не найден", show_alert=True)
            return
        
        # Проверяем возможность открытия
        if pack['cost'] == 0:
            can_open, time_left = await can_open_free_pack(user_id)
            if not can_open:
                hours = int(time_left // 3600)
                mins = int((time_left % 3600) // 60)
                print(f"[{datetime.now()}] Бесплатный пак недоступен для пользователя {user_id}, осталось {hours}ч {mins}м")
                await callback.answer(f"⏳ Доступно через {hours}ч {mins}м", show_alert=True)
                return
        
        if pack['cost'] > 0 and user['balance'] < pack['cost']:
            print(f"[{datetime.now()}] Недостаточно средств у пользователя {user_id}: баланс {user['balance']}, стоимость {pack['cost']}")
            await callback.answer("❌ Недостаточно монет", show_alert=True)
            return
        
        # Списание стоимости
        if pack['cost'] > 0:
            await update_user_balance(user_id, -pack['cost'])
            print(f"[{datetime.now()}] Списано {pack['cost']} монет с пользователя {user_id}")
        else:
            await update_last_pack_time(user_id)
            print(f"[{datetime.now()}] Обновлено время открытия бесплатного пака для пользователя {user_id}")
        
        # Генерация карт
        cards = await generate_pack_cards(pack)
        print(f"[{datetime.now()}] Сгенерировано {len(cards)} карт для пака {pack_id}")
        
        if not cards:
            # Возвращаем деньги если карты не сгенерировались
            if pack['cost'] > 0:
                await update_user_balance(user_id, pack['cost'])
                print(f"[{datetime.now()}] Возвращены {pack['cost']} монет пользователю {user_id} из-за ошибки генерации")
            await callback.answer("❌ Ошибка генерации карт", show_alert=True)
            return
        
        # Добавляем карты пользователю
        card_ids = [card['id'] for card in cards]
        add_result = await add_cards_to_user(user_id, card_ids)
        serial_numbers = add_result['serial_numbers']
        print(f"[{datetime.now()}] Карты добавлены пользователю {user_id}, серийные номера: {serial_numbers}")
        
        # НАЧИСЛЯЕМ ОЧКИ ЗА КАРТЫ - ПЕРЕМЕЩЕНО В НАЧАЛО!
        total_score_earned = 0
        score_details = []
        
        print(f"[{datetime.now()}] НАЧАЛО РАСЧЕТА ОЧКОВ:")
        
        # Подготавливаем данные для показа
        rarity_order = {'common': 1, 'rare': 2, 'epic': 3, 'legendary': 4}
        sorted_cards = sorted(cards, key=lambda x: rarity_order.get(x['rarity'], 0))
        
        # Рассчитываем очки для каждой карты
        for card in sorted_cards:
            score_for_card = calculate_score_for_card(card)
            total_score_earned += score_for_card
            score_details.append({
                'player_name': card['player_name'],
                'rarity': card['rarity'],
                'score': score_for_card
            })
            print(f"  Карта: {card['player_name']} ({card['rarity']}) = {score_for_card} очков")
        
        print(f"[{datetime.now()}] ИТОГО ОЧКОВ: {total_score_earned}")
        
        # Обновляем счет пользователя - ТЕПЕРЬ ПОСЛЕ РАСЧЕТА ОЧКОВ
        if total_score_earned > 0:
            update_result = await update_user_score(user_id, total_score_earned)
            if update_result:
                print(f"[{datetime.now()}] Начислено {total_score_earned} очков пользователю {user_id}. Новый счет: {update_result['score']}")
            else:
                print(f"[{datetime.now()}] ОШИБКА: Не удалось обновить счет пользователя {user_id}")
        else:
            print(f"[{datetime.now()}] Нет очков для начисления пользователю {user_id}")
        
        # Логируем открытие
        await log_pack_opening(user_id, pack['id'], card_ids)
        print(f"[{datetime.now()}] Открытие пака {pack_id} записано в логи")
        
        # Обновляем статистику
        await update_collection_stats_by_cards(card_ids)
        print(f"[{datetime.now()}] Статистика коллекции обновлена")
        
        # Сохраняем информацию о картах и очках
        card_infos = []
        for i, card in enumerate(sorted_cards):
            # Используем те же очки что уже рассчитали
            card_score = score_details[i]['score']
            card_info = {
                'card': card,
                'serial_number': serial_numbers.get(card['id'], {}).get('serial_number', 0),
                'collection_name': await get_collection_name(card.get('collection_id')),
                'score': card_score
            }
            card_infos.append(card_info)
        
        # ФИНАЛЬНАЯ ПРОВЕРКА СУММЫ
        calculated_total = sum(info['score'] for info in card_infos)
        if calculated_total != total_score_earned:
            print(f"[{datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА: расхождение в сумме очков! calculated_total={calculated_total}, total_score_earned={total_score_earned}")
            # Используем пересчитанную сумму для надежности
            total_score_earned = calculated_total
        
        await state.set_state(PackStates.viewing_cards)
        await state.update_data(
            card_infos=card_infos,
            current_card_index=0,
            pack_name=pack['name'],
            total_score_earned=total_score_earned,
            score_details=score_details
        )
        
        await show_opened_card(callback, state)
        
    except Exception as e:
        print(f"[{datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА при открытии пака: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка при открытии пака", show_alert=True)

def calculate_score_for_card(card: Dict) -> int:
    """Рассчитывает количество очков за карту в зависимости от редкости"""
    rarity = card.get('rarity', 'common')
    
    # Строго определенные диапазоны очков по редкостям
    score_ranges = {
        'common': (5, 10),      # обычный: строго 5-10 очков
        'rare': (10, 15),       # редкий: строго 10-15 очков  
        'epic': (15, 20),       # эпический: строго 15-20 очков
        'legendary': (20, 25)   # легендарный: строго 20-25 очков
    }
    
    # Получаем диапазон для данной редкости
    if rarity not in score_ranges:
        print(f"[{datetime.now()}] ВНИМАНИЕ: неизвестная редкость '{rarity}', используем common")
        rarity = 'common'
    
    min_score, max_score = score_ranges[rarity]
    
    # Случайное значение в диапазоне (включительно)
    score = random.randint(min_score, max_score)
    
    # ДЕБАГ: логируем расчет очков
    print(f"[{datetime.now()}] Расчет очков: {card['player_name']} ({rarity}) -> {min_score}-{max_score} = {score} очков")
    
    # Дополнительная проверка на корректность диапазона
    if not (min_score <= score <= max_score):
        print(f"[{datetime.now()}] ОШИБКА: очки {score} вне диапазона {min_score}-{max_score} для редкости {rarity}")
        # Возвращаем минимальное значение при ошибке
        return min_score
    
    return score

async def show_opened_card(callback: CallbackQuery, state: FSMContext):
    """Показывает открытую карту с картинкой и начисленными очками"""
    user_id = callback.from_user.id
    
    try:
        data = await state.get_data()
        card_infos = data['card_infos']
        current_index = data['current_card_index']
        pack_name = data['pack_name']
        total_score_earned = data.get('total_score_earned', 0)
        
        current_info = card_infos[current_index]
        card = current_info['card']
        rarity_style = PackDesign.RARITY_STYLES.get(card['rarity'], PackDesign.RARITY_STYLES['common'])
        
        print(f"[{datetime.now()}] Отображение карты {current_index + 1}/{len(card_infos)} для пользователя {user_id}, редкость: {card['rarity']}")
        
        # Получаем путь к картинке
        image_path = f"players/{card['rarity']}/{card['uniq_name']}.jpg"
        
        # Создаем текст карточки с информацией об очках
        card_text = (
            f"🎉 <b>НОВАЯ КАРТА!</b>\n\n"
            f"📦 <b>Пак:</b> {pack_name}\n"
            f"🎴 <b>Карта {current_index + 1}/{len(card_infos)}</b>\n\n"
            f"{rarity_style['color']} {rarity_style['emoji']} <b>{card['player_name']}</b>\n"
            f"{rarity_style['color']} 🏷️ {rarity_style['name']}\n"
            f"{rarity_style['color']} 🔢 #{current_info['serial_number']:06d}\n"
            f"{rarity_style['color']} 🎯 {int(card['weight'])}\n"
            f"{rarity_style['color']} ⭐ <b>Очки:</b> +{current_info['score']}\n"
        )
        
        # Добавляем информацию о коллекции
        if current_info['collection_name']:
            card_text += f"\n🏆 <b>Коллекция:</b> {current_info['collection_name']}"
        
        # Показываем общее количество заработанных очков только на последней карте
        if current_index == len(card_infos) - 1 and total_score_earned > 0:
            # Всегда пересчитываем сумму для точности
            calculated_total = sum(info['score'] for info in card_infos)
            card_text += f"\n\n🏅 <b>Всего заработано очков за пак:</b> +{calculated_total}"
            
        # Создаем клавиатуру
        keyboard_rows = []
        
        # Навигация если карт больше одной
        if len(card_infos) > 1:
            nav_buttons = []
            if current_index > 0:
                nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data="card_prev"))
            nav_buttons.append(InlineKeyboardButton(text=f"{current_index + 1}/{len(card_infos)}", callback_data="card_info"))
            if current_index < len(card_infos) - 1:
                nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data="card_next"))
            keyboard_rows.append(nav_buttons)
        
        # Основные кнопки
        action_buttons = []
        if current_index == len(card_infos) - 1:
            # Если это последняя карта, показываем кнопку для открытия еще паков
            action_buttons.append(InlineKeyboardButton(text="📦 Открыть ещё паков", callback_data="show_shop_packs"))
        else:
            # Если не последняя карта, показываем кнопку для быстрого перехода к следующей
            action_buttons.append(InlineKeyboardButton(text="⏩ Следующая карта", callback_data="card_next"))
        
        keyboard_rows.append(action_buttons)
        keyboard_rows.append([InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu_from_shop")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        
        # Всегда отправляем новое сообщение
        try:
            # Удаляем предыдущее сообщение
            await callback.message.delete()
            print(f"[{datetime.now()}] Предыдущее сообщение с картой удалено")
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось удалить предыдущее сообщение: {e}")
        
        if os.path.exists(image_path):
            photo = FSInputFile(image_path)
            await callback.message.answer_photo(
                photo=photo,
                caption=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА отображения карты: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка отображения карты", show_alert=True)

@router.callback_query(F.data.in_(["card_prev", "card_next", "card_info"]))
async def navigate_opened_cards(callback: CallbackQuery, state: FSMContext):
    """Навигация по открытым картам с поддержкой картинок"""
    user_id = callback.from_user.id
    
    try:
        data = await state.get_data()
        current_index = data['current_card_index']
        card_infos = data['card_infos']
        
        print(f"[{datetime.now()}] Навигация по картам: {callback.data}, текущий индекс: {current_index}")
        
        if callback.data == "card_prev":
            new_index = max(0, current_index - 1)
        elif callback.data == "card_next":
            new_index = min(len(card_infos) - 1, current_index + 1)
        else:  # card_info
            await callback.answer(f"Карта {current_index + 1} из {len(card_infos)}")
            return
        
        await state.update_data(current_card_index=new_index)
        
        # Удаляем текущее сообщение и показываем новое
        try:
            await callback.message.delete()
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось удалить сообщение при навигации: {e}")
        
        await show_opened_card(callback, state)
        await callback.answer()
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА навигации по картам: {e}")
        traceback.print_exc()
        await callback.answer("❌ Ошибка навигации", show_alert=True)

@router.callback_query(F.data == "show_shop_packs")
async def show_shop_packs_from_anywhere(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки открытия магазина из любого состояния"""
    user_id = callback.from_user.id
    current_state = await state.get_state()
    
    print(f"[{datetime.now()}] Запрос магазина паков из состояния {current_state} для пользователя {user_id}")
    
    if current_state == PackStates.viewing_cards:
        # Если мы в состоянии просмотра карт, используем специальный обработчик
        await back_to_shop_from_cards(callback, state)
    else:
        # Иначе используем обычный обработчик
        await show_packs_menu(callback, state)

@router.callback_query(F.data == "show_shop_packs", PackStates.viewing_cards)
async def back_to_shop_from_cards(callback: CallbackQuery, state: FSMContext):
    """Возврат в магазин паков из просмотра карт"""
    user_id = callback.from_user.id
    print(f"[{datetime.now()}] Возврат в магазин из просмотра карт для пользователя {user_id}")
    
    await state.set_state(PackStates.viewing_packs)
    try:
        # Удаляем сообщение с картой (если оно есть)
        await callback.message.delete()
    except Exception as e:
        print(f"[{datetime.now()}] Не удалось удалить сообщение с картой: {e}")
    
    try:
        # Отправляем новое сообщение с магазином
        await show_packs_menu(callback, state)
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА возврата в магазин: {e}")
        await callback.answer("❌ Ошибка загрузки магазина", show_alert=True)

@router.callback_query(F.data == "back_to_menu_from_shop", PackStates.viewing_cards)
async def back_to_menu_from_cards(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из просмотра карт с улучшенной логикой удаления"""
    user_id = callback.from_user.id
    print(f"[{datetime.now()}] Возврат в главное меню из просмотра карт для пользователя {user_id}")
    
    try:        
        # Очищаем состояние
        await state.clear()
        
        # Удаляем сообщение с картой
        try:
            await callback.message.delete()
            print(f"[{datetime.now()}] Сообщение с картой успешно удалено")
        except Exception as e:
            print(f"[{datetime.now()}] Не удалось удалить сообщение с картой: {e}")
            # Если не удалось удалить, пытаемся отредактировать
            try:
                await callback.message.edit_text("🔄 Возвращаемся в меню...")
            except:
                pass
        
        # Отправляем новое сообщение с меню
        await show_menu(callback, state)
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА возврата в меню: {e}")
        # В случае ошибки пытаемся отправить меню как новое сообщение
        try:
            await callback.message.answer("🏠 Возвращаемся в главное меню...")
            await show_menu(callback, state)
        except Exception as final_error:
            print(f"[{datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА: {final_error}")
            await callback.answer("❌ Ошибка загрузки меню", show_alert=True)
