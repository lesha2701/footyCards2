from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import List, Dict, Any
import os
from db.user_queries import *

from db.card_queries import get_user_cards_by_rarity, get_user_card_details, get_user_total_cards_count

router = Router()

# Состояния для просмотра карт
class CardsStates(StatesGroup):
    viewing_rarities = State()
    viewing_cards_list = State()
    viewing_card_details = State()

# Стили для редкостей
RARITY_STYLES = {
    'common': {"emoji": "⚪", "name": "Обычные", "button": "⚪ Обычные", "color": "⚪"},
    'rare': {"emoji": "🔵", "name": "Редкие", "button": "🔵 Редкие", "color": "🔵"},
    'epic': {"emoji": "🟣", "name": "Эпические", "button": "🟣 Эпические", "color": "🟣"},
    'legendary': {"emoji": "🟡", "name": "Легендарные", "button": "🟡 Легендарные", "color": "🟡"}
}

@router.callback_query(F.data == "my_cards")
async def cards_menu(callback: CallbackQuery, state: FSMContext):
    """Меню карт с выбором между картами и альбомом"""
    user_id = callback.from_user.id
    
    try:
        # Получаем базовую статистику
        user_stats = await get_user_stats(user_id)
        
        text = (
            "🃏 <b>МОИ КАРТЫ</b>\n\n"
            "📋 <b>Выберите раздел:</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎴 Просмотр карт", callback_data="view_cards")],
            [InlineKeyboardButton(text="📚 Альбом коллекций", callback_data="album")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in cards_menu: {e}")
        await callback.answer("❌ Ошибка загрузки меню", show_alert=True)

@router.callback_query(F.data == "view_cards")
async def show_rarity_selection(callback: CallbackQuery, state: FSMContext):
    """Показывает выбор редкости карт"""
    try:
        user_id = callback.from_user.id
        
        # Получаем количество карт по редкостям
        counts = await get_user_total_cards_count(user_id)
        total_cards = sum(counts.values())
        
        # Красивое оформление
        text = (
            "🎴 <b>МОЯ КОЛЛЕКЦИЯ</b>\n\n"
            f"📊 <b>Всего карт:</b> {total_cards}\n\n"
            "✨ <b>Выберите редкость для просмотра:</b>\n\n"
        )
        
        # Кнопки выбора редкости
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=RARITY_STYLES['legendary']['button'], callback_data="cards_legendary")],
            [InlineKeyboardButton(text=RARITY_STYLES['epic']['button'], callback_data="cards_epic")],
            [InlineKeyboardButton(text=RARITY_STYLES['rare']['button'], callback_data="cards_rare")],
            [InlineKeyboardButton(text=RARITY_STYLES['common']['button'], callback_data="cards_common")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        await state.set_state(CardsStates.viewing_rarities)
        
        # Всегда отправляем новое сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_rarity_selection: {e}")
        await callback.answer("❌ Ошибка загрузки коллекции", show_alert=True)

@router.callback_query(F.data.startswith("cards_") & ~F.data.endswith(("_prev", "_next")))
async def show_cards_list(callback: CallbackQuery, state: FSMContext):
    """Показывает список карт выбранной редкости"""
    try:
        user_id = callback.from_user.id
        
        # Извлекаем редкость из callback_data
        rarity = callback.data.split("_")[1]  # legendary, epic, rare, common
        
        # Получаем карты пользователя этой редкости
        cards = await get_user_cards_by_rarity(user_id, rarity)
        
        if not cards:
            style = RARITY_STYLES[rarity]
            text = (
                f"{style['emoji']} <b>У вас нет {style['name'].lower()} карт</b>\n\n"
                "🎯 Открывайте больше паков, чтобы пополнить коллекцию!"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 Открыть паки", callback_data="show_shop_packs")],
                [InlineKeyboardButton(text="↩️ Назад к редкостям", callback_data="my_cards")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])
            
            # Удаляем предыдущее сообщение и отправляем новое
            try:
                await callback.message.delete()
            except:
                pass
            
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return
        
        # Сохраняем карты в состоянии для пагинации
        await state.update_data(
            current_rarity=rarity,
            all_cards=cards,
            current_page=0
        )
        
        await show_cards_page(callback, state)
        
    except Exception as e:
        print(f"Error in show_cards_list: {e}")
        await callback.answer("❌ Ошибка загрузки карт", show_alert=True)

async def show_cards_page(callback: CallbackQuery, state: FSMContext):
    """Показывает страницу с картами"""
    try:
        data = await state.get_data()
        cards = data['all_cards']
        current_page = data['current_page']
        rarity = data['current_rarity']
        style = RARITY_STYLES[rarity]
        
        # Разбиваем на страницы по 5 карт
        page_size = 5
        total_pages = (len(cards) + page_size - 1) // page_size
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(cards))
        page_cards = cards[start_idx:end_idx]
        
        text = (
            f"{style['emoji']} <b>{style['name']} карты</b>\n\n"
            f"📊 Всего игроков: {len(cards)}\n\n"
            f"📄 Страница {current_page + 1}/{total_pages}\n"
        )
        
        # Создаем кнопки для карт
        keyboard_buttons = []
        for i, card in enumerate(page_cards, start=1):
            button_text = f"{i}. {card['player_name']}"
            if card['copies_count'] > 1:
                button_text += f" (x{card['copies_count']})"
            
            keyboard_buttons.append([
                InlineKeyboardButton(text=button_text, callback_data=f"card_{card['id']}")
            ])
        
        # Кнопки навигации
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data="cards_prev"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="cards_info"))
        
        if current_page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data="cards_next"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        # Кнопки возврата
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="↩️ Назад к редкостям", callback_data="my_cards")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await state.set_state(CardsStates.viewing_cards_list)
        
        # Удаляем предыдущее сообщение и отправляем новое
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error in show_cards_page: {e}")
        await callback.answer("❌ Ошибка загрузки страницы", show_alert=True)

