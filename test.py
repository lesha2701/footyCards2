from db.pool import get_db_pool
from datetime import *
import pytz
import json
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router, F, Bot
import random

FREE_PACK_COOLDOWN = 3
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

async def get_user_by_id(user_id: int):
    """Получаем пользователя по ID со статистикой"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            u.*,
            COUNT(uc.id) as cards_count,
            COUNT(DISTINCT uc.card_id) as unique_cards
        FROM users u
        LEFT JOIN user_cards uc ON u.user_id = uc.user_id
        WHERE u.user_id = $1
        GROUP BY u.user_id
        """
        return await conn.fetchrow(query, user_id)

async def create_user(user_id: int, username: str, balance: int = 100):
    """Создаем нового пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO users (user_id, username, balance) 
        VALUES ($1, $2, $3) 
        RETURNING *
        """
        return await conn.fetchrow(query, user_id, username, balance)

async def update_user_balance(user_id: int, balance_change: int):
    """Обновляем баланс пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE users 
        SET balance = balance + $2 
        WHERE user_id = $1 
        RETURNING balance
        """
        return await conn.fetchval(query, user_id, balance_change)

async def get_user_stats(user_id: int):
    """Получаем полную статистику пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            u.user_id,
            u.username,
            u.balance,
            COUNT(uc.id) as total_cards,
            COUNT(DISTINCT uc.card_id) as unique_cards,
            COUNT(DISTINCT CASE WHEN c.rarity = 'legendary' THEN uc.card_id END) as legendary_cards,
            COUNT(DISTINCT CASE WHEN c.rarity = 'epic' THEN uc.card_id END) as epic_cards
        FROM users u
        LEFT JOIN user_cards uc ON u.user_id = uc.user_id
        LEFT JOIN cards c ON uc.card_id = c.id
        WHERE u.user_id = $1
        GROUP BY u.user_id
        """
        return await conn.fetchrow(query, user_id)

async def check_user_can_open_pack(user_id: int, pack_cost: int) -> bool:
    """Проверяет, может ли пользователь открыть пак"""
    user = await get_user_by_id(user_id)
    return user and user['balance'] >= pack_cost

async def update_last_pack_time(user_id: int):
    """Обновляет время последнего открытия бесплатного пака в московском времени"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Сохраняем текущее московское время
        moscow_time = datetime.now(MOSCOW_TZ)
        query = "UPDATE users SET last_free_pack = $1 WHERE user_id = $2"
        await conn.execute(query, moscow_time, user_id)

async def can_open_free_pack(user_id: int):
    """Проверяет, можно ли открыть бесплатный пак по московскому времени"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT last_free_pack FROM users WHERE user_id = $1"
        last_pack_time = await conn.fetchval(query, user_id)
        
        if not last_pack_time:
            return True, 0
        
        # Текущее время в Москве
        now_moscow = datetime.now(MOSCOW_TZ)
        
        # Конвертируем время из базы в московское
        if last_pack_time.tzinfo is None:
            last_pack_time_utc = last_pack_time.replace(tzinfo=timezone.utc)
            last_pack_time_moscow = last_pack_time_utc.astimezone(MOSCOW_TZ)
        else:
            last_pack_time_moscow = last_pack_time.astimezone(MOSCOW_TZ)
        
        time_passed = now_moscow - last_pack_time_moscow
        cooldown = timedelta(hours=FREE_PACK_COOLDOWN)
        
        if time_passed >= cooldown:
            return True, 0
        else:
            time_left = (cooldown - time_passed).total_seconds()
            # Форматируем время без .0
            hours_left = int(time_left // 3600)
            minutes_left = int((time_left % 3600) // 60)
            return False, time_left
        
async def update_user_balance(user_id: int, amount: int):
    """Обновляет баланс пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            amount, user_id
        )

async def update_user_trophies(user_id: int, amount: int):
    """Обновляет трофеи пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET trophies = trophies + $1 WHERE user_id = $2",
            amount, user_id
        )

async def get_user_balance(user_id: int):
    """Получает баланс пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT balance FROM users WHERE user_id = $1",
            user_id
        )

async def save_game_result(user_id: int, game_type: str, result: str, 
                          bet_amount: int, win_amount: int, 
                          player_score: int, opponent_score: int):
    """Сохраняет результат игры"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO game_results 
            (user_id, game_type, result, bet_amount, win_amount, 
             player_score, opponent_score, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        """, user_id, game_type, result, bet_amount, win_amount, 
           player_score, opponent_score)
        
# Дополнительные запросы для маркета
async def create_market_listing(user_id: int, user_card_id: int, price: int):
    """Создает объявление о продаже карточки на маркете"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем, не выставлена ли уже эта карточка пользователем
        existing_query = """
        SELECT id FROM market_listings 
        WHERE card_id = $1 AND is_sold = FALSE AND user_id = $2
        """
        existing = await conn.fetchval(existing_query, user_card_id, user_id)
        
        if existing:
            return None, "Эта карточка уже выставлена вами на продажу"
        
        # Дополнительная проверка: не выставлена ли карточка кем-то другим
        # (хотя это маловероятно, так как карточка принадлежит пользователю)
        existing_global_query = """
        SELECT id FROM market_listings 
        WHERE card_id = $1 AND is_sold = FALSE
        """
        existing_global = await conn.fetchval(existing_global_query, user_card_id)
        
        if existing_global:
            return None, "Эта карточка уже выставлена на продажу другим пользователем"
            
        query = """
        INSERT INTO market_listings (user_id, card_id, price, created_at)
        VALUES ($1, $2, $3, NOW())
        RETURNING id
        """
        try:
            listing_id = await conn.fetchval(query, user_id, user_card_id, price)
            return listing_id, "Объявление успешно создано"
        except Exception as e:
            print(f"Error creating market listing: {e}")
            return None, f"Ошибка при создании объявления: {e}"
        
async def record_sale_history(user_card_id: int, seller_id: int, buyer_id: int, price: int):
    """Записывает историю продажи карточки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем предыдущих владельцев (как строки)
        previous_owners_query = """
        SELECT array_agg(DISTINCT seller_id::text) 
        FROM market_sales_history 
        WHERE user_card_id = $1
        """
        previous_owners = await conn.fetchval(previous_owners_query, user_card_id) or []
        
        # Добавляем текущего продавца как строку
        if str(seller_id) not in previous_owners:
            previous_owners.append(str(seller_id))
        
        query = """
        INSERT INTO market_sales_history 
        (user_card_id, seller_id, buyer_id, price, previous_owners)
        VALUES ($1, $2, $3, $4, $5)
        """
        await conn.execute(query, user_card_id, seller_id, buyer_id, price, previous_owners)

async def get_sale_history(user_card_id: int):
    """Получает историю продаж карточки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT msh.*, u1.username as seller_name, u2.username as buyer_name
        FROM market_sales_history msh
        LEFT JOIN users u1 ON msh.seller_id = u1.user_id
        LEFT JOIN users u2 ON msh.buyer_id = u2.user_id
        WHERE msh.user_card_id = $1
        ORDER BY msh.sold_at DESC
        """
        return await conn.fetch(query, user_card_id)

async def remove_market_listing(listing_id: int, user_id: int):
    """Удаляет объявление с маркета (только для владельца)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "DELETE FROM market_listings WHERE id = $1 AND user_id = $2"
        return await conn.execute(query, listing_id, user_id)

async def update_market_listing_price(listing_id: int, user_id: int, new_price: int):
    """Обновляет цену в объявлении"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE market_listings SET price = $1 WHERE id = $2 AND user_id = $3"
        return await conn.execute(query, new_price, listing_id, user_id)

async def get_user_market_listings(user_id: int):
    """Получает все активные объявления пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT ml.*, c.player_name, c.rarity, c.uniq_name, c.weight, 
               uc.serial_number, col.name as collection_name
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN collections col ON c.collection_id = col.id
        WHERE ml.user_id = $1 AND ml.is_sold = FALSE
        ORDER BY ml.created_at DESC
        """
        return await conn.fetch(query, user_id)
    
async def get_market_listings(page: int = 0, limit: int = 10, rarity: str = None, exclude_user_id: int = None):
    """Получает объявления с маркета с пагинацией и фильтрацией"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        base_query = """
        SELECT ml.*, c.player_name, c.rarity, c.uniq_name, c.weight,
               uc.serial_number, u.username as seller_name, col.name as collection_name
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON ml.user_id = u.user_id
        JOIN collections col ON c.collection_id = col.id
        WHERE ml.is_sold = FALSE
        """
        
        params = [limit, page * limit]
        param_count = 2
        
        if rarity and rarity != 'all':
            base_query += f" AND c.rarity = ${param_count + 1}"
            params.append(rarity)
            param_count += 1
        
        # Исключаем предложения текущего пользователя
        if exclude_user_id is not None:
            base_query += f" AND ml.user_id != ${param_count + 1}"
            params.append(exclude_user_id)
            param_count += 1
        
        base_query += " ORDER BY ml.created_at DESC LIMIT $1 OFFSET $2"
        
        return await conn.fetch(base_query, *params)

async def get_market_listing_by_id(listing_id: int):
    """Получает объявление по ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT ml.*, c.player_name, c.rarity, c.uniq_name, c.weight,
               uc.serial_number, u.username as seller_name, col.name as collection_name
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON ml.user_id = u.user_id
        JOIN collections col ON c.collection_id = col.id
        WHERE ml.id = $1
        """
        return await conn.fetchrow(query, listing_id)

async def get_market_listing_by_card_id(card_id: int):
    """Ищет объявление по ID карточки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT ml.*, c.player_name, c.rarity, c.uniq_name, 
               uc.serial_number, u.username as seller_name
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON ml.user_id = u.user_id
        WHERE ml.card_id = $1 AND ml.is_sold = FALSE
        """
        return await conn.fetchrow(query, card_id)

async def buy_market_listing(listing_id: int, buyer_id: int):
    """Покупка карточки с маркета с записью истории"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Получаем информацию об объявлении
            listing = await conn.fetchrow(
                "SELECT * FROM market_listings WHERE id = $1 AND is_sold = FALSE FOR UPDATE",
                listing_id
            )
            
            if not listing:
                return False, "Объявление не найдено или уже продано"
            
            # Проверяем баланс покупателя
            buyer_balance = await conn.fetchval(
                "SELECT balance FROM users WHERE user_id = $1",
                buyer_id
            )
            
            if buyer_balance < listing['price']:
                return False, "Недостаточно средств"
            
            # Обновляем балансы
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                listing['price'], buyer_id
            )
            
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                listing['price'], listing['user_id']
            )
            
            # Передаем карточку новому владельцу
            await conn.execute(
                "UPDATE user_cards SET user_id = $1 WHERE id = $2",
                buyer_id, listing['card_id']
            )
            
            # Записываем историю продажи
            await record_sale_history(listing['card_id'], listing['user_id'], buyer_id, listing['price'])
            
            # Помечаем объявление как проданное
            await conn.execute(
                "UPDATE market_listings SET is_sold = TRUE, buyer_id = $1, sold_at = NOW() WHERE id = $2",
                buyer_id, listing_id
            )
            
            return True, "Покупка успешна"

