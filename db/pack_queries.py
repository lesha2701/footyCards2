from db.pool import get_db_pool
from typing import List, Dict
import random
from datetime import datetime, timedelta
from db.card_queries import (
    get_collection_cards_by_level, 
    get_available_collections_by_card_rarity,
    get_random_card_by_rarity
)

async def generate_pack_cards(pack: Dict) -> List[Dict]:
    """Генерирует карты для пака по новой логике"""
    pool = await get_db_pool()
    cards_count = pack.get('cards_amount', 5)
    selected_cards = []
    
    # Шансы редкостей из пака
    rarity_probs = {
        'common': pack.get('common_chance', 70) / 100.0,
        'rare': pack.get('rare_chance', 25) / 100.0,
        'epic': pack.get('epic_chance', 4) / 100.0,
        'legendary': pack.get('legendary_chance', 1) / 100.0
    }
    
    print(f"🎴 Генерация карт для пака '{pack['name']}' ({pack['id']}): {cards_count} карт")
    
    for i in range(cards_count):
        try:
            # ШАГ 1: Определяем редкость карты
            rarity = select_rarity(rarity_probs)
            print(f"  Карта {i+1}: редкость = {rarity}")
            
            # ШАГ 2: Определяем уровень коллекции для этой редкости
            collection_level = await select_collection_level_for_rarity(pool, rarity)
            print(f"    -> уровень коллекции = {collection_level}")
            
            # ШАГ 3: Выбираем случайную карту из коллекций этого уровня
            card = await get_random_card_by_rarity_and_level(pool, rarity, collection_level)
            
            if card:
                print(f"    -> {card.get('player_name', '?')} [{card.get('rarity', '?')}] из {collection_level}")
                selected_cards.append(dict(card))
            else:
                # Fallback: если нет карт, берем просто карту нужной редкости
                print(f"    -> Нет карт уровня {collection_level}, берем любую карту редкости {rarity}")
                fallback_card = await get_random_card_by_rarity_fallback(pool, rarity)
                if fallback_card:
                    selected_cards.append(dict(fallback_card))
                    
        except Exception as e:
            print(f"    -> Ошибка генерации карты {i+1}: {e}")
            continue
    
    return selected_cards

async def select_collection_level_for_rarity(pool, rarity: str) -> str:
    """Выбирает уровень коллекции на основе редкости карты"""
    async with pool.acquire() as conn:
        # Получаем вероятности уровней для этой редкости
        query = """
        SELECT collection_level, probability 
        FROM collection_level_probabilities 
        WHERE card_rarity = $1
        """
        results = await conn.fetch(query, rarity)
        
        if not results:
            # Дефолтные вероятности если нет в БД
            default_probs = {
                'common': {'ordinary': 70, 'rare': 20, 'super_rare': 10},
                'rare': {'ordinary': 60, 'rare': 25, 'super_rare': 15},
                'epic': {'ordinary': 50, 'rare': 30, 'super_rare': 20},
                'legendary': {'ordinary': 40, 'rare': 40, 'super_rare': 20}
            }
            probs = default_probs.get(rarity, {'ordinary': 100})
        else:
            probs = {row['collection_level']: row['probability'] for row in results}
        
        # Преобразуем проценты в дроби и нормализуем
        total = sum(probs.values())
        if total == 0:
            return 'ordinary'  # fallback
        
        # Выбираем уровень на основе вероятностей
        roll = random.random() * total
        cumulative = 0
        for level, prob in probs.items():
            cumulative += prob
            if roll <= cumulative:
                return level
        
        return 'ordinary'  # fallback
    
async def get_random_card_by_rarity_and_level(pool, rarity: str, collection_level: str) -> Dict:
    """Получает случайную карту указанной редкости из коллекций указанного уровня"""
    async with pool.acquire() as conn:
        query = """
        SELECT c.*, col.name as collection_name, col.level as collection_level
        FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1 
          AND col.level = $2 
          AND col.is_available = TRUE
        ORDER BY RANDOM() 
        LIMIT 1
        """
        result = await conn.fetchrow(query, rarity, collection_level)
        
        if result:
            return dict(result)
        
        # Если нет карт в коллекциях этого уровня, пробуем найти без привязки к коллекции
        backup_query = """
        SELECT c.*, 'Без коллекции' as collection_name
        FROM cards c
        WHERE c.rarity = $1 
          AND (c.collection_id IS NULL OR 
               c.collection_id NOT IN (SELECT id FROM collections WHERE is_available = FALSE))
        ORDER BY RANDOM() 
        LIMIT 1
        """
        backup_result = await conn.fetchrow(backup_query, rarity)
        
        if backup_result:
            backup_dict = dict(backup_result)
            backup_dict['collection_level'] = 'ordinary'  # Дефолтный уровень
            return backup_dict
        
        return None
    
