from db.pool import get_db_pool
from typing import List, Dict, Any, Tuple
import random
import math

async def generate_pack_cards(pack: Dict) -> List[Dict]:
    """Генерирует карты для пака на основе его настроек БЕЗ ДУБЛИКАТОВ"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        cards_count = pack['cards_amount']

        print(pack)
        common_chance = pack['common_chance']
        rare_chance = pack['rare_chance']
        epic_chance = pack['epic_chance']
        legendary_chance = pack['legendary_chance']

        print(common_chance, rare_chance, epic_chance, legendary_chance)

        # Собираем все карты в список
        selected_cards = []
        
        for i in range(cards_count):
            number = random.randint(0, 99)
            print(number)
            
            if number < common_chance:
                card = await getCard(conn, 'common')  # Передаем connection и получаем карту
                print("generate common")
            elif number < common_chance + rare_chance:
                card = await getCard(conn, 'rare')
                print("generate rare")
            elif number < common_chance + rare_chance + epic_chance:
                card = await getCard(conn, 'epic')
                print("generate epic")
            else:
                card = await getCard(conn, 'legendary')
                print("generate legendary")
            
            # Добавляем карту в список, если она найдена
            if card:
                selected_cards.append(dict(card))

        # Если карт меньше чем нужно, возвращаем что есть
        if len(selected_cards) < cards_count:
            print(f"Warning: Only {len(selected_cards)} cards available, but need {cards_count}")
        
        return selected_cards

async def getCard(conn, rarity):
    """Получает одну случайную карту указанной редкости"""
    query = """
    SELECT c.* FROM cards c
    WHERE (c.rarity = $1)
    ORDER BY RANDOM()
    LIMIT 1
    """
    return await conn.fetchrow(query, rarity)

def select_rarity(probabilities: Dict[str, float]) -> str:
    """Выбирает редкость на основе вероятностей"""
    roll = random.random() * 100
    cumulative = 0
    
    for rarity, prob in probabilities.items():
        cumulative += prob
        if roll <= cumulative:
            return rarity
    
    return 'common'  # Fallback

# Остальные функции остаются без изменений
async def get_available_packs(user_id: int) -> List[Dict]:
    """Получает все доступные паки для пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Базовые паки (всегда доступные)
        base_packs = await conn.fetch("""
            SELECT * FROM packs 
            WHERE is_always_available = true
            ORDER BY cost, id
        """)
        
        # Коллекционные паки (активные коллекции с доступными картами)
        collection_packs = await conn.fetch("""
            SELECT 
                'collection_' || c.id as id,
                c.name as name,
                c.description as description,
                500 as cost,  -- Фиксированная цена 500 монет
                3 as cards_amount,  -- Фиксированно 3 карты
                null as cooldown_hours,
                'collection' as pack_type,
                false as is_always_available,
                30 as common_chance,
                40 as rare_chance,
                20 as epic_chance,
                10 as legendary_chance,
                c.id as collection_id
            FROM collections c
            WHERE c.is_active = true 
            AND c.end_date > NOW()
            AND c.cards_opened < c.total_cards  -- Есть доступные карты
            AND EXISTS (
                SELECT 1 FROM cards 
                WHERE collection_id = c.id 
                LIMIT 1
            )
            ORDER BY c.id
        """)
        
        all_packs = [dict(pack) for pack in base_packs] + [dict(pack) for pack in collection_packs]
        return all_packs