async def get_user_cards_for_market(user_id: int):
    """Получает карточки пользователя, которые можно выставить на продажу"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT uc.id as user_card_id, c.*, uc.serial_number, col.name as collection_name,
               (SELECT COUNT(*) FROM market_listings ml WHERE ml.card_id = uc.id AND ml.is_sold = FALSE) as already_listed
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        JOIN collections col ON c.collection_id = col.id
        WHERE uc.user_id = $1 AND uc.is_locked = FALSE
        ORDER BY 
            CASE c.rarity
                WHEN 'legendary' THEN 1
                WHEN 'epic' THEN 2
                WHEN 'rare' THEN 3
                WHEN 'common' THEN 4
            END,
            c.player_name
        """
        return await conn.fetch(query, user_id)

async def get_total_market_listings_count(rarity: str = None, exclude_user_id: int = None):
    """Получает общее количество активных объявлений с фильтрацией"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        base_query = """
        SELECT COUNT(*) 
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        WHERE ml.is_sold = FALSE
        """
        
        params = []
        
        if rarity and rarity != 'all':
            base_query += " AND c.rarity = $1"
            params.append(rarity)
        
        if exclude_user_id is not None:
            if params:
                base_query += f" AND ml.user_id != ${len(params) + 1}"
            else:
                base_query += " AND ml.user_id != $1"
            params.append(exclude_user_id)
        
        return await conn.fetchval(base_query, *params)
        
async def get_market_listing_by_user_card_id(user_card_id: int):
    """Ищет объявление по ID карточки пользователя с информацией о коллекции"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT ml.*, c.player_name, c.rarity, c.uniq_name, c.weight,
               uc.serial_number, u.username as seller_name, col.name as collection_name
        FROM market_listings ml
        JOIN user_cards uc ON ml.card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON ml.user_id = u.user_id
        JOIN collections col ON c.collection_id = col.id
        WHERE ml.card_id = $1 AND ml.is_sold = FALSE
        """
        return await conn.fetchrow(query, user_card_id)
    
async def get_user_sale_history(user_id: int):
    """Получает историю продаж и покупок пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # История продаж (как продавец)
        sales_query = """
        SELECT msh.*, c.player_name, c.rarity, uc.serial_number,
               u.username as buyer_name
        FROM market_sales_history msh
        JOIN user_cards uc ON msh.user_card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON msh.buyer_id = u.user_id
        WHERE msh.seller_id = $1
        ORDER BY msh.sold_at DESC
        LIMIT 20
        """
        
        # История покупок (как покупатель)
        purchases_query = """
        SELECT msh.*, c.player_name, c.rarity, uc.serial_number,
               u.username as seller_name
        FROM market_sales_history msh
        JOIN user_cards uc ON msh.user_card_id = uc.id
        JOIN cards c ON uc.card_id = c.id
        JOIN users u ON msh.seller_id = u.user_id
        WHERE msh.buyer_id = $1
        ORDER BY msh.sold_at DESC
        LIMIT 20
        """
        
        sales = await conn.fetch(sales_query, user_id)
        purchases = await conn.fetch(purchases_query, user_id)
        
        return {
            'sales': [dict(row) for row in sales],
            'purchases': [dict(row) for row in purchases]
        }
    
    # Добавьте эту функцию в db/user_queries.py
