from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.markdown import html_decoration as hd
from typing import List

from db.user_queries import *

router = Router()

# Состояния для маркета
class MarketStates(StatesGroup):
    selecting_card = State()
    setting_price = State()
    editing_price = State()
    searching_card = State()
    filtering_rarity = State()
    viewing_history = State()


# Меню маркета
@router.callback_query(F.data == "market_menu")
async def market_menu(callback: CallbackQuery, state: FSMContext):
    text = """<b>🏪 Футбольный Маркет</b>

📊 <i>Торговая площадка для настоящих коллекционеров</i>

🎯 Выберите действие:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Выставить на продажу", callback_data="market_sell")],
        [InlineKeyboardButton(text="📋 Мои предложения", callback_data="market_my_listings")],
        [InlineKeyboardButton(text="🛒 Обзор рынка", callback_data="market_browse")],
        [InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="market_search")],
        [InlineKeyboardButton(text="📈 Мои сделки", callback_data="market_my_deals")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

# 1. Выставить игрока на продажу - НОВАЯ ВЕРСИЯ С СПИСКОМ
@router.callback_query(F.data == "market_sell")
async def market_sell_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем количество активных объявлений
    active_listings_count = await get_user_active_listings_count(user_id)
    if active_listings_count >= 5:
        await callback.answer(
            "❌ У вас уже 5 активных объявлений!\n"
            "Снимите одно из объявлений, чтобы выставить новое.",
            show_alert=True
        )
        return
    
    user_cards = await get_user_cards_for_market(user_id)
    
    if not user_cards:
        await callback.answer("У вас нет карточек для продажи", show_alert=True)
        return
    
    available_cards = [card for card in user_cards if card['already_listed'] == 0]
    
    if not available_cards:
        await callback.answer("Все ваши карточки уже выставлены на продажу", show_alert=True)
        return
    
    await state.update_data(available_cards=available_cards, current_page=0, filter_rarity='all')
    await show_cards_list(callback, state)

async def show_cards_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    available_cards = data['available_cards']
    current_page = data['current_page']
    filter_rarity = data.get('filter_rarity', 'all')
    
    # Получаем количество активных объявлений
    user_id = callback.from_user.id
    active_listings_count = await get_user_active_listings_count(user_id)
    
    # Фильтрация по редкости
    if filter_rarity != 'all':
        filtered_cards = [card for card in available_cards if card['rarity'] == filter_rarity]
    else:
        filtered_cards = available_cards
    
    start_idx = current_page * 5
    end_idx = min(start_idx + 5, len(filtered_cards))
    page_cards = filtered_cards[start_idx:end_idx]
    
    if not page_cards:
        await callback.answer("🎴 Карточки не найдены", show_alert=True)
        return
    
    text = f"""<b>🎴 Выбор карточки для продажи</b>

