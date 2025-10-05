from db.pool import get_db_pool
from typing import List, Dict, Any, Tuple
import random
import math

# КОНФИГУРАЦИЯ СИСТЕМЫ ШАНСОВ (легко настраивается)
class DropRateConfig:
    # Базовые вероятности для разных типов паков (common, rare, epic, legendary)
    PACK_RARITY_PROBABILITIES = {
        'free': {
            'common': 75,    # 75%
            'rare': 22,      # 22% 
            'epic': 2.5,     # 2.5%
            'legendary': 0.5 # 0.5%
        },
        'premium': {
            'common': 55,    # 55%
            'rare': 35,      # 35%
            'epic': 8,       # 8%
            'legendary': 2   # 2%
        },
        'collection': {
            'common': 40,    # 40%
            'rare': 40,      # 40%
            'epic': 15,      # 15%
            'legendary': 5   # 5%
        },
        'event': {
            'common': 30,    # 30%
            'rare': 40,      # 40%
            'epic': 20,      # 20%
            'legendary': 10  # 10%
        }
    }
    
    # Модификаторы редкости внутри каждой категории
    RARITY_TIERS = {
        'common': {
            'tier_1': {'weight': 0.6, 'modifier': 1.0},   # 60% - обычные common
            'tier_2': {'weight': 0.3, 'modifier': 0.7},   # 30% - редкие common  
            'tier_3': {'weight': 0.1, 'modifier': 0.4}    # 10% - очень редкие common
        },
        'rare': {
            'tier_1': {'weight': 0.5, 'modifier': 1.0},   # 50% - обычные rare
            'tier_2': {'weight': 0.3, 'modifier': 0.6},   # 30% - редкие rare
            'tier_3': {'weight': 0.2, 'modifier': 0.3}    # 20% - очень редкие rare
        },
        'epic': {
            'tier_1': {'weight': 0.4, 'modifier': 1.0},   # 40% - обычные epic
            'tier_2': {'weight': 0.4, 'modifier': 0.5},   # 40% - редкие epic
            'tier_3': {'weight': 0.2, 'modifier': 0.2}    # 20% - очень редкие epic
        },
        'legendary': {
            'tier_1': {'weight': 0.3, 'modifier': 1.0},   # 30% - обычные legendary
            'tier_2': {'weight': 0.4, 'modifier': 0.4},   # 40% - редкие legendary
            'tier_3': {'weight': 0.3, 'modifier': 0.1}    # 30% - очень редкие legendary
        }
    }
    
    # Модификаторы на основе веса карты (чем выше вес, тем реже выпадение)
    WEIGHT_MODIFIERS = {
        'common': lambda w: 1.5 - w,    # Для common: вес 0.1 = множитель 1.4, вес 0.3 = множитель 1.2
        'rare': lambda w: 1.4 - w,      # Для rare: вес 0.4 = множитель 1.0, вес 0.6 = множитель 0.8
        'epic': lambda w: 1.3 - w,      # Для epic: вес 0.7 = множитель 0.6, вес 0.8 = множитель 0.5
        'legendary': lambda w: 1.2 - w  # Для legendary: вес 0.9 = множитель 0.3, вес 1.0 = множитель 0.2
    }
    
    # Гарантированные дропы (минимальное количество карт определенной редкости)
    GUARANTEED_DROPS = {
        'premium': {'rare': 1},      # В премиум паке гарантированно 1 rare+
        'collection': {'rare': 1},   # В коллекционном паке гарантированно 1 rare+
        'event': {'epic': 1}         # В ивентовом паке гарантированно 1 epic+
    }
    
    # Бонусы за редкость (дополнительные шансы для редких карт)
    RARITY_BONUS = {
        'common': 1.0,
        'rare': 1.2,
        'epic': 1.5,
        'legendary': 2.0
    }

async def generate_pack_cards(pack: Dict) -> List[Dict]:
    """Генерирует карты для пака на основе его настроек БЕЗ ДУБЛИКАТОВ"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        cards_count = pack['cards_amount']
        
        # Определяем collection_id для коллекционных паков
        collection_id = None
        if isinstance(pack.get('id'), str) and pack['id'].startswith('collection_'):
            collection_id = int(pack['id'].replace('collection_', ''))
        elif pack.get('collection_id'):
            collection_id = pack['collection_id']
        
        # Получаем все доступные карты
        if collection_id:
            query = """
            SELECT * FROM cards 
            WHERE collection_id = $1 
            ORDER BY RANDOM()
            LIMIT $2
            """
            available_cards = await conn.fetch(query, collection_id, cards_count)
        else:
            query = """
            SELECT c.* FROM cards c
            LEFT JOIN collections col ON c.collection_id = col.id
            WHERE (col.id IS NULL OR col.cards_opened < col.total_cards)
            ORDER BY RANDOM()
            LIMIT $1
            """
            available_cards = await conn.fetch(query, cards_count)
        
        # Если карт меньше чем нужно, возвращаем что есть
        if len(available_cards) < cards_count:
            print(f"Warning: Only {len(available_cards)} cards available, but need {cards_count}")
        
        # Берем нужное количество карт
        selected_cards = available_cards[:cards_count]
        
        return [dict(card) for card in selected_cards]

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