async def get_all_users():
    """Получает всех пользователей из базы данных"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            query = "SELECT user_id, username, balance, last_free_pack, created_at FROM users"
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Ошибка при получении всех пользователей: {e}")
        return []
    
async def get_user_stats(user_id: int):
    """Получает полную статистику пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Основная информация пользователя
        user_query = """
        SELECT username, balance, score, created_at 
        FROM users 
        WHERE user_id = $1
        """
        user_data = await conn.fetchrow(user_query, user_id)
        
        if not user_data:
            return None
        
        # Количество карт
        cards_query = "SELECT COUNT(*) FROM user_cards WHERE user_id = $1"
        total_cards = await conn.fetchval(cards_query, user_id)
        
        # Количество уникальных карт
        unique_cards_query = "SELECT COUNT(DISTINCT card_id) FROM user_cards WHERE user_id = $1"
        unique_cards = await conn.fetchval(unique_cards_query, user_id)
        
        # Статистика тренировок
        training_query = """
        SELECT 
            COUNT(*) as total_trainings,
            COUNT(CASE WHEN success = true THEN 1 END) as successful_trainings,
            COALESCE(SUM(reward_earned), 0) as training_rewards,
            COALESCE(MAX(level), 1) as max_training_level
        FROM training_results 
        WHERE user_id = $1
        """
        training_stats = await conn.fetchrow(training_query, user_id)
        
        # Статистика игр
        games_query = """
        SELECT 
            COUNT(*) as total_games,
            COUNT(CASE WHEN result = 'win' THEN 1 END) as wins,
            COUNT(CASE WHEN result = 'lose' THEN 1 END) as losses,
            COUNT(CASE WHEN result = 'draw' THEN 1 END) as draws,
            COALESCE(SUM(win_amount), 0) as total_winnings,
            COALESCE(SUM(bet_amount), 0) as total_bets
        FROM game_results 
        WHERE user_id = $1
        """
        games_stats = await conn.fetchrow(games_query, user_id)
        
        # Любимые карты
        favorites_query = "SELECT COUNT(*) FROM user_cards WHERE user_id = $1 AND is_favorite = true"
        favorite_cards = await conn.fetchval(favorites_query, user_id)
        
        return {
            'username': user_data['username'],
            'balance': user_data['balance'],
            'score': user_data['score'],
            'created_at': user_data['created_at'],
            'total_cards': total_cards or 0,
            'unique_cards': unique_cards or 0,
            'favorite_cards': favorite_cards or 0,
            'total_trainings': training_stats['total_trainings'] or 0,
            'successful_trainings': training_stats['successful_trainings'] or 0,
            'training_rewards': training_stats['training_rewards'] or 0,
            'max_training_level': training_stats['max_training_level'] or 1,
            'total_games': games_stats['total_games'] or 0,
            'wins': games_stats['wins'] or 0,
            'losses': games_stats['losses'] or 0,
            'draws': games_stats['draws'] or 0,
            'total_winnings': games_stats['total_winnings'] or 0,
            'total_bets': games_stats['total_bets'] or 0
        }
    
async def get_leaderboard(user_id: int, limit: int = 10):
    """Получает топ игроков по очкам и позицию текущего пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем топ игроков
        top_players_query = """
        SELECT user_id, username, score, balance
        FROM users 
        WHERE score > 0
        ORDER BY score DESC 
        LIMIT $1
        """
        top_players = await conn.fetch(top_players_query, limit)
        
        # Получаем позицию текущего пользователя
        user_position_query = """
        SELECT position FROM (
            SELECT user_id, ROW_NUMBER() OVER (ORDER BY score DESC) as position
            FROM users 
            WHERE score > 0
        ) ranked 
        WHERE user_id = $1
        """
        user_position = await conn.fetchval(user_position_query, user_id)
        
        # Получаем общее количество игроков с очками
        total_players_query = "SELECT COUNT(*) FROM users WHERE score > 0"
        total_players = await conn.fetchval(total_players_query)
        
        # Получаем данные текущего пользователя
        user_data_query = "SELECT username, score FROM users WHERE user_id = $1"
        user_data = await conn.fetchrow(user_data_query, user_id)
        
        return {
            'top_players': [dict(player) for player in top_players],
            'user_position': user_position,
            'total_players': total_players,
            'current_user': dict(user_data) if user_data else None
        }
    
async def get_collections_info():
    """Получает информацию о всех коллекциях"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            id,
            name,
            description,
            total_cards,
            cards_opened,
            start_date,
            end_date,
            is_active
        FROM collections 
        WHERE total_cards > 0
        ORDER BY 
            is_active DESC,
            end_date DESC NULLS LAST,
            start_date DESC
        """
        collections = await conn.fetch(query)
        return [dict(collection) for collection in collections]

# Добавим в db/user_queries.py

async def get_user_active_listings_count(user_id: int) -> int:
    """Получает количество активных объявлений пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT COUNT(*) 
        FROM market_listings 
        WHERE user_id = $1 AND is_sold = FALSE
        """
        return await conn.fetchval(query, user_id)

async def get_average_card_price(card_base_id: int) -> float:
    """Получает среднюю цену карточки по истории продаж"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT ROUND(AVG(price)) as avg_price
        FROM market_sales_history msh
        JOIN user_cards uc ON msh.user_card_id = uc.id
        WHERE uc.card_id = $1
        AND msh.sold_at >= NOW() - INTERVAL '30 days'  -- Только за последние 30 дней
        """
        result = await conn.fetchval(query, card_base_id)
        return result if result else None

async def get_card_market_stats(card_base_id: int) -> dict:
    """Получает полную статистику по карточке на рынке"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            COUNT(*) as total_sales,
            ROUND(AVG(price)) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            COUNT(DISTINCT seller_id) as unique_sellers
        FROM market_sales_history msh
        JOIN user_cards uc ON msh.user_card_id = uc.id
        WHERE uc.card_id = $1
        AND msh.sold_at >= NOW() - INTERVAL '30 days'
        """
        return await conn.fetchrow(query, card_base_id)
    
    # Реферальные запросы
async def create_referral(referrer_id: int, referred_id: int):
    """Создает реферальную связь"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO referrals (referrer_id, referred_id) 
        VALUES ($1, $2)
        RETURNING *
        """
        try:
            return await conn.fetchrow(query, referrer_id, referred_id)
        except Exception as e:
            print(f"Ошибка создания реферальной связи: {e}")
            return None

async def get_referral_by_referred(referred_id: int):
    """Получает реферальную связь по приглашенному пользователю"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM referrals WHERE referred_id = $1"
        return await conn.fetchrow(query, referred_id)

async def get_user_referrals(referrer_id: int):
    """Получает всех приглашенных пользователей"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT r.*, u.username, u.created_at as user_created
        FROM referrals r
        LEFT JOIN users u ON r.referred_id = u.user_id
        WHERE r.referrer_id = $1
        ORDER BY r.created_at DESC
        """
        return await conn.fetch(query, referrer_id)

async def verify_referral(referred_id: int):
    """Помечает реферал как верифицированный (выполнил условия)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE referrals 
        SET is_verified = TRUE, verified_at = NOW() 
        WHERE referred_id = $1 AND is_verified = FALSE
        RETURNING *
        """
        return await conn.fetchrow(query, referred_id)

async def mark_reward_given(referred_id: int, reward_amount: int):
    """Помечает что награда была выдана"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE referrals 
        SET reward_given = TRUE, reward_amount = $2 
        WHERE referred_id = $1 AND reward_given = FALSE
        RETURNING *
        """
        return await conn.fetchrow(query, referred_id, reward_amount)

async def get_referral_stats(referrer_id: int):
    """Получает статистику по рефералам"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            COUNT(*) as total_referrals,
            COUNT(CASE WHEN is_verified = TRUE THEN 1 END) as verified_referrals,
            COUNT(CASE WHEN reward_given = TRUE THEN 1 END) as rewarded_referrals,
            COALESCE(SUM(reward_amount), 0) as total_rewards_earned
        FROM referrals 
        WHERE referrer_id = $1
        """
        return await conn.fetchrow(query, referrer_id)

async def check_user_activity_requirements(user_id: int):
    """Проверяет выполнил ли пользователь условия для верификации реферала"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем есть ли хотя бы одна карта и одна тренировка
        query = """
        SELECT 
            EXISTS(SELECT 1 FROM user_cards WHERE user_id = $1 LIMIT 1) as has_cards,
            EXISTS(SELECT 1 FROM training_results WHERE user_id = $1 LIMIT 1) as has_trainings
        """
        result = await conn.fetchrow(query, user_id)
        return result['has_cards'] and result['has_trainings']
    

# Запросы для уведомлений о бесплатных паках
async def get_or_create_notification_record(user_id: int):
    """Получает или создает запись об уведомлениях для пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO free_pack_notifications (user_id) 
        VALUES ($1)
        ON CONFLICT (user_id) 
        DO UPDATE SET updated_at = NOW()
        RETURNING *
        """
        return await conn.fetchrow(query, user_id)

async def update_notification_sent_time(user_id: int):
    """Обновляет время последнего отправленного уведомления"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE free_pack_notifications 
        SET last_notification_sent = NOW(), 
            notifications_count = notifications_count + 1,
            updated_at = NOW()
        WHERE user_id = $1
        RETURNING *
        """
        return await conn.fetchrow(query, user_id)

async def get_notification_record(user_id: int):
    """Получает запись об уведомлениях пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM free_pack_notifications WHERE user_id = $1"
        return await conn.fetchrow(query, user_id)