📊 Активных объявлений: {active_listings_count}/5
📄 Страница {current_page + 1}/{(len(filtered_cards) - 1) // 5 + 1}
🎯 Фильтр: {get_rarity_display_name(filter_rarity)}

<blockquote>"""
    
    for i, card in enumerate(page_cards, start=1):
        emoji = get_rarity_emoji(card['rarity'])
        text += f"""
{emoji} <b>{card['player_name']}</b>
├ Редкость: {card['rarity'].capitalize()}
├ Коллекция: {card['collection_name']}
├ Вес: {card['weight']}
├ Номер: #{card['serial_number']}
└ ID: <code>{card['user_card_id']}</code>

"""
    
    text += "</blockquote>"
    
    keyboard_buttons = []
    
    # Кнопки выбора карточек
    for i, card in enumerate(page_cards, start=1):
        emoji = get_rarity_emoji(card['rarity'])
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {card['player_name'][:12]}...", 
                callback_data=f"select_card_{card['user_card_id']}"
            )
        ])
    
    # Навигация
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⏪", callback_data="prev_cards_page"))
    
    if end_idx < len(filtered_cards):
        nav_buttons.append(InlineKeyboardButton(text="⏩", callback_data="next_cards_page"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    # Фильтры
    filter_buttons = [
        InlineKeyboardButton(text="⭐", callback_data="market_cards_filter_all"),
        InlineKeyboardButton(text="⚪", callback_data="market_cards_filter_common"),
        InlineKeyboardButton(text="🔵", callback_data="market_cards_filter_rare"),
        InlineKeyboardButton(text="🟣", callback_data="market_cards_filter_epic"),
        InlineKeyboardButton(text="🟡", callback_data="market_cards_filter_legendary")
    ]

    keyboard_buttons.append(filter_buttons)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "market_my_deals")
async def show_my_deals(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    history = await get_user_sale_history(user_id)
    
    text = """<b>📈 История моих сделок</b>

💼 <i>Ваши продажи и покупки на маркете</i>"""
    
    # Продажи
    if history['sales']:
        text += "\n\n💰 <b>Продажи:</b>\n<blockquote>"
        for sale in history['sales'][:5]:
            text += f"""
🎯 {sale['player_name']}
├ 💰 {sale['price']} монет
├ 👤 {sale['buyer_name']}
└ 📅 {sale['sold_at'].strftime('%d.%m.%Y')}
"""
        text += "</blockquote>"
    else:
        text += "\n\n📭 <i>У вас еще не было продаж</i>"
    
    # Покупки
    if history['purchases']:
        text += "\n\n🛒 <b>Покупки:</b>\n<blockquote>"
        for purchase in history['purchases'][:5]:
            text += f"""
🎯 {purchase['player_name']}
├ 💰 {purchase['price']} монет
├ 👤 {purchase['seller_name']}
└ 📅 {purchase['sold_at'].strftime('%d.%m.%Y')}
"""
        text += "</blockquote>"
    else:
        text += "\n\n📭 <i>У вас еще не было покупок</i>"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("market_cards_filter_"))
async def filter_cards_rarity(callback: CallbackQuery, state: FSMContext):
    filter_type = callback.data.split("_")[3]  # Измените индекс
    await state.update_data(filter_rarity=filter_type, current_page=0)
    await show_cards_list(callback, state)

@router.callback_query(F.data.startswith("select_card_"))
async def select_card_for_sale(callback: CallbackQuery, state: FSMContext):
    try:
        user_card_id = int(callback.data.split("_")[2])  # Конвертируем в int
        await state.update_data(selected_card_id=user_card_id)
        await state.set_state(MarketStates.setting_price)
        
        data = await state.get_data()
        available_cards = data['available_cards']
        card = next((c for c in available_cards if c['user_card_id'] == user_card_id), None)
        
        if card:
            text = f"""<b>🎴 Установка цены</b>

<blockquote>
<b>{card['player_name']}</b>
├ Редкость: {get_rarity_emoji(card['rarity'])} {card['rarity'].capitalize()}
├ Коллекция: {card['collection_name']}
├ Вес: {card['weight']}
├ Номер: #{card['serial_number']}
└ ID: <code>{card['user_card_id']}</code>
</blockquote>

💵 Введите цену продажи:
⚠️ <i>Максимальная цена: 200,000 монет</i>"""
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="market_sell")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback.answer("Ошибка выбора карточки", show_alert=True)
    except ValueError:
        await callback.answer("Ошибка формата ID карточки", show_alert=True)

@router.message(MarketStates.setting_price)
async def set_card_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть положительным числом")
            return
        
        # Добавляем проверку максимальной цены
        if price > 200000:
            await message.answer("❌ Максимальная цена для продажи - 200,000 монет")
            return
            
        data = await state.get_data()
        user_card_id = data['selected_card_id']
        
        # Убедимся, что user_card_id - целое число
        if isinstance(user_card_id, str):
            try:
                user_card_id = int(user_card_id)
            except ValueError:
                await message.answer("❌ Ошибка: неверный формат ID карточки")
                return
        
        result = await create_market_listing(message.from_user.id, user_card_id, price)
        
        if result:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏪 Вернуться в маркет", callback_data="market_menu")]
            ])
            await message.answer(
                f"✅ Карточка успешно выставлена на продажу за <b>{price} монет</b>!\n"
                f"ID карточки: <code>{user_card_id}</code>",
                reply_markup=keyboard
            )
            await state.clear()
        else:
            await message.answer("❌ Ошибка при создании объявления")
            
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число")

# 2. Мои предложения на продажу - НОВАЯ ВЕРСИЯ С СПИСКОМ
@router.callback_query(F.data == "market_my_listings")
async def show_my_listings(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    listings = await get_user_market_listings(user_id)
    
    if not listings:
        await callback.answer("У вас нет активных предложений", show_alert=True)
        return
    
    await state.update_data(my_listings=listings, current_page=0)
    await show_listings_list(callback, state)

async def show_listings_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    listings = data['my_listings']
    current_page = data['current_page']
    
    start_idx = current_page * 5
    end_idx = min(start_idx + 5, len(listings))
    page_listings = listings[start_idx:end_idx]
    
    if not page_listings:
        await callback.answer("Предложения не найдены", show_alert=True)
        return
    
    text = f"""<b>📋 Мои предложения на продажу</b>

📄 Страница {current_page + 1}/{(len(listings) - 1) // 5 + 1}

<blockquote>"""
    
    for i, listing in enumerate(page_listings, start=1):
        emoji = get_rarity_emoji(listing['rarity'])
        text += f"""
{emoji} <b>{listing['player_name']}</b>
├ 💵 <b>Цена:</b> {listing['price']} монет
├ 🏷️ <b>Коллекция:</b> {listing['collection_name']}
├ 🎯 <b>Рейтинг:</b> {int(listing['weight'])}
├ 🔢 <b>Номер:</b> #{listing['serial_number']}
└ 🆔 <b>ID:</b> <code>{listing['card_id']}</code>

"""
    
    text += "</blockquote>"
    
    keyboard_buttons = []
    
    for i, listing in enumerate(page_listings, start=1):
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"#{i} {listing['player_name'][:12]}...", 
                callback_data=f"view_listing_{listing['id']}"
            )
        ])
    
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data="prev_listings_page"))
    
    if end_idx < len(listings):
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data="next_listings_page"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="market_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("view_listing_"))
async def view_listing_detail(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split("_")[2])
    
    data = await state.get_data()
    listings = data['my_listings']
    listing = next((l for l in listings if l['id'] == listing_id), None)
    
    if not listing:
        await callback.answer("Предложение не найдено", show_alert=True)
        return
    
    text = f"""<b>📋 Мое предложение #{listing['id']}</b>

<blockquote>👤 <b>{listing['player_name']}</b>
{get_rarity_emoji(listing['rarity'])} <b>Редкость:</b> {listing['rarity'].capitalize()}
🏷️ <b>Коллекция:</b> {listing['collection_name']}
🎯 <b>Рейтинг:</b> {int(listing['weight'])}
🔢 <b>Номер:</b> #{listing['serial_number']}
🆔 <b>ID:</b> <code>{listing['card_id']}</code>
💵 <b>Цена:</b> {listing['price']} монет
📅 <b>Выставлено:</b> {listing['created_at'].strftime('%d.%m.%Y %H:%M')}
</blockquote>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить цену", callback_data=f"edit_price_{listing['id']}")],
        [InlineKeyboardButton(text="❌ Снять с продажи", callback_data=f"remove_listing_{listing['id']}")],
        [InlineKeyboardButton(text="🔙 К списку", callback_data="market_my_listings")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("edit_price_"))
async def edit_listing_price(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split("_")[2])
    await state.update_data(editing_listing_id=listing_id)
    await state.set_state(MarketStates.editing_price)
    
    await callback.message.edit_text(
        "💵 Введите новую цену для этого предложения:\n"
        "⚠️ <i>Максимальная цена: 200,000 монет</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="market_my_listings")]
        ])
    )

