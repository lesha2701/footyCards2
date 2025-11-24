from aiogram import Router


def setup_message_routers() -> Router:
    from . import start
    from . import main_menu
    from . import show_shop_packs
    from . import my_cards
    from . import football21
    from . import footballDice
    from . import slots
    from . import market
    from . import donate
    from . import football_roulette
    from . import football_training
    from . import referral_system
    from . import album
    from . import profile
    from . import broadcast
    from . import craft
    from . import penalty

    router = Router()
    router.include_router(start.router)
    router.include_router(main_menu.router)
    router.include_router(show_shop_packs.router)
    router.include_router(my_cards.router)
    router.include_router(football21.router)
    router.include_router(footballDice.router)
    router.include_router(slots.router)
    router.include_router(market.router)
    router.include_router(donate.router)
    router.include_router(football_roulette.router)
    router.include_router(football_training.router)
    router.include_router(referral_system.router)
    router.include_router(album.router)
    router.include_router(profile.router)
    router.include_router(broadcast.router)
    router.include_router(craft.router)
    router.include_router(penalty.router)
    
    return router