async def reset_notification_record(user_id: int):
    """Сбрасывает запись об уведомлениях (при открытии бесплатного пака)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE free_pack_notifications 
        SET last_notification_sent = NULL,
            updated_at = NOW()
        WHERE user_id = $1
        """
        await conn.execute(query, user_id)

async def get_users_with_available_free_packs():
    """Получает пользователей, у которых доступен бесплатный пак"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            u.user_id,
            u.last_free_pack,
            fpn.last_notification_sent,
            fpn.notifications_count
        FROM users u
        LEFT JOIN free_pack_notifications fpn ON u.user_id = fpn.user_id
        WHERE u.last_free_pack IS NULL 
           OR (u.last_free_pack IS NOT NULL 
               AND EXTRACT(EPOCH FROM (NOW() - u.last_free_pack)) >= 10800) -- 3 часа в секундах
        """
        return await conn.fetch(query)
    
async def get_chat_pack_status(user_id: int):
    """Получает статус открытия паков в чатах для пользователя (глобальный)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM chat_pack_openings 
        WHERE user_id = $1
        """
        result = await conn.fetchrow(query, user_id)
        return dict(result) if result else None

async def create_chat_pack_record(user_id: int, chat_id: int):
    """Создает запись об открытии паков в чате"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO chat_pack_openings (user_id, chat_id, opened_at, next_available_at, total_opened)
        VALUES ($1, $2, NOW(), NOW(), 0)
        RETURNING *
        """
        result = await conn.fetchrow(query, user_id, chat_id)
        return dict(result)

async def update_chat_pack_opening(user_id: int):
    """Обновляет запись после открытия пака"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE chat_pack_openings 
        SET 
            last_opened_at = NOW(),
            next_available_at = NOW() + INTERVAL '3 hours',
            total_opened = total_opened + 1
        WHERE user_id = $1
        RETURNING *
        """
        result = await conn.fetchrow(query, user_id)
        return dict(result) if result else None

async def can_open_chat_pack(user_id: int):
    """Проверяет, может ли пользователь открыть пак в любом чате (глобальная проверка)"""
    pack_status = await get_chat_pack_status(user_id)
    
    if not pack_status:
        return True, "first_time"
    
    # Используем UTC время для сравнения
    now = datetime.now(timezone.utc)
    next_available = pack_status['next_available_at']
    
    # Если next_available без часового пояса, добавляем UTC
    if next_available.tzinfo is None:
        next_available = next_available.replace(tzinfo=timezone.utc)
    else:
        # Если уже с часовым поясом, конвертируем в UTC для единообразия
        next_available = next_available.astimezone(timezone.utc)
    
    print(f"DEBUG: user_id={user_id}, now={now}, next_available={next_available}, can_open={now >= next_available}")
    
    if now >= next_available:
        return True, "available"
    else:
        # Вычисляем оставшееся время
        remaining = next_available - now
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return False, f"{hours:02d}:{minutes:02d}"
    
async def create_chat_pack_record_with_cooldown(user_id: int):
    """Создает запись об открытии паков с установленным cooldown"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO chat_pack_openings (user_id, last_opened_at, next_available_at, total_opened)
        VALUES ($1, NOW(), NOW() + INTERVAL '3 hours', 1)
        RETURNING *
        """
        result = await conn.fetchrow(query, user_id)
        return dict(result)
    
async def get_chat_pack_stats():
    """Получает общую статистику открытий паков во всех чатах"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            COUNT(*) as total_users,
            COALESCE(SUM(total_opened), 0) as total_opened,
            MAX(last_opened_at) as last_opened
        FROM chat_pack_openings
        """
        result = await conn.fetchrow(query)
        return dict(result) if result else {'total_users': 0, 'total_opened': 0, 'last_opened': None}
    
async def get_user_collections_progress(user_id: int):
    """Получает прогресс пользователя по всем коллекциям"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            c.id,
            c.name,
            c.description,
            c.total_cards,
            c.is_active,
            c.badge_emoji,
            c.badge_name,
            COUNT(DISTINCT uc.card_id) as user_cards_count,
            EXISTS(
                SELECT 1 FROM collection_rewards cr 
                WHERE cr.collection_id = c.id AND cr.user_id = $1
            ) as reward_claimed,
            (SELECT COUNT(*) FROM cards WHERE collection_id = c.id) as actual_cards_count
        FROM collections c
        LEFT JOIN cards card ON c.id = card.collection_id
        LEFT JOIN user_cards uc ON card.id = uc.card_id AND uc.user_id = $1
        GROUP BY c.id
        ORDER BY c.is_active DESC, c.end_date DESC NULLS LAST, c.start_date DESC
        """
        return await conn.fetch(query, user_id)
    
async def get_collection_with_badge(collection_id: int):
    """Получает информацию о коллекции со значком"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            id, name, description, badge_emoji, badge_name
        FROM collections 
        WHERE id = $1
        """
        return await conn.fetchrow(query, collection_id)

async def get_collection_cards_with_user_progress(collection_id: int, user_id: int):
    """Получает все карты коллекции с отметкой о наличии у пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            card.id,
            card.player_name,
            card.rarity,
            card.uniq_name,
            card.weight,
            EXISTS(
                SELECT 1 FROM user_cards uc 
                WHERE uc.card_id = card.id AND uc.user_id = $2
            ) as user_has_card,
            COUNT(uc.id) as copies_count
        FROM cards card
        LEFT JOIN user_cards uc ON card.id = uc.card_id AND uc.user_id = $2
        WHERE card.collection_id = $1
        GROUP BY card.id
        ORDER BY 
            CASE card.rarity
                WHEN 'legendary' THEN 1
                WHEN 'epic' THEN 2
                WHEN 'rare' THEN 3
                WHEN 'common' THEN 4
            END,
            card.player_name
        """
        return await conn.fetch(query, collection_id, user_id)

async def claim_collection_reward(user_id: int, collection_id: int, reward_amount: int):
    """Записывает факт получения награды за коллекцию"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO collection_rewards (user_id, collection_id, reward_amount, claimed_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (user_id, collection_id) DO NOTHING
        RETURNING *
        """
        return await conn.fetchrow(query, user_id, collection_id, reward_amount)

async def check_collection_reward_claimed(user_id: int, collection_id: int):
    """Проверяет, получал ли пользователь награду за коллекцию"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM collection_rewards 
        WHERE user_id = $1 AND collection_id = $2
        """
        return await conn.fetchrow(query, user_id, collection_id)
    

# Добавляем в db/user_queries.py

async def unlock_user_badge(user_id: int, badge_type: str, badge_emoji: str, badge_name: str, collection_id: int = None):
    """Разблокирует значок пользователю"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO user_badges (user_id, badge_type, badge_emoji, badge_name, collection_id)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, badge_type, collection_id) DO NOTHING
        RETURNING *
        """
        return await conn.fetchrow(query, user_id, badge_type, badge_emoji, badge_name, collection_id)

async def get_user_badges(user_id: int):
    """Получает все значки пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM user_badges 
        WHERE user_id = $1 
        ORDER BY unlocked_at DESC
        """
        return await conn.fetch(query, user_id)

async def get_user_active_badge(user_id: int):
    """Получает активный значок пользователя (для отображения)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM user_badges 
        WHERE user_id = $1 
        ORDER BY 
            CASE badge_emoji
                WHEN '👑' THEN 1
                WHEN '🥇' THEN 2
                WHEN '🥈' THEN 3
                WHEN '🥉' THEN 4
                WHEN '🏆' THEN 5
                ELSE 6
            END,
            unlocked_at DESC
        LIMIT 1
        """
        return await conn.fetchrow(query, user_id)