@router.message(MarketStates.editing_price)
async def update_listing_price(message: Message, state: FSMContext):
    try:
        new_price = int(message.text)
        if new_price <= 0:
            await message.answer("❌ Цена должна быть положительным числом")
            return
        
        # Добавляем проверку максимальной цены
        if new_price > 200000:
            await message.answer("❌ Максимальная цена для продажи - 200,000 монет")
            return
            
        data = await state.get_data()
        listing_id = data['editing_listing_id']
        
        await update_market_listing_price(listing_id, message.from_user.id, new_price)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Вернуться в маркет", callback_data="market_menu")]
        ])
        
        await message.answer(
            f"✅ Цена успешно изменена на {new_price} монет!",
            reply_markup=keyboard
        )
        await state.clear()
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число")

@router.callback_query(F.data.startswith("remove_listing_"))
async def remove_listing(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split("_")[2])
    
    await remove_market_listing(listing_id, callback.from_user.id)
    await callback.answer("✅ Предложение снято с продажи", show_alert=True)
    await show_my_listings(callback, state)

# 3. Просмотр маркета - ИСПРАВЛЕННАЯ ВЕРСИЯ
@router.callback_query(F.data == "market_browse")
async def browse_market(callback: CallbackQuery, state: FSMContext):
    await state.update_data(market_page=0, market_filter='all')
    await show_market_page(callback, state)

