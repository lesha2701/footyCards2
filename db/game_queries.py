from db.pool import get_db_pool
from datetime import datetime, timedelta, timezone


async def save_game_result(
    user_id: int,
    game_type: str,
    result: str,
    bet_amount: int,
    win_amount: int = 0,
    player_score: int = None,
    opponent_score: int = None
) -> None:
    """Сохраняет результат игры в базу данных"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO game_results 
        (user_id, game_type, result, bet_amount, win_amount, player_score, opponent_score)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await conn.execute(
            query, user_id, game_type, result, bet_amount, 
            win_amount, player_score, opponent_score
        )

async def get_user_game_stats(user_id: int, game_type: str = None):
    """Получает статистику игр пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if game_type:
            query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
                SUM(win_amount) as total_winnings,
                SUM(bet_amount) as total_bets
            FROM game_results 
            WHERE user_id = $1 AND game_type = $2
            """
            result = await conn.fetchrow(query, user_id, game_type)
        else:
            query = """
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
                SUM(win_amount) as total_winnings,
                SUM(bet_amount) as total_bets
            FROM game_results 
            WHERE user_id = $1
            """
            result = await conn.fetchrow(query, user_id)
        
        return dict(result) if result else {
            'total_games': 0, 'wins': 0, 'losses': 0, 'draws': 0,
            'total_winnings': 0, 'total_bets': 0
        }
    
async def get_football_dice_stats(user_id: int):
    """Получение статистики по футбольным костям"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Общая статистика
        total_games = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice'",
            user_id
        )
        
        wins = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice' AND result = 'win'",
            user_id
        )
        
        losses = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice' AND result = 'lose'",
            user_id
        )
        
        draws = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice' AND result = 'draw'",
            user_id
        )
        
        # Финансовая статистика
        total_win = await conn.fetchval(
            "SELECT COALESCE(SUM(win_amount), 0) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice'",
            user_id
        )
        
        total_bet = await conn.fetchval(
            "SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE user_id = $1 AND game_type = 'football_dice'",
            user_id
        )
        
        profit = total_win - total_bet
        
        # Процент побед
        win_percentage = (wins / total_games * 100) if total_games > 0 else 0
        
        return {
            'total_games': total_games,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_percentage': round(win_percentage, 1),
            'total_win': total_win,
            'total_bet': total_bet,
            'profit': profit
        }
    