async def get_user_completed_collections_count(user_id: int):
    """Получает количество завершенных коллекций пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT COUNT(*) as completed_count
        FROM (
            SELECT c.id
            FROM collections c
            LEFT JOIN cards card ON c.id = card.collection_id
            LEFT JOIN user_cards uc ON card.id = uc.card_id AND uc.user_id = $1
            GROUP BY c.id
            HAVING COUNT(DISTINCT uc.card_id) = COUNT(DISTINCT card.id)
        ) completed
        """
        return await conn.fetchval(query, user_id)
    
# Добавляем в db/user_queries.py

async def get_user_profile_stats(user_id: int):
    """Получает полную статистику для профиля пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Основная информация пользователя
        user_query = """
        SELECT 
            u.username,
            u.balance,
            u.score,
            u.created_at,
            COUNT(DISTINCT uc.card_id) as unique_cards,
            COUNT(uc.id) as total_cards,
            (SELECT COUNT(*) FROM collections) as total_collections,
            (SELECT COUNT(*) FROM collections c 
             WHERE EXISTS (SELECT 1 FROM cards card 
                          WHERE card.collection_id = c.id 
                          AND EXISTS (SELECT 1 FROM user_cards uc2 
                                     WHERE uc2.card_id = card.id 
                                     AND uc2.user_id = u.user_id))) as collections_with_cards
        FROM users u
        LEFT JOIN user_cards uc ON u.user_id = uc.user_id
        WHERE u.user_id = $1
        GROUP BY u.user_id
        """
        user_data = await conn.fetchrow(user_query, user_id)
        
        if not user_data:
            return None
        
        # Статистика игр
        games_query = """
        SELECT 
            COUNT(*) as total_games,
            COUNT(CASE WHEN result = 'win' THEN 1 END) as wins,
            COALESCE(SUM(win_amount), 0) as total_winnings
        FROM game_results 
        WHERE user_id = $1
        """
        games_stats = await conn.fetchrow(games_query, user_id)
        
        # Статистика тренировок
        training_query = """
        SELECT 
            COUNT(*) as total_trainings,
            COUNT(CASE WHEN success = true THEN 1 END) as successful_trainings,
            COALESCE(MAX(level), 1) as max_training_level
        FROM training_results 
        WHERE user_id = $1
        """
        training_stats = await conn.fetchrow(training_query, user_id)
        
        # Статистика рефералов
        referral_query = """
        SELECT 
            COUNT(*) as total_referrals,
            COUNT(CASE WHEN is_verified = TRUE THEN 1 END) as verified_referrals
        FROM referrals 
        WHERE referrer_id = $1
        """
        referral_stats = await conn.fetchrow(referral_query, user_id)
        
        # Завершенные коллекции
        completed_collections_query = """
        SELECT COUNT(*) as completed_collections
        FROM (
            SELECT c.id
            FROM collections c
            JOIN cards card ON c.id = card.collection_id
            GROUP BY c.id
            HAVING COUNT(DISTINCT card.id) = (
                SELECT COUNT(DISTINCT uc2.card_id)
                FROM user_cards uc2
                JOIN cards card2 ON uc2.card_id = card2.id
                WHERE uc2.user_id = $1 AND card2.collection_id = c.id
            )
        ) completed
        """
        completed_collections = await conn.fetchval(completed_collections_query, user_id)
        
        return {
            'username': user_data['username'],
            'balance': user_data['balance'],
            'score': user_data['score'],
            'created_at': user_data['created_at'],
            'unique_cards': user_data['unique_cards'] or 0,
            'total_cards': user_data['total_cards'] or 0,
            'total_collections': user_data['total_collections'] or 0,
            'collections_with_cards': user_data['collections_with_cards'] or 0,
            'completed_collections': completed_collections or 0,
            'total_games': games_stats['total_games'] or 0,
            'wins': games_stats['wins'] or 0,
            'total_winnings': games_stats['total_winnings'] or 0,
            'total_trainings': training_stats['total_trainings'] or 0,
            'successful_trainings': training_stats['successful_trainings'] or 0,
            'max_training_level': training_stats['max_training_level'] or 1,
            'total_referrals': referral_stats['total_referrals'] or 0,
            'verified_referrals': referral_stats['verified_referrals'] or 0
        }

async def get_user_badges_with_collections(user_id: int):
    """Получает значки пользователя с информацией о коллекциях"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            ub.*,
            c.name as collection_name
        FROM user_badges ub
        LEFT JOIN collections c ON ub.collection_id = c.id
        WHERE ub.user_id = $1 
        ORDER BY 
            CASE ub.badge_emoji
                WHEN '👑' THEN 1
                WHEN '🥇' THEN 2
                WHEN '🥈' THEN 3
                WHEN '🥉' THEN 4
                WHEN '🏆' THEN 5
                WHEN '⭐' THEN 6
                ELSE 7
            END,
            ub.unlocked_at DESC
        """
        return await conn.fetch(query, user_id)
    

# Добавляем в db/user_queries.py

async def get_all_active_users():
    """Получает всех активных пользователей бота"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT DISTINCT user_id 
        FROM users 
        WHERE user_id IS NOT NULL
        """
        return await conn.fetch(query)

async def get_users_count():
    """Получает общее количество пользователей"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT COUNT(*) as count FROM users"
        return await conn.fetchval(query)

async def create_broadcast(title: str, message_text: str, message_type: str = 'text', media_file_id: str = None):
    """Создает новую рассылку"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO broadcasts (title, message_text, message_type, media_file_id)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """
        return await conn.fetchrow(query, title, message_text, message_type, media_file_id)

async def get_pending_broadcasts():
    """Получает неотправленные рассылки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM broadcasts 
        WHERE is_sent = FALSE 
        ORDER BY created_at DESC
        """
        return await conn.fetch(query)