async def show_market_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('market_page', 0)
    rarity_filter = data.get('market_filter', 'all')
    
    # Исключаем предложения текущего пользователя
    listings = await get_market_listings(page, 5, rarity_filter, callback.from_user.id)
    total_count = await get_total_market_listings_count(rarity_filter, callback.from_user.id)
    
    if not listings:
        text = """<b>🎪 Футбольный Маркет</b>

📊 На рынке пока нет предложений
🎯 Будьте первым, кто выставит карточку!"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Выставить карточку", callback_data="market_sell")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        return
    
    text = f"""<b>🎪 Футбольный Маркет</b>

📊 Предложения: {page * 5 + 1}-{min((page + 1) * 5, total_count)} из {total_count}
🎯 Фильтр: {get_rarity_display_name(rarity_filter)}

<blockquote>"""
    
    for i, listing in enumerate(listings, start=1):
        emoji = get_rarity_emoji(listing['rarity'])
        text += f"""
{emoji} <b>{listing['player_name']}</b>
├ 💵 <b>Цена:</b> 🪙 {listing['price']:,}
├ 👤 <b>Продавец:</b> {listing['seller_name']}
├ 🏷️ <b>Коллекция:</b> {listing['collection_name']}
├ 🎯 <b>Рейтинг:</b> {int(listing['weight'])}
└ 🔢 <b>Номер:</b> #{listing['serial_number']}
"""
    
    text += "</blockquote>"
    
    keyboard_buttons = []
    
    for i, listing in enumerate(listings, start=1):
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"🛒 Купить #{i} - 🪙 {listing['price']:,}", 
                callback_data=f"buy_listing_{listing['id']}"
            )
        ])
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⏪", callback_data="market_prev"))
    
    if (page + 1) * 5 < total_count:
        nav_buttons.append(InlineKeyboardButton(text="⏩", callback_data="market_next"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    filter_buttons = [
        InlineKeyboardButton(text="⭐", callback_data="market_filter_all"),
        InlineKeyboardButton(text="⚪", callback_data="market_filter_common"),
        InlineKeyboardButton(text="🔵", callback_data="market_filter_rare"),
        InlineKeyboardButton(text="🟣", callback_data="market_filter_epic"),
        InlineKeyboardButton(text="🟡", callback_data="market_filter_legendary")
    ]
    keyboard_buttons.append(filter_buttons)
    
    action_buttons = [
        InlineKeyboardButton(text="📤 Продать", callback_data="market_sell"),
        InlineKeyboardButton(text="🏠 Меню", callback_data="market_menu")
    ]
    keyboard_buttons.append(action_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "market_history")
async def market_history_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        """
    📈 <b>История продаж</b>
    
    📝 Введите ID карточки для просмотра её истории продаж:
    """,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="market_menu")]
        ])
    )
    await state.set_state(MarketStates.viewing_history)

@router.message(MarketStates.viewing_history)
async def show_sale_history(message: Message, state: FSMContext):
    try:
        card_id = int(message.text)
        history = await get_sale_history(card_id)
        
        if not history:
            await message.answer("""
    📈 <b>История продаж</b>
    
    ❌ Для этой карточки нет истории продаж
            """)
            return
        
        text = f"""
    📈 <b>История продаж карточки #{card_id}</b>
    
    📊 Всего сделок: {len(history)}
    ━━━━━━━━━━━━━━━━━━━━━
    """
        
        for i, sale in enumerate(history, start=1):
            text += f"""
    🎯 <b>Сделка #{i}</b>
    ├ Дата: {sale['sold_at'].strftime('%d.%m.%Y %H:%M')}
    ├ Цена: 🪙 {sale['price']:,}
    ├ Продавец: 👤 {sale['seller_name'] or 'Unknown'}
    └ Покупатель: 👤 {sale['buyer_name'] or 'Unknown'}
    
    """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")],
            [InlineKeyboardButton(text="🔄 Проверить другую", callback_data="market_history")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.clear()
        
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID карточки")

@router.callback_query(F.data.startswith("buy_listing_"))
async def confirm_purchase(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split("_")[2])
    
    # Получаем информацию об объявлении
    listing = await get_market_listing_by_id(listing_id)
    
    if not listing:
        await callback.answer("❌ Объявление не найдено", show_alert=True)
        return
    
    text = f"""<b>🛒 Подтверждение покупки</b>