@router.callback_query(F.data.in_(["cards_prev", "cards_next"]), CardsStates.viewing_cards_list)
async def navigate_cards(callback: CallbackQuery, state: FSMContext):
    """Навигация по страницам карт"""
    try:
        data = await state.get_data()
        current_page = data['current_page']
        total_pages = (len(data['all_cards']) + 4) // 5  # 5 карт на страницу
        
        if callback.data == "cards_prev":
            new_page = max(0, current_page - 1)
        else:
            new_page = min(current_page + 1, total_pages - 1)
        
        await state.update_data(current_page=new_page)
        
        # Удаляем текущее сообщение и показываем новое
        try:
            await callback.message.delete()
        except:
            pass
        
        await show_cards_page(callback, state)
        await callback.answer()
        
    except Exception as e:
        print(f"Error in navigate_cards: {e}")
        await callback.answer("❌ Ошибка навигации", show_alert=True)

@router.callback_query(F.data.startswith("card_"), CardsStates.viewing_cards_list)
async def show_card_details(callback: CallbackQuery, state: FSMContext):
    """Показывает детальную информацию о карте с фотографией"""
    try:
        user_id = callback.from_user.id
        card_id = int(callback.data.split("_")[1])
        
        # Получаем детальную информацию о карте
        card_details = await get_user_card_details(user_id, card_id)
        
        if not card_details:
            await callback.answer("❌ Карта не найдена", show_alert=True)
            return
        
        card_info = card_details['card_info']
        style = RARITY_STYLES[card_info['rarity']]
        
        # Формируем текст
        card_text = (
            f"{style['emoji']} <b>{card_info['player_name']}</b>\n\n"
            f"🏷️ <b>Редкость:</b> {style['name']}\n"
            f"🎯 <b>Рейтинг:</b> {int(card_info['weight'])}\n"
            f"📊 <b>Копий у вас:</b> {card_details['copies_count']}\n"
        )
        
        if card_details['best_serial_number']:
            card_text += f"🔢 <b>Лучший номер:</b> #{card_details['best_serial_number']}\n"
        
        if card_details['collection_name']:
            card_text += f"🏆 <b>Коллекция:</b> {card_details['collection_name']}\n"
        
        card_text += f"📅 <b>Первое получение:</b> {card_details['first_obtained'].strftime('%d.%m.%Y')}\n\n"
        
        # Показываем все порядковые номера, если их немного
        if card_details['copies_count'] <= 10:
            card_text += "🔢 <b>Ваши номера:</b> "
            serials = [f"#{s['serial_number']}" for s in card_details['serial_numbers']]
            card_text += ", ".join(serials)
        else:
            card_text += f"🔢 <b>Номера:</b> Показаны первые 10 из {card_details['copies_count']}\n"
            serials = [f"#{s['serial_number']}" for s in card_details['serial_numbers'][:10]]
            card_text += ", ".join(serials) + "..."

        # Получаем текущую редкость из состояния для кнопки возврата
        data = await state.get_data()
        current_rarity = data.get('current_rarity', card_info['rarity'])
        
        # Клавиатура
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад к списку", callback_data=f"cards_{current_rarity}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
        
        await state.set_state(CardsStates.viewing_card_details)
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        # Проверяем наличие фото карты
        image_path = f"players/{card_info['rarity']}/{card_info['uniq_name']}.jpg"
        
        if os.path.exists(image_path):
            # Отправляем сообщение с фото
            photo = FSInputFile(image_path)
            await callback.message.answer_photo(
                photo=photo,
                caption=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Отправляем текстовое сообщение если фото нет
            await callback.message.answer(
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        print(f"Error in show_card_details: {e}")
        await callback.answer("❌ Ошибка загрузки карты", show_alert=True)

@router.callback_query(F.data.startswith("cards_"), CardsStates.viewing_card_details)
async def back_to_cards_list(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку карт из детального просмотра"""
    try:
        # Извлекаем редкость из callback_data
        parts = callback.data.split("_")
        if len(parts) >= 2:
            rarity = parts[1]
            await state.update_data(current_rarity=rarity)
            
            # Удаляем сообщение с картой
            try:
                await callback.message.delete()
            except:
                pass
            
            await show_cards_list(callback, state)
        else:
            await callback.answer("❌ Ошибка навигации")
            
    except Exception as e:
        print(f"Error in back_to_cards_list: {e}")
        await callback.answer("❌ Ошибка возврата", show_alert=True)

@router.callback_query(F.data == "back_to_menu", CardsStates.viewing_card_details)
async def back_to_menu_from_cards(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из просмотра карт"""
    await state.clear()
    try:
        # Удаляем сообщение с картой
        await callback.message.delete()
    except:
        pass
    
    try:
        # Импортируем здесь чтобы избежать циклического импорта
        from handlers.main_menu import show_menu
        # Отправляем новое сообщение с меню
        await show_menu(callback, state)
    except Exception as e:
        print(f"Error returning to menu from cards: {e}")
        await callback.answer("❌ Ошибка загрузки меню", show_alert=True)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_general(callback: CallbackQuery, state: FSMContext):
    """Общий обработчик возврата в главное меню"""
    current_state = await state.get_state()
    
    if current_state == CardsStates.viewing_card_details:
        # Если мы в состоянии просмотра карты, используем специальный обработчик
        await back_to_menu_from_cards(callback, state)
    else:
        # Для всех других состояний - обычный возврат
        await state.clear()
        try:
            # Удаляем текущее сообщение
            await callback.message.delete()
        except:
            pass
        
        try:
            # Импортируем здесь чтобы избежать циклического импорта
            from handlers.main_menu import show_menu
            # Отправляем новое сообщение с меню
            await show_menu(callback, state)
        except Exception as e:
            print(f"Error returning to menu: {e}")
            await callback.answer("❌ Ошибка загрузки меню", show_alert=True)