async def get_broadcast_by_id(broadcast_id: int):
    """Получает рассылку по ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM broadcasts WHERE id = $1"
        return await conn.fetchrow(query, broadcast_id)

async def update_broadcast_status(broadcast_id: int, sent_count: int, failed_count: int):
    """Обновляет статус рассылки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE broadcasts 
        SET is_sent = TRUE, sent_at = NOW(), 
            sent_count = $2, failed_count = $3
        WHERE id = $1
        """
        await conn.execute(query, broadcast_id, sent_count, failed_count)

async def create_broadcast_status(broadcast_id: int, user_id: int, status: str, error_message: str = None, message_id: int = None):
    """Создает запись о статусе отправки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO broadcast_status (broadcast_id, user_id, status, error_message, message_id)
        VALUES ($1, $2, $3, $4, $5)
        """
        await conn.execute(query, broadcast_id, user_id, status, error_message, message_id)

async def get_broadcast_message_id(broadcast_id: int, user_id: int):
    """Получает message_id сообщения рассылки для пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT message_id FROM broadcast_status 
        WHERE broadcast_id = $1 AND user_id = $2 AND status = 'sent'
        """
        return await conn.fetchval(query, broadcast_id, user_id)

async def get_broadcast_stats(broadcast_id: int):
    """Получает статистику по рассылке"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending
        FROM broadcast_status 
        WHERE broadcast_id = $1
        """
        return await conn.fetchrow(query, broadcast_id)

async def get_recent_broadcasts(limit: int = 10):
    """Получает последние рассылки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM broadcasts 
        ORDER BY created_at DESC 
        LIMIT $1
        """
        return await conn.fetch(query, limit)
    
async def get_12h_stats():
    """Получает статистику за последние 12 часов"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Временной диапазон (последние 12 часов)
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=12)
        
        stats = {}
        
        # 1. Статистика по открытию паков
        pack_stats_query = """
        SELECT 
            COUNT(*) as total_packs_opened,
            COUNT(DISTINCT user_id) as unique_users_opened_packs,
            COALESCE(SUM(cards_count), 0) as total_cards_from_packs
        FROM pack_openings 
        WHERE opened_at >= $1
        """
        pack_stats = await conn.fetchrow(pack_stats_query, time_threshold)
        stats['pack_stats'] = dict(pack_stats) if pack_stats else {}
        
        # 2. Статистика по редкостям карт из паков
        rarity_stats_query = """
        SELECT 
            c.rarity,
            COUNT(uc.id) as cards_count
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        WHERE uc.obtained_at >= $1
        GROUP BY c.rarity
        ORDER BY 
            CASE c.rarity
                WHEN 'legendary' THEN 1
                WHEN 'epic' THEN 2
                WHEN 'rare' THEN 3
                WHEN 'common' THEN 4
            END
        """
        rarity_stats = await conn.fetch(rarity_stats_query, time_threshold)
        stats['rarity_stats'] = {row['rarity']: row['cards_count'] for row in rarity_stats}
        
        # 3. Статистика по тренировкам
        training_stats_query = """
        SELECT 
            COUNT(*) as total_trainings,
            COUNT(DISTINCT user_id) as unique_users_trained,
            COUNT(CASE WHEN success = true THEN 1 END) as successful_trainings,
            COUNT(CASE WHEN success = false THEN 1 END) as failed_trainings,
            COALESCE(SUM(reward_earned), 0) as total_rewards_earned,
            COALESCE(AVG(level), 0) as average_level,
            MAX(level) as max_level
        FROM training_results 
        WHERE trained_at >= $1
        """
        training_stats = await conn.fetchrow(training_stats_query, time_threshold)
        stats['training_stats'] = dict(training_stats) if training_stats else {}
        
        # 4. Статистика по типам тренировок
        drill_type_stats_query = """
        SELECT 
            drill_type,
            COUNT(*) as count,
            COUNT(CASE WHEN success = true THEN 1 END) as success_count,
            AVG(level) as avg_level
        FROM training_results 
        WHERE trained_at >= $1
        GROUP BY drill_type
        ORDER BY count DESC
        """
        drill_type_stats = await conn.fetch(drill_type_stats_query, time_threshold)
        stats['drill_type_stats'] = [dict(row) for row in drill_type_stats]
        
        # 5. Статистика по играм
        game_stats_query = """
        SELECT 
            COUNT(*) as total_games,
            COUNT(DISTINCT user_id) as unique_users_played,
            COUNT(CASE WHEN result = 'win' THEN 1 END) as wins,
            COUNT(CASE WHEN result = 'lose' THEN 1 END) as losses,
            COUNT(CASE WHEN result = 'draw' THEN 1 END) as draws,
            COALESCE(SUM(bet_amount), 0) as total_bets,
            COALESCE(SUM(win_amount), 0) as total_winnings,
            COALESCE(AVG(player_score), 0) as avg_player_score,
            COALESCE(AVG(opponent_score), 0) as avg_opponent_score
        FROM game_results 
        WHERE created_at >= $1
        """
        game_stats = await conn.fetchrow(game_stats_query, time_threshold)
        stats['game_stats'] = dict(game_stats) if game_stats else {}
        
        # 6. Статистика по типам игр
        game_type_stats_query = """
        SELECT 
            game_type,
            COUNT(*) as total_games,
            COUNT(CASE WHEN result = 'win' THEN 1 END) as wins,
            COUNT(CASE WHEN result = 'lose' THEN 1 END) as losses,
            COUNT(CASE WHEN result = 'draw' THEN 1 END) as draws,
            AVG(player_score) as avg_player_score,
            AVG(opponent_score) as avg_opponent_score,
            SUM(win_amount) as total_winnings
        FROM game_results 
        WHERE created_at >= $1
        GROUP BY game_type
        ORDER BY total_games DESC
        """
        game_type_stats = await conn.fetch(game_type_stats_query, time_threshold)
        stats['game_type_stats'] = [dict(row) for row in game_type_stats]
        
        # 7. Статистика по рефералам
        referral_stats_query = """
        SELECT 
            COUNT(*) as new_referrals,
            COUNT(CASE WHEN is_verified = true THEN 1 END) as verified_referrals,
            COUNT(CASE WHEN reward_given = true THEN 1 END) as rewarded_referrals,
            COALESCE(SUM(reward_amount), 0) as total_rewards_given
        FROM referrals 
        WHERE created_at >= $1
        """
        referral_stats = await conn.fetchrow(referral_stats_query, time_threshold)
        stats['referral_stats'] = dict(referral_stats) if referral_stats else {}
        
        # 8. Активность пользователей (новые пользователи)
        user_stats_query = """
        SELECT 
            COUNT(*) as new_users,
            COALESCE(SUM(balance), 0) as total_balance_added,
            COALESCE(SUM(score), 0) as total_score_added
        FROM users 
        WHERE created_at >= $1
        """
        user_stats = await conn.fetchrow(user_stats_query, time_threshold)
        stats['user_stats'] = dict(user_stats) if user_stats else {}
        
        # 9. Общая финансовая статистика
        financial_stats_query = """
        SELECT 
            (SELECT COALESCE(SUM(win_amount), 0) FROM game_results WHERE created_at >= $1) as total_won_in_games,
            (SELECT COALESCE(SUM(reward_earned), 0) FROM training_results WHERE trained_at >= $1) as total_earned_in_trainings,
            (SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE created_at >= $1) as total_bet_in_games
        """
        financial_stats = await conn.fetchrow(financial_stats_query, time_threshold)
        stats['financial_stats'] = dict(financial_stats) if financial_stats else {}
        
        return stats
    
# Penalty queries
async def get_user_penalty_stats(user_id: int):
    """Получает статистику пользователя по пенальти"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            u.penalty_rating,
            u.is_shadow_mode,
            u.penalty_games_today,
            u.last_penalty_game_date,
            COUNT(pr.id) as total_games,
            COUNT(CASE WHEN pr.winner_id = u.user_id THEN 1 END) as wins,
            COUNT(CASE WHEN pr.winner_id != u.user_id AND pr.winner_id IS NOT NULL THEN 1 END) as losses,
            COUNT(CASE WHEN pr.winner_id IS NULL THEN 1 END) as draws,
            COALESCE(SUM(pr.coins_earned), 0) as total_coins_earned
        FROM users u
        LEFT JOIN penalty_results pr ON (u.user_id = pr.player1_id OR u.user_id = pr.player2_id)
        WHERE u.user_id = $1 AND pr.is_completed = TRUE
        GROUP BY u.user_id
        """
        return await conn.fetchrow(query, user_id)

async def update_user_penalty_rating(user_id: int, rating_change: int):
    """Обновляет рейтинг пользователя в пенальти"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        new_rating = await conn.fetchval("""
        UPDATE users 
        SET penalty_rating = GREATEST(0, penalty_rating + $2)
        WHERE user_id = $1
        RETURNING penalty_rating
        """, user_id, rating_change)
        return new_rating

async def create_penalty_invitation(inviter_id: int, invitee_identifier: str, bot: Bot):
    """Создает приглашение на матч с поиском по юзернейму или ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем лимит игр для приглашающего
        can_play, message = await can_play_penalty_today(inviter_id)
        if not can_play:
            return None, f"Вы не можете отправить приглашение: {message}"
        invitee = await find_user_by_uz_or_id(invitee_identifier)
        
        if not invitee:
            return None, "Пользователь не найден или находится в режиме невидимки"
        
        invitee_id = invitee['user_id']
        
        # Проверяем, не приглашает ли пользователь сам себя
        if inviter_id == invitee_id:
            return None, "Вы не можете пригласить самого себя"
        
        # Проверяем, нет ли уже активного приглашения
        existing_invitation = await conn.fetchrow("""
        SELECT * FROM penalty_invitations 
        WHERE inviter_id = $1 AND invitee_id = $2 AND status = 'pending'
        """, inviter_id, invitee_id)
        
        if existing_invitation:
            return None, "Вы уже отправили приглашение этому пользователю"
        
        # Получаем информацию о приглашающем
        inviter = await conn.fetchrow(
            "SELECT username, uz FROM users WHERE user_id = $1", inviter_id
        )
        
        inviter_username = inviter['uz'] or inviter['username'] or f"Игрок {inviter_id}"
        invitee_username = invitee['uz'] or invitee['username'] or f"Игрок {invitee_id}"
        
        # Создаем приглашение
        query = """
        INSERT INTO penalty_invitations 
        (inviter_id, invitee_id, inviter_username, invitee_username)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """
        invitation = await conn.fetchrow(query, inviter_id, invitee_id, inviter_username, invitee_username)
        
        # Отправляем уведомление приглашенному
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_invite:{invitation['id']}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_invite:{invitation['id']}")
                ]
            ])
            
            await bot.send_message(
                chat_id=invitee_id,
                text=f"🎯 <b>Приглашение на пенальти!</b>\n\n"
                     f"Игрок <b>{inviter_username}</b> приглашает вас на матч в режиме пенальти!\n\n"
                     f"⚽ <b>Правила:</b>\n"
                     f"• 5 основных ударов\n"
                     f"• Выбор карты влияет на шанс промаха\n"
                     f"• Награда: 100 монет за победу\n\n"
                     f"<i>Приглашение действует 2 минуты</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление: {e}")
            return None, "Не удалось отправить приглашение. Возможно, пользователь заблокировал бота"
        
        return dict(invitation), "Приглашение отправлено"