<blockquote>
👤 <b>{listing['player_name']}</b>
{get_rarity_emoji(listing['rarity'])} <b>Редкость:</b> {listing['rarity'].capitalize()}
🏷️ <b>Коллекция:</b> {listing['collection_name']}
🎯 <b>Рейтинг:</b> {int(listing['weight'])}
🔢 <b>Номер:</b> #{listing['serial_number']}
👤 <b>Продавец:</b> {listing['seller_name']}
💵 <b>Цена:</b> {listing['price']} монет
</blockquote>

<b>Вы уверены, что хотите купить эту карточку?</b>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, купить", callback_data=f"confirm_buy_{listing_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="market_browse")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("confirm_buy_"))
async def buy_listing(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split("_")[2])
    
    success, message = await buy_market_listing(listing_id, callback.from_user.id)
    
    if success:
        text = """<b>✅ Покупка успешна!</b>

🎉 Карточка добавлена в вашу коллекцию
📦 Средства списаны с баланса"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🃏 Мои карточки", callback_data="my_cards")],
            [InlineKeyboardButton(text="🛒 К маркету", callback_data="market_browse")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)
        await browse_market(callback, state)

# 4. Поиск карточки по ID - ИСПРАВЛЕННАЯ ВЕРСИЯ
@router.callback_query(F.data == "market_search")
async def search_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MarketStates.searching_card)
    
    text = """<b>🔍 Поиск карточки на маркете</b>

🎯 <i>Найдите нужную карточку по её уникальному ID</i>

💡 <b>Как найти ID карточки?</b>
• Попросите владельца карточки поделиться ID
• ID отображается в информации о карточке
• Это число, например: 123

📝 <b>Введите ID карточки:</b>"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="market_menu")]
        ])
    )