async def get_random_card_by_rarity_fallback(pool, rarity: str) -> Dict:
    """Fallback: получает любую карту указанной редкости"""
    async with pool.acquire() as conn:
        query = """
        SELECT c.*, 
               COALESCE(col.name, 'Без коллекции') as collection_name,
               COALESCE(col.level, 'ordinary') as collection_level
        FROM cards c
        LEFT JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1 
          AND (col.id IS NULL OR col.is_available = TRUE)
        ORDER BY RANDOM() 
        LIMIT 1
        """
        result = await conn.fetchrow(query, rarity)
        return dict(result) if result else None

async def get_filtered_cards_by_rarity_level(pool, rarity: str, level: str) -> List[Dict]:
    async with pool.acquire() as conn:
        # ✅ ОТЛАДКА: сколько карт найдено
        debug_query = """
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN c.rarity = $1 THEN 1 END) as matching_rarity
        FROM cards c JOIN collections col ON c.collection_id = col.id
        WHERE col.level = $2 AND col.is_available = TRUE
        """
        debug = await conn.fetchrow(debug_query, rarity, level)
        print(f"DEBUG: rarity={rarity}, level={level}: total={debug['total']}, matching={debug['matching_rarity']}")
        
        query = """
        SELECT c.id, c.player_name, c.rarity, c.collection_id, c.weight, c.uniq_name
        FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1 AND col.level = $2 AND col.is_available = TRUE
        ORDER BY RANDOM()
        LIMIT 10
        """
        cards = await conn.fetch(query, rarity, level)
        print(f"  Found {len(cards)} cards: {[c['player_name'] for c in cards]}")
        return [dict(c) for c in cards]

async def get_random_card_by_rarity(pool, rarity: str) -> Dict:
    """Fallback: ТОЛЬКО нужная редкость"""
    async with pool.acquire() as conn:
        query = """
        SELECT c.* FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1 AND col.is_available = TRUE
        ORDER BY RANDOM() LIMIT 1
        """
        result = await conn.fetchrow(query, rarity)
        return dict(result) if result else {'rarity': rarity, 'player_name': 'Fallback'}

def select_rarity(probabilities: Dict[str, float]) -> str:
    """Выбирает редкость карты на основе вероятностей из пака"""
    roll = random.random()
    cumulative = 0
    
    for rarity, prob in probabilities.items():
        cumulative += prob
        if roll <= cumulative:
            return rarity
    
    return 'common'  # Fallback

def select_weighted(probs: Dict[str, float]) -> str:
    """Уровень коллекции по весам"""
    roll = random.random()
    cumulative = 0
    for level, prob in probs.items():
        cumulative += prob
        if roll <= cumulative: return level
    return 'ordinary'

async def toggle_collection_available(collection_id: int, available: bool) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "UPDATE collections SET is_available = $1 WHERE id = $2 RETURNING id",
            available, collection_id
        )
    print(f"Collection {collection_id} {'enabled' if available else 'disabled'} for drops")
    return bool(result)

async def get_random_card_by_rarity(pool, rarity: str):
    """Fallback: случайная карта редкости (если нет коллекций)"""
    async with pool.acquire() as conn:
        query = """
        SELECT c.* FROM cards c
        JOIN collections col ON c.collection_id = col.id
        WHERE c.rarity = $1 AND col.is_available = TRUE
        ORDER BY RANDOM() LIMIT 1
        """
        return await conn.fetchrow(query, rarity) or {'rarity': rarity, 'player_name': 'Fallback Card'}

async def getCard(conn, rarity):
    """Получает одну случайную карту указанной редкости из активных коллекций"""
    query = """
    SELECT c.* FROM cards c
    LEFT JOIN collections col ON c.collection_id = col.id
    WHERE c.rarity = $1 
    AND (c.collection_id IS NULL OR (col.is_active = true AND col.cards_opened < col.total_cards))
    ORDER BY RANDOM()
    LIMIT 1
    """
    return await conn.fetchrow(query, rarity)

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
        
        all_packs = [dict(pack) for pack in base_packs]
        return all_packs

async def get_pack_by_id(pack_id: any) -> Dict:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        pack_id = int(pack_id)
        query = "SELECT * FROM packs WHERE id = $1"
        result = await conn.fetchrow(query, pack_id)
        return dict(result) if result else {}
    return {}

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
    """Обновляет статистику коллекций на основе выпавших карт и деактивирует исчерпанные коллекции"""
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
            SET 
                cards_opened = LEAST(cards_opened + $2, total_cards),
                is_active = CASE 
                    WHEN cards_opened + $2 >= total_cards THEN false 
                    ELSE is_active 
                END
            WHERE id = $1 
            RETURNING id, cards_opened, total_cards, is_active
            """
            result = await conn.fetchrow(update_query, collection_id, cards_count)
            if result:
                updated_count += 1
                # Логируем если коллекция была деактивирована
                if not result['is_active'] and result['cards_opened'] >= result['total_cards']:
                    print(f"[{datetime.now()}] Коллекция {collection_id} исчерпана и деактивирована. Выпало: {result['cards_opened']}/{result['total_cards']}")
        
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