async def get_penalty_invitation(invitation_id: int):
    """Получает приглашение по ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM penalty_invitations WHERE id = $1"
        return await conn.fetchrow(query, invitation_id)

async def update_penalty_invitation_status(invitation_id: int, status: str):
    """Обновляет статус приглашения"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE penalty_invitations SET status = $1 WHERE id = $2"
        await conn.execute(query, status, invitation_id)

async def update_daily_penalty_games(user_id: int):
    """Обновляет счетчик игр (для обратной совместимости)"""
    # Эта функция теперь не нужна для логики лимита, но оставляем для совместимости
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Обновляем last_penalty_game_date для обратной совместимости
        query = "UPDATE users SET last_penalty_game_date = CURRENT_DATE WHERE user_id = $1"
        await conn.execute(query, user_id)

async def can_play_penalty_today(user_id: int):
    """Проверяет, может ли пользователь играть (лимит 3 игры в час)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Считаем количество игр пользователя за последний час
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        games_count = await conn.fetchval("""
        SELECT COUNT(*) 
        FROM penalty_results 
        WHERE (player1_id = $1 OR player2_id = $1) 
        AND completed_at >= $2
        AND is_completed = TRUE
        """, user_id, one_hour_ago)
        
        # Проверяем лимит (3 игры в час)
        if games_count >= 3:
            # Находим время самой старой игры в этом часовом окне
            oldest_game_time = await conn.fetchval("""
            SELECT MIN(completed_at) 
            FROM penalty_results 
            WHERE (player1_id = $1 OR player2_id = $1) 
            AND completed_at >= $2
            AND is_completed = TRUE
            """, user_id, one_hour_ago)
            
            if oldest_game_time:
                # Приводим оба времени к UTC для корректного вычитания
                next_available = oldest_game_time + timedelta(hours=1)
                now_utc = datetime.now(timezone.utc)
                time_left = next_available - now_utc
                
                minutes_left = max(0, int(time_left.total_seconds() // 60))
                return False, f"Лимит игр исчерпан. Следующая игра через {minutes_left} минут"
        update_daily_penalty_games
        return True, "Можно играть"

async def get_card_by_user_card_id(user_card_id: int):
    """Получает информацию о карте по ID карты пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT c.*, uc.id as user_card_id, uc.user_id, uc.serial_number
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        WHERE uc.id = $1
        """
        return await conn.fetchrow(query, user_card_id)

async def get_user_cards_by_rarity(user_id: int, rarity: str = None):
    """Получает карты пользователя с фильтрацией по редкости"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        base_query = """
        SELECT uc.id as user_card_id, c.*, uc.serial_number, col.name as collection_name
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        JOIN collections col ON c.collection_id = col.id
        WHERE uc.user_id = $1 AND uc.is_locked = FALSE
        """
        
        params = [user_id]
        
        if rarity and rarity != 'all':
            base_query += " AND c.rarity = $2"
            params.append(rarity)
        
        base_query += """
        ORDER BY 
            CASE c.rarity
                WHEN 'legendary' THEN 1
                WHEN 'epic' THEN 2
                WHEN 'rare' THEN 3
                WHEN 'common' THEN 4
            END,
            c.player_name
        """
        
        return await conn.fetch(base_query, *params)

async def update_user_uz(user_id: int, uz: str):
    """Обновляет юзернейм пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET uz = $1 WHERE user_id = $2"
        await conn.execute(query, uz, user_id)

async def find_user_by_uz_or_id(identifier: str):
    """Ищет пользователя по юзернейму или ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Пробуем найти по ID
        if identifier.isdigit():
            user = await conn.fetchrow(
                "SELECT user_id, username, uz FROM users WHERE user_id = $1 AND is_shadow_mode = FALSE",
                int(identifier)
            )
            if user:
                return user
        
        # Ищем по юзернейму
        user = await conn.fetchrow(
            "SELECT user_id, username, uz FROM users WHERE (uz = $1 OR username = $1) AND is_shadow_mode = FALSE",
            identifier
        )
        return user

async def create_penalty_match_v2(player1_id: int, player2_id: int = None, is_vs_bot: bool = False):
    """Создает новый матч по пенальти v2"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        player1_username = await conn.fetchval(
            "SELECT username FROM users WHERE user_id = $1", player1_id
        )
        player2_username = None
        if player2_id:
            player2_username = await conn.fetchval(
                "SELECT username FROM users WHERE user_id = $1", player2_id
            )
        
        query = """
        INSERT INTO penalty_matches_v2 
        (player1_id, player2_id, player1_username, player2_username, is_vs_bot, match_state)
        VALUES ($1, $2, $3, $4, $5, 'waiting_actions')
        RETURNING *
        """
        return await conn.fetchrow(query, player1_id, player2_id, player1_username, player2_username, is_vs_bot)

async def get_active_penalty_match_v2(user_id: int):
    """Получает активный матч пользователя v2"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT * FROM penalty_matches_v2 
        WHERE (player1_id = $1 OR player2_id = $1) 
        AND match_state != 'finished'
        AND expires_at > NOW()
        ORDER BY created_at DESC 
        LIMIT 1
        """
        return await conn.fetchrow(query, user_id)

async def update_penalty_match_actions_v2(match_id: int, user_id: int, kicks: dict, defenses: dict):
    """Обновляет действия игрока в матче v2"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        match = await conn.fetchrow("SELECT * FROM penalty_matches_v2 WHERE id = $1", match_id)
        
        if match['player1_id'] == user_id:
            query = """
            UPDATE penalty_matches_v2 
            SET player1_kicks = $1, player1_defenses = $2,
                last_action_time = NOW()
            WHERE id = $3
            """
        else:
            query = """
            UPDATE penalty_matches_v2 
            SET player2_kicks = $1, player2_defenses = $2,
                last_action_time = NOW()
            WHERE id = $3
            """
        
        await conn.execute(query, json.dumps(kicks), json.dumps(defenses), match_id)

async def process_penalty_match_v2(match_id: int):
    """Обрабатывает матч и определяет результат v2"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            match = await conn.fetchrow("SELECT * FROM penalty_matches_v2 WHERE id = $1 FOR UPDATE", match_id)
            
            if not match:
                print(f"DEBUG: Матч {match_id} не найден")
                return None
            
            if match['match_state'] != 'waiting_actions':
                print(f"DEBUG: Матч {match_id} уже обработан, состояние: {match['match_state']}")
                return None
            
            # Проверяем, что оба игрока определили действия
            if not match['player1_kicks'] or not match['player1_defenses']:
                print(f"DEBUG: Игрок 1 еще не завершил выбор действий")
                return None
            
            if not match['is_vs_bot'] and (not match['player2_kicks'] or not match['player2_defenses']):
                print(f"DEBUG: Игрок 2 еще не завершил выбор действий")
                return None
            
            print(f"DEBUG: Матч {match_id} готов к обработке")
            
            # Обрабатываем матч против бота
            if match['is_vs_bot']:
                result = await process_bot_match_v2(match)
            else:
                result = await process_pvp_match_v2(match)
            
            # Сохраняем результат
            await conn.execute("""
            UPDATE penalty_matches_v2 
            SET player1_score = $1, player2_score = $2, winner_id = $3,
                match_state = 'finished', completed_at = NOW()
            WHERE id = $4
            """, result['player1_score'], result['player2_score'], result['winner_id'], match_id)
            
            print(f"DEBUG: Матч {match_id} успешно обработан")
            return result