async def get_slot_machine_stats(user_id: int):
    """Получение статистики по слот-машине"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Общая статистика
        total_games = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine'",
            user_id
        )
        
        wins = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine' AND win_amount > 0",
            user_id
        )
        
        jackpots = await conn.fetchval(
            "SELECT COUNT(*) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine' AND result = 'jackpot'",
            user_id
        )
        
        # Финансовая статистика
        total_win = await conn.fetchval(
            "SELECT COALESCE(SUM(win_amount), 0) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine'",
            user_id
        )
        
        total_bet = await conn.fetchval(
            "SELECT COALESCE(SUM(bet_amount), 0) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine'",
            user_id
        )
        
        profit = total_win - total_bet
        
        # Процент побед
        win_percentage = (wins / total_games * 100) if total_games > 0 else 0
        
        return {
            'total_games': total_games,
            'wins': wins,
            'jackpots': jackpots,
            'win_percentage': round(win_percentage, 1),
            'total_win': total_win,
            'total_bet': total_bet,
            'profit': profit,
            'biggest_win': await conn.fetchval(
                "SELECT COALESCE(MAX(win_amount), 0) FROM game_results WHERE user_id = $1 AND game_type = 'slot_machine'",
                user_id
            )
        }
    
async def get_football_roulette_stats(user_id: int):
    """Получает статистику игрока в футбольной рулетке"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT 
            COUNT(*) as total_games,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'lose' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
            COALESCE(SUM(win_amount), 0) as total_win,
            COALESCE(SUM(bet_amount), 0) as total_bet,
            COALESCE(SUM(win_amount - bet_amount), 0) as profit,
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    ROUND(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
                ELSE 0 
            END as win_percentage,
            COALESCE(MAX(win_amount), 0) as biggest_win
        FROM game_results 
        WHERE user_id = $1 AND game_type = 'football_roulette'
        """
        return await conn.fetchrow(query, user_id)
    
async def save_training_result(user_id: int, drill_type: str, success: bool, reward_earned: int, level: int):
    """Сохраняет результат тренировки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        INSERT INTO training_results 
        (user_id, drill_type, success, reward_earned, level, trained_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        """
        await conn.execute(query, user_id, drill_type, success, reward_earned, level)

async def get_training_stats(user_id: int):
    """Получает статистику тренировок игрока"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Основная статистика
        stats_query = """
        SELECT 
            COUNT(*) as total_trainings,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
            CASE 
                WHEN COUNT(*) > 0 THEN 
                    ROUND(SUM(CASE WHEN success THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1)
                ELSE 0 
            END as success_rate,
            COALESCE(SUM(reward_earned), 0) as total_earned
        FROM training_results 
        WHERE user_id = $1
        """
        stats = await conn.fetchrow(stats_query, user_id)
        
        # Уровни для каждого упражнения
        levels_query = """
        SELECT drill_type, MAX(level) as max_level
        FROM training_results 
        WHERE user_id = $1
        GROUP BY drill_type
        """
        levels = await conn.fetch(levels_query, user_id)
        
        # Количество успешных тренировок для каждого упражнения
        successes_query = """
        SELECT drill_type, COUNT(*) as successes
        FROM training_results 
        WHERE user_id = $1 AND success = TRUE
        GROUP BY drill_type
        """
        successes = await conn.fetch(successes_query, user_id)
        
        # Форматируем результаты
        drill_levels = {row['drill_type']: row['max_level'] for row in levels}
        drill_successes = {row['drill_type']: row['successes'] for row in successes}
        
        return {
            'total_trainings': stats['total_trainings'],
            'successful': stats['successful'],
            'success_rate': stats['success_rate'],
            'total_earned': stats['total_earned'],
            'drill_levels': drill_levels,
            'drill_successes': drill_successes
        }

async def check_training_cooldown(user_id: int, drill_type: str):
    """Проверяет, доступно ли упражнение для тренировки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        query = """
        SELECT trained_at 
        FROM training_results 
        WHERE user_id = $1 AND drill_type = $2 
        ORDER BY trained_at DESC 
        LIMIT 1
        """
        last_training = await conn.fetchval(query, user_id, drill_type)
        
        if not last_training:
            return {'available': True, 'time_left': 0}
        
        # Получаем cooldown из конфигурации упражнений
        from handlers.football_training import TRAINING_DRILLS
        cooldown = TRAINING_DRILLS[drill_type]['cooldown']
        
        next_available = last_training + cooldown
        now = datetime.now(last_training.tzinfo)  # Используем ту же временную зону
        time_left = max(0, (next_available - now).total_seconds())
        
        return {'available': time_left == 0, 'time_left': time_left}
    

async def get_memory_records(limit=10):
    """Получить топ рекордов памяти"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(f'''
            SELECT mr.*, u.username 
            FROM memory_records mr 
            LEFT JOIN users u ON mr.user_id = u.user_id 
            ORDER BY mr.time_taken ASC 
            LIMIT {limit}
        ''')

async def get_dribbling_records(limit=10):
    """Получить топ рекордов обводки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(f'''
            SELECT dr.*, u.username 
            FROM dribbling_records dr 
            LEFT JOIN users u ON dr.user_id = u.user_id 
            ORDER BY dr.defenders_beaten DESC 
            LIMIT {limit}
        ''')

async def check_and_update_memory_record(user_id, username, time_taken, sequence_length=5):
    """Проверить и обновить рекорд памяти"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем текущий топ-10
        current_records = await get_memory_records(10)
        
        # Проверяем, попадает ли результат в топ-10
        if len(current_records) < 10 or time_taken < current_records[-1]['time_taken']:
            # Добавляем новый рекорд
            await conn.execute('''
                INSERT INTO memory_records (user_id, username, time_taken, sequence_length)
                VALUES ($1, $2, $3, $4)
            ''', user_id, username, time_taken, sequence_length)
            
            # Удаляем лишние записи (оставляем только топ-10)
            await conn.execute('''
                DELETE FROM memory_records 
                WHERE id NOT IN (
                    SELECT id FROM memory_records 
                    ORDER BY time_taken ASC 
                    LIMIT 10
                )
            ''')
            return True
        return False

async def check_and_update_dribbling_record(user_id, username, defenders_beaten):
    """Проверить и обновить рекорд обводки"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Получаем текущий топ-10
        current_records = await get_dribbling_records(10)
        
        # Проверяем, попадает ли результат в топ-10
        if len(current_records) < 10 or defenders_beaten > current_records[-1]['defenders_beaten']:
            # Добавляем новый рекорд
            await conn.execute('''
                INSERT INTO dribbling_records (user_id, username, defenders_beaten)
                VALUES ($1, $2, $3)
            ''', user_id, username, defenders_beaten)
            
            # Удаляем лишние записи (оставляем только топ-10)
            await conn.execute('''
                DELETE FROM dribbling_records 
                WHERE id NOT IN (
                    SELECT id FROM dribbling_records 
                    ORDER BY defenders_beaten DESC 
                    LIMIT 10
                )
            ''')
            return True
        return False

async def get_minesweeper_stats(user_id):
    """Получить статистику сапёра для пользователя"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow('''
            SELECT COUNT(*) as games_played, 
                   SUM(success) as games_won,
                   SUM(reward_earned) as total_earned
            FROM training_results 
            WHERE user_id = $1 AND drill_type = 'minesweeper'
        ''', user_id)
    
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