async def get_pack_by_id(pack_id) -> Dict:
    """Получает пак по ID (обрабатывает как числовые, так и строковые ID коллекций)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if isinstance(pack_id, str) and pack_id.startswith('collection_'):
            # Это коллекционный пак
            collection_id = pack_id.replace('collection_', '')
            pack = await conn.fetchrow("""
                SELECT 
                    'collection_' || c.id as id,
                    c.name as name,
                    c.description as description,
                    500 as cost,
                    3 as cards_amount,
                    null as cooldown_hours,
                    'collection' as pack_type,
                    false as is_always_available,
                    30 as common_chance,
                    40 as rare_chance,
                    20 as epic_chance,
                    10 as legendary_chance,
                    c.id as collection_id
                FROM collections c
                WHERE c.id = $1 
                AND c.is_active = true 
                AND c.end_date > NOW()
                AND c.cards_opened < c.total_cards
            """, int(collection_id))
        else:
            # Это обычный пак
            try:
                pack_id_int = int(pack_id)
                pack = await conn.fetchrow("SELECT * FROM packs WHERE id = $1", pack_id_int)
            except (ValueError, TypeError):
                # Если pack_id нельзя преобразовать в int, пробуем как строку
                pack = await conn.fetchrow("SELECT * FROM packs WHERE id = $1", str(pack_id))
        
        return dict(pack) if pack else None

async def update_collection_stats(collection_id: int, cards_opened: int):
    """Обновляет статистику коллекции после открытия карт"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE collections 
        SET cards_opened = cards_opened + $2 
        WHERE id = $1 
        RETURNING cards_opened, total_cards
        """
        return await conn.fetchrow(query, collection_id, cards_opened)

async def get_collection_name(collection_id: int) -> str:
    """Получает название коллекции по ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT name FROM collections WHERE id = $1"
        return await conn.fetchval(query, collection_id)

async def update_collection_stats_by_cards(card_ids: List[int]) -> int:
    """Обновляет статистику коллекций на основе выпавших карт"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем collection_id всех выпавших карт
        query = """
        SELECT DISTINCT collection_id 
        FROM cards 
        WHERE id = ANY($1) AND collection_id IS NOT NULL
        """
        collections = await conn.fetch(query, card_ids)
        
        updated_count = 0
        for collection in collections:
            collection_id = collection['collection_id']
            # Считаем сколько карт этой коллекции выпало
            count_query = """
            SELECT COUNT(*) 
            FROM cards 
            WHERE id = ANY($1) AND collection_id = $2
            """
            cards_count = await conn.fetchval(count_query, card_ids, collection_id)
            
            # Обновляем статистику коллекции (не превышая лимит)
            update_query = """
            UPDATE collections 
            SET cards_opened = LEAST(cards_opened + $2, total_cards)
            WHERE id = $1 
            RETURNING id
            """
            result = await conn.fetchval(update_query, collection_id, cards_count)
            if result:
                updated_count += 1
        
        return updated_count

async def log_pack_opening(user_id: int, pack_id: int, card_ids: List[int]):
    """Логирует открытие пака с обработкой дубликатов карт"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Создаем запись об открытии пака
        query = """
        INSERT INTO pack_openings (user_id, pack_id, opened_at)
        VALUES ($1, $2, NOW())
        RETURNING id
        """
        pack_opening_id = await conn.fetchval(query, user_id, str(pack_id))
        
        # Убираем дубликаты карт для этого открытия
        seen = set()
        unique_card_ids = []
        for card_id in card_ids:
            if card_id not in seen:
                seen.add(card_id)
                unique_card_ids.append(card_id)
        
        # Для каждой уникальной карты создаем связь
        for card_id in unique_card_ids:
            try:
                card_query = """
                INSERT INTO pack_opening_cards (pack_opening_id, card_id)
                VALUES ($1, $2)
                """
                await conn.execute(card_query, pack_opening_id, card_id)
            except Exception as e:
                # Игнорируем ошибку дубликата, просто логируем
                print(f"Duplicate card {card_id} in pack opening {pack_opening_id}, skipping")
                continue

async def update_user_score(user_id: int, score_to_add: int) -> Dict:
    """Обновляет счет пользователя (добавляет очки)"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        UPDATE users 
        SET score = score + $1 
        WHERE user_id = $2 
        RETURNING user_id, score
        """
        result = await conn.fetchrow(query, score_to_add, user_id)
        return dict(result) if result else None
    
async def get_user_score(user_id: int) -> int:
    """Получает текущий счет пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = "SELECT score FROM users WHERE user_id = $1"
        result = await conn.fetchval(query, user_id)
        return result or 0