async def process_bot_match_v2(match: dict):
    """Обрабатывает матч против бота v2"""
    player1_kicks = json.loads(match['player1_kicks'])
    player1_defenses = json.loads(match['player1_defenses'])
    
    player1_score = 0
    player2_score = 0
    
    # Бот случайно выбирает удары и защиты
    bot_kicks = {}
    bot_defenses = {}
    directions = ['left', 'center', 'right']
    
    for i in range(1, 6):
        bot_kicks[str(i)] = random.choice(directions)
        bot_defenses[str(i)] = random.choice(directions)
    
    # Симулируем 5 ударов
    for i in range(1, 6):
        kick_num = str(i)
        
        # Удар игрока
        player_kick = player1_kicks.get(kick_num)
        bot_defense = bot_defenses.get(kick_num)
        
        if player_kick != bot_defense:
            player1_score += 1
        
        # Удар бота
        bot_kick = bot_kicks.get(kick_num)
        player_defense = player1_defenses.get(kick_num)
        
        if bot_kick != player_defense:
            player2_score += 1
    
    # ИСПРАВЛЕНИЕ: Правильно определяем победителя
    if player1_score > player2_score:
        winner_id = match['player1_id']  # Игрок победил
    elif player2_score > player1_score:
        winner_id = 0  # Бот победил (используем 0 вместо None)
    else:
        winner_id = None  # Ничья
    
    return {
        'player1_score': player1_score,
        'player2_score': player2_score,
        'winner_id': winner_id,
        'bot_kicks': bot_kicks,
        'bot_defenses': bot_defenses
    }

async def process_pvp_match_v2(match: dict):
    """Обрабатывает PvP матч v2"""
    player1_kicks = json.loads(match['player1_kicks'])
    player1_defenses = json.loads(match['player1_defenses'])
    player2_kicks = json.loads(match['player2_kicks'])
    player2_defenses = json.loads(match['player2_defenses'])
    
    player1_score = 0
    player2_score = 0
    
    # Симулируем 5 ударов
    for i in range(1, 6):
        kick_num = str(i)
        
        # Удар первого игрока
        player1_kick = player1_kicks.get(kick_num)
        player2_defense = player2_defenses.get(kick_num)
        
        if player1_kick != player2_defense:
            player1_score += 1
        
        # Удар второго игрока
        player2_kick = player2_kicks.get(kick_num)
        player1_defense = player1_defenses.get(kick_num)
        
        if player2_kick != player1_defense:
            player2_score += 1
    
    # Определяем победителя
    if player1_score > player2_score:
        winner_id = match['player1_id']
    elif player2_score > player1_score:
        winner_id = match['player2_id']
    else:
        winner_id = None  # Ничья
    
    return {
        'player1_score': player1_score,
        'player2_score': player2_score,
        'winner_id': winner_id
    }

async def get_penalty_match_v2_by_id(match_id: int):
    """Получает матч v2 по ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM penalty_matches_v2 WHERE id = $1"
        return await conn.fetchrow(query, match_id)

async def cleanup_expired_matches_v2():
    """Очищает просроченные матчи v2"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Помечаем просроченные матчи как завершенные
        await conn.execute("""
        UPDATE penalty_matches_v2 
        SET match_state = 'finished', completed_at = NOW()
        WHERE expires_at <= NOW() AND match_state != 'finished'
        """)

async def create_penalty_invitation_v2(inviter_id: int, invitee_identifier: str, bot: Bot):
    """Создает приглашение на матч v2 с поиском по юзернейму или ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Проверяем лимит игр для приглашающего
        can_play, message = await can_play_penalty_today(inviter_id)
        if not can_play:
            return None, f"Вы не можете отправить приглашение: {message}"
        
        invitee = await find_user_by_uz_or_id(invitee_identifier)
        
        if not invitee:
            return None, "Пользователь не найден или находится в режиме невидимки"
        
        invitee_id = invitee['user_id']
        
        # Проверяем, не приглашает ли пользователь сам себя
        if inviter_id == invitee_id:
            return None, "Вы не можете пригласить самого себя"
        
        # Проверяем, нет ли уже активного приглашения
        existing_invitation = await conn.fetchrow("""
        SELECT * FROM penalty_invitations 
        WHERE inviter_id = $1 AND invitee_id = $2 AND status = 'pending'
        """, inviter_id, invitee_id)
        
        if existing_invitation:
            return None, "Вы уже отправили приглашение этому пользователю"
        
        # Получаем информацию о приглашающем
        inviter = await conn.fetchrow(
            "SELECT username, uz FROM users WHERE user_id = $1", inviter_id
        )
        
        inviter_username = inviter['uz'] or inviter['username'] or f"Игрок {inviter_id}"
        invitee_username = invitee['uz'] or invitee['username'] or f"Игрок {invitee_id}"
        
        # Создаем приглашение
        query = """
        INSERT INTO penalty_invitations 
        (inviter_id, invitee_id, inviter_username, invitee_username)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """
        invitation = await conn.fetchrow(query, inviter_id, invitee_id, inviter_username, invitee_username)
        
        # Отправляем уведомление приглашенному
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_invite:{invitation['id']}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_invite:{invitation['id']}")
                ]
            ])
            
            await bot.send_message(
                chat_id=invitee_id,
                text=f"🎯 <b>Приглашение на пенальти v2!</b>\n\n"
                     f"Игрок <b>{inviter_username}</b> приглашает вас на матч в новой системе пенальти!\n\n"
                     f"⚽ <b>Новая система:</b>\n"
                     f"• Заранее определите 5 ударов и 5 защит\n"
                     f"• Результат вычисляется автоматически\n"
                     f"• Максимально честно и быстро\n\n"
                     f"<i>Приглашение действует 2 минуты</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление: {e}")
            return None, "Не удалось отправить приглашение. Возможно, пользователь заблокировал бота"
        
        return dict(invitation), "Приглашение отправлено"
    
# Необходимо добавить функцию toggle_shadow_mode в db/user_queries.py
async def toggle_shadow_mode(user_id: int, enable: bool):
    """Включает/выключает режим невидимки для пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "UPDATE users SET is_shadow_mode = $1 WHERE user_id = $2"
        await conn.execute(query, enable, user_id)

async def save_penalty_result_v2(match: dict, result: dict, rating_change: int, coins_earned: int, user_id: int):
    """Сохраняет результат матча в penalty_results"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Определяем, кто является игроком 1 и 2
        is_player1 = match['player1_id'] == user_id
        
        if match['is_vs_bot']:
            player2_id = None
            player2_username = "Бот"
        else:
            player2_id = match['player2_id'] if is_player1 else match['player1_id']
            player2_username = match['player2_username'] if is_player1 else match['player1_username']
        
        query = """
        INSERT INTO penalty_results 
        (player1_id, player2_id, player1_username, player2_username,
         player1_score, player2_score, winner_id, is_vs_bot,
         rating_change, coins_earned, created_at, completed_at, is_completed)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW(), TRUE)
        """
        
        await conn.execute(
            query,
            match['player1_id'],
            player2_id,
            match['player1_username'],
            player2_username,
            result['player1_score'],
            result['player2_score'],
            result['winner_id'],
            match['is_vs_bot'],
            rating_change,
            coins_earned
        )