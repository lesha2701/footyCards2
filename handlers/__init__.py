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
    return router