@router.message(MarketStates.searching_card)
async def search_card_by_id(message: Message, state: FSMContext):
    try:
        card_id = int(message.text)
        listing = await get_market_listing_by_user_card_id(card_id)
        
        if not listing:
            await message.answer("""<b>❌ Карточка не найдена</b>

Возможные причины:
• Карточка уже продана
• Карточка снята с продажи
• Неверный ID карточки

Проверьте ID и попробуйте снова""")
            return
        
        text = f"""<b>✅ Карточка найдена!</b>

<blockquote>
👤 <b>{listing['player_name']}</b>
{get_rarity_emoji(listing['rarity'])} <b>Редкость:</b> {listing['rarity'].capitalize()}
🏷️ <b>Коллекция:</b> {listing['collection_name']}
🎯 <b>Рейтинг:</b> {int(listing['weight'])}
🔢 <b>Номер:</b> #{listing['serial_number']}
👤 <b>Продавец:</b> {listing['seller_name']}
💵 <b>Цена:</b> {listing['price']} монет
📅 <b>Выставлено:</b> {listing['created_at'].strftime('%d.%m.%Y %H:%M')}
</blockquote>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        if listing['user_id'] != message.from_user.id:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="🛒 Купить сейчас", callback_data=f"buy_listing_{listing['id']}")
            ])
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🔍 Новый поиск", callback_data="market_search"),
            InlineKeyboardButton(text="🏠 В меню", callback_data="market_menu")
        ])
        
        await message.answer(text, reply_markup=keyboard)
        await state.clear()
        
    except ValueError:
        await message.answer("""<b>❌ Неверный формат</b>

Пожалуйста, введите <b>число</b> - ID карточки.

Пример: 123 или 456""")

# Вспомогательные функции
def get_rarity_emoji(rarity: str) -> str:
    emoji_map = {
        'common': '⚪',
        'rare': '🔵', 
        'epic': '🟣',
        'legendary': '🟡'
    }
    return emoji_map.get(rarity, '⚪')

def get_rarity_display_name(rarity: str) -> str:
    names = {
        'all': 'Все',
        'common': '⚪ Обычные',
        'rare': '🔵 Редкие', 
        'epic': '🟣 Эпические',
        'legendary': '🟡 Легендарные'
    }
    return names.get(rarity, 'Все')

# Обработчики навигации для списков
@router.callback_query(F.data == "prev_cards_page")
async def prev_cards_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_page = data['current_page']
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        await show_cards_list(callback, state)
    else:
        await callback.answer("Это первая страница")

@router.callback_query(F.data == "next_cards_page")
async def next_cards_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    available_cards = data['available_cards']
    current_page = data['current_page']
    
    if (current_page + 1) * 5 < len(available_cards):
        await state.update_data(current_page=current_page + 1)
        await show_cards_list(callback, state)
    else:
        await callback.answer("Это последняя страница")

@router.callback_query(F.data == "prev_listings_page")
async def prev_listings_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_page = data['current_page']
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        await show_listings_list(callback, state)
    else:
        await callback.answer("Это первая страница")

@router.callback_query(F.data == "next_listings_page")
async def next_listings_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    listings = data['my_listings']
    current_page = data['current_page']
    
    if (current_page + 1) * 5 < len(listings):
        await state.update_data(current_page=current_page + 1)
        await show_listings_list(callback, state)
    else:
        await callback.answer("Это последняя страница")

@router.callback_query(F.data == "market_prev")
async def market_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('market_page', 0)
    if page > 0:
        await state.update_data(market_page=page - 1)
        await show_market_page(callback, state)
    else:
        await callback.answer("Это первая страница")

@router.callback_query(F.data == "market_next")
async def market_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('market_page', 0)
    rarity_filter = data.get('market_filter', 'all')
    total_count = await get_total_market_listings_count(rarity_filter)
    
    if (page + 1) * 5 < total_count:
        await state.update_data(market_page=page + 1)
        await show_market_page(callback, state)
    else:
        await callback.answer("Это последняя страница")

# Обработчики фильтров
@router.callback_query(F.data.startswith("market_filter_"))
async def apply_market_filter(callback: CallbackQuery, state: FSMContext):
    filter_type = callback.data.split("_")[2]
    await state.update_data(market_filter=filter_type, market_page=0)
    await show_market_page(callback, state)