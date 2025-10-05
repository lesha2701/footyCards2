# game_config.py
from dataclasses import dataclass

@dataclass
class DuelConfig:
    # Баланс игры
    WIN_COINS = 50
    DRAW_COINS = 25
    LOSE_COINS = 10
    LOSE_COINS_PENALTY = 5  # Сколько монет отнимается за поражение
    
    WIN_TROPHIES = 30
    LOSE_TROPHIES = 15
    DRAW_TROPHIES = 10
    
    # Модификаторы характеристик
    ATTACK_WEIGHT = 0.4
    DEFENSE_WEIGHT = 0.3
    CARD_WEIGHT_WEIGHT = 0.2
    RARITY_BONUS = 0.1
    
    # Редкость -> множитель
    RARITY_MULTIPLIERS = {
        'common': 1.0,
        'rare': 1.2,
        'epic': 1.5,
        'legendary': 2.0
    }
    
    # Баланс матча
    MAX_WEIGHT_DIFFERENCE = 0.3
    MATCH_DURATION = 90  # секунды в матче
    GOAL_PROBABILITY_BASE = 0.15  # базовая вероятность гола
    SHIELD_DURATION = 30  # минут защиты после атаки
    
    # Лимиты
    MAX_MATCHES_PER_HOUR = 10
    MIN_COINS_FOR_DUEL = 0
    
    # Фразы для комментариев
    GOAL_PHRASES = [
        "⚽️ Великолепный гол! {attacker} забивает в верхний угол!",
        "🎯 Точно в девятку! {attacker} не оставляет шансов вратарю!",
        "🔥 Невероятный удар! {attacker} поражает ворота!",
        "💫 Искусный дриблинг и точный завершающий удар от {attacker}!",
        "🚀 Мощнейший выстрел! {attacker} отправляет мяч в сетку!",
        "🌟 Голевая момента! {attacker} реализует свой шанс!",
        "🎩 Фантастический гол! {attacker} в великолепной форме!",
        "💥 Сногсшибательный удар! {attacker} забивает красивейший гол!"
    ]

    SAVE_PHRASES = [
        "🧤 Фантастический сейв! {defender} спасает свою команду!",
        "✋️ Мяч отбит! {defender} проявляет невероятную реакцию!",
        "🛡️ Непробиваемая защита! {defender} в своем репертуаре!",
        "🌟 Классный отбор мяча! {defender} прерывает атаку!",
        "💪 Мощное сопротивление! {defender} не пропускает!",
        "🎯 Точно в руки! {defender} уверенно берет мяч!",
        "🔥 Спасение матча! {defender} выручает свою команду!",
        "🦸 Суперсейв! {defender} творит чудеса в воротах!"
    ]
    
    MATCH_START_PHRASES = [
        "⚔️ Матч начинается! {player1} против {player2}",
        "🔔 Свисток! Начинается дуэль между {player1} и {player2}",
        "🎯 Игра началась! {player1} и {player2} вступают в бой"
    ]
    
    MATCH_END_PHRASES = {
        'win': ["🏆 Победа! {winner} одерживает верх над {loser}", "✅ {winner} слишком силен сегодня!"],
        'lose': ["😔 Поражение... {loser} уступает {winner}", "❌ {winner} оказывается лучше"],
        'draw': ["🤝 Ничья! Равная борьба между соперниками", "⚖️ Никто не смог взять верх в этом матче"]
    }