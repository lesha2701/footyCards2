from db.pool import get_db_pool

async def add_cards_to_user(user_id: int, card_ids):
    """Добавляет карты пользователю с автоматическим присвоением порядкового номера"""
    pool = await get_db_pool()
    added_count = 0
    serial_numbers = {}  # Будем хранить номера для каждой карточки
    
    async with pool.acquire() as conn:
        for card_id in card_ids:
            try:
                # Получаем текущее количество таких карточек в системе
                count_query = "SELECT COUNT(*) FROM user_cards WHERE card_id = $1"
                total_copies = await conn.fetchval(count_query, card_id)
                
                # Порядковый номер = текущее количество + 1
                serial_number = total_copies + 1
                
                # Добавляем карту с порядковым номером
                query = """
                INSERT INTO user_cards (user_id, card_id, serial_number, obtained_at) 
                VALUES ($1, $2, $3, NOW())
                RETURNING id
                """
                result = await conn.fetchval(query, user_id, card_id, serial_number)
                
                if result:
                    added_count += 1
                    serial_numbers[card_id] = {
                        'serial_number': serial_number,
                        'total_copies': total_copies + 1  # +1 потому что мы только что добавили
                    }
                    print(f"Added card {card_id} to user {user_id} with serial number #{serial_number}")
            except Exception as e:
                print(f"Error adding card {card_id} to user {user_id}: {e}")
        
        return {
            'added_count': added_count,
            'serial_numbers': serial_numbers
        }
    
async def get_card_serial_info(card_id: int):
    """Получает информацию о порядковом номере карточки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем общее количество таких карточек
        count_query = "SELECT COUNT(*) FROM user_cards WHERE card_id = $1"
        total_copies = await conn.fetchval(count_query, card_id)
        
        # Получаем информацию о карточке
        card_query = "SELECT * FROM cards WHERE id = $1"
        card_info = await conn.fetchrow(card_query, card_id)
        
        return {
            'total_copies': total_copies,
            'card_info': dict(card_info) if card_info else None,
            'rarity': card_info['rarity'] if card_info else 'common'
        }
    
async def get_cards_by_ids(card_ids):
    """Получает карты по их ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT * FROM cards WHERE id = ANY($1)"
        return await conn.fetch(query, card_ids)
    
async def check_cards_exist() -> bool:
    """Проверяет есть ли карты в базе"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT COUNT(*) FROM cards"
        count = await conn.fetchval(query)
        return count > 0
    

async def get_user_cards_by_rarity(user_id: int, rarity: str):
    """Получает уникальные карты пользователя по редкости с количеством копий"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            c.id,
            c.player_name,
            c.rarity,
            c.weight,
            c.uniq_name,
            c.collection_id,
            COUNT(uc.id) as copies_count,
            MIN(uc.serial_number) as first_serial_number
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        WHERE uc.user_id = $1 AND c.rarity = $2
        GROUP BY c.id, c.player_name, c.rarity, c.weight, c.uniq_name, c.collection_id
        ORDER BY 
            CASE c.rarity
                WHEN 'legendary' THEN 1
                WHEN 'epic' THEN 2
                WHEN 'rare' THEN 3
                WHEN 'common' THEN 4
            END,
            c.player_name
        """
        results = await conn.fetch(query, user_id, rarity)
        return [dict(row) for row in results]

async def get_user_card_details(user_id: int, card_id: int):
    """Получает детальную информацию о карточке пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Информация о карточке и количестве копий
        query = """
        SELECT 
            c.*,
            COUNT(uc.id) as copies_count,
            MIN(uc.serial_number) as best_serial_number,
            MIN(uc.obtained_at) as first_obtained,
            col.name as collection_name
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        LEFT JOIN collections col ON c.collection_id = col.id
        WHERE uc.user_id = $1 AND c.id = $2
        GROUP BY c.id, col.name
        """
        result = await conn.fetchrow(query, user_id, card_id)
        
        if not result:
            return None
            
        # Получаем все порядковые номера этой карточки у пользователя
        serial_query = """
        SELECT serial_number, obtained_at 
        FROM user_cards 
        WHERE user_id = $1 AND card_id = $2 
        ORDER BY serial_number
        """
        serials = await conn.fetch(serial_query, user_id, card_id)
        
        return {
            'card_info': dict(result),
            'copies_count': result['copies_count'],
            'best_serial_number': result['best_serial_number'],
            'first_obtained': result['first_obtained'],
            'collection_name': result['collection_name'],
            'serial_numbers': [dict(serial) for serial in serials]
        }

async def get_user_total_cards_count(user_id: int):
    """Получает общее количество карт по редкостям"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            c.rarity,
            COUNT(uc.id) as count
        FROM user_cards uc
        JOIN cards c ON uc.card_id = c.id
        WHERE uc.user_id = $1
        GROUP BY c.rarity
        """
        results = await conn.fetch(query, user_id)
        
        counts = {row['rarity']: row['count'] for row in results}
        
        # Заполняем нулями отсутствующие редкости
        for rarity in ['common', 'rare', 'epic', 'legendary']:
            if rarity not in counts:
                counts[rarity] = 0
                
        return counts

    
async def get_user_cards(user_id: int):
    """Получение всех карт пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT uc.*, p.name, p.club, p.nation, p.position, p.rating, p.rarity, p.photo "
            "FROM user_cards uc "
            "JOIN players p ON uc.player_id = p.id "
            "WHERE uc.user_id = $1 "
            "ORDER BY p.rating DESC, p.rarity DESC",
            user_id
        )
    
async def get_player_info(player_id: int):
    """Получение информации об игроке"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM players WHERE id = $1",
            player_id
        )