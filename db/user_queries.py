from db.pool import get_db_pool
from datetime import *
import pytz

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
        # Проверяем, не выставлена ли уже карточка
        existing_query = "SELECT id FROM market_listings WHERE card_id = $1 AND is_sold = FALSE"
        existing = await conn.fetchval(existing_query, user_card_id)
        
        if existing:
            return None
            
        query = """
        INSERT INTO market_listings (user_id, card_id, price, created_at)
        VALUES ($1, $2, $3, NOW())
        RETURNING id
        """
        try:
            return await conn.fetchval(query, user_id, user_card_id, price)
        except Exception as e:
            print(f"Error creating market listing: {e}")
            return None
        
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
        ORDER BY 
            is_active DESC,
            end_date DESC NULLS LAST,
            start_date DESC
        """
        collections = await conn.fetch(query)
        return [dict(collection) for collection in collections]