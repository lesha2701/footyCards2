import asyncio
from datetime import datetime, timedelta
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import setup_message_routers
from handlers.chat_packs import router as chat_packs_router

from config import config
from db.pool import create_db_pool, close_db_pool, get_db_pool
from db.user_queries import *

from handlers import main_menu

async def check_referrals_activity_periodically(bot: Bot):
    """Фоновая задача для проверки активности рефералов каждые 5 минут"""
    while True:
        try:
            print(f"[{datetime.now()}] Запуск фоновой проверки рефералов...")
            
            # Получаем всех неверифицированных рефералов
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                query = """
                SELECT r.referred_id, r.referrer_id 
                FROM referrals r 
                WHERE r.is_verified = FALSE
                """
                unverified_refs = await conn.fetch(query)
            
            for ref in unverified_refs:
                try:
                    # Проверяем активность пользователя
                    is_active = await check_user_activity_requirements(ref['referred_id'])
                    
                    if is_active:
                        # Верифицируем и выдаем награды
                        await verify_referral(ref['referred_id'])
                        
                        # Вычисляем награду для приглашающего
                        referral_stats = await get_referral_stats(ref['referrer_id'])
                        base_reward = 200 + (referral_stats['verified_referrals'] - 1) * 100
                        
                        # Выдаем награды
                        await update_user_balance(ref['referrer_id'], base_reward)
                        await mark_reward_given(ref['referred_id'], base_reward)
                        await update_user_balance(ref['referred_id'], 200)
                        
                        # Отправляем уведомления с кнопками меню
                        try:
                            # Приглашающему - с кнопкой меню
                            keyboard_referrer = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📋 Главное меню", callback_data="open_menu")],
                                [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral_system")]
                            ])
                            
                            await bot.send_message(
                                chat_id=ref['referrer_id'],
                                text=f"🎉 <b>Реферал стал активным!</b>\n\n"
                                     f"Ваш друг выполнил условия и вы получили <b>{base_reward} монет</b>!\n"
                                     f"Продолжайте приглашать друзей для получения еще больших наград! 💰",
                                reply_markup=keyboard_referrer,
                                parse_mode="HTML"
                            )
                            
                            # Приглашенному - с кнопкой меню
                            keyboard_referred = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="📋 Открыть меню", callback_data="open_menu")]
                            ])
                            
                            await bot.send_message(
                                chat_id=ref['referred_id'],
                                text=f"🎉 <b>Спасибо за активность!</b>\n\n"
                                     f"Вы получили <b>200 монет</b> за участие в реферальной программе! ⚽\n\n"
                                     f"<i>Продолжайте собирать карты и участвовать в тренировках!</i>",
                                reply_markup=keyboard_referred,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            print(f"Ошибка отправки уведомления: {e}")
                            
                except Exception as e:
                    print(f"Ошибка обработки реферала {ref['referred_id']}: {e}")
            
            # Ждем 5 минут до следующей проверки
            await asyncio.sleep(300)  # 300 секунд = 5 минут
            
        except Exception as e:
            print(f"Критическая ошибка в фоновой задаче рефералов: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке

async def check_free_packs_availability(bot: Bot):
    """Фоновая задача для проверки доступности бесплатных паков каждую минуту"""
    while True:
        try:
            print(f"[{datetime.now()}] Запуск проверки бесплатных паков...")
            
            # Получаем пользователей с доступными бесплатными паками
            users_with_available_packs = await get_users_with_available_free_packs()
            
            if not users_with_available_packs:
                print(f"[{datetime.now()}] Нет пользователей с доступными бесплатными паками")
            else:
                print(f"[{datetime.now()}] Найдено {len(users_with_available_packs)} пользователей с доступными паками")
            
            for user in users_with_available_packs:
                try:
                    user_id = user['user_id']
                    last_free_pack = user['last_free_pack']
                    last_notification_sent = user['last_notification_sent']
                    
                    # Создаем или обновляем запись об уведомлениях
                    await get_or_create_notification_record(user_id)
                    
                    # Проверяем, нужно ли отправлять уведомление
                    should_send_notification = await should_send_free_pack_notification(
                        user_id, last_notification_sent
                    )
                    
                    if should_send_notification:
                        # Определяем тип уведомления
                        notification_type = "first_time" if last_free_pack is None else "available"
                        
                        # Отправляем уведомление
                        # await send_free_pack_notification(bot, user_id, notification_type)
                        # await asyncio.sleep(0.1)
                        
                        # Обновляем время отправки уведомления
                        await update_notification_sent_time(user_id)
                        
                        print(f"[{datetime.now()}] Отправлено уведомление о бесплатном паке пользователю {user_id}")
                    
                except Exception as e:
                    print(f"Ошибка обработки пользователя {user['user_id']} для бесплатного пака: {e}")
            
            # Ждем 1 минуту до следующей проверки
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Критическая ошибка в фоновой задаче бесплатных паков: {e}")
            await asyncio.sleep(30)  # Ждем 30 секунд при ошибке

async def should_send_free_pack_notification(user_id: int, last_notification_sent) -> bool:
    """Проверяет, нужно ли отправлять уведомление о бесплатном паке"""
    if last_notification_sent is None:
        return True  # Никогда не отправляли - отправляем
    
    return False

async def send_free_pack_notification(bot: Bot, user_id: int, notification_type: str):
    """Отправляет уведомление о доступности бесплатного пака"""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Открыть магазин паков", callback_data="show_shop_packs")],
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="open_menu")]
        ])
        
        if notification_type == "first_time":
            message_text = (
                "🎁 <b>Бесплатный пак доступен!</b>\n\n"
                "⚽ У вас есть возможность открыть <b>бесплатный пак</b> с футбольными карточками!\n\n"
                "💫 <b>Особенности бесплатного пака:</b>\n"
                "• Открывается <b>каждые 3 часа</b>\n"
                "• Содержит случайные карты игроков\n"
                "• Не требует монет\n"
                "• Помогает пополнять коллекцию\n\n"
                "🚀 <b>Не упусти возможность получить новых игроков!</b>"
            )
        else:  # notification_type == "available"
            message_text = (
                "🔄 <b>Бесплатный пак снова доступен!</b>\n\n"
                "⏰ Прошло 3 часа - время открыть новый бесплатный пак!\n\n"
                "🎴 <b>Что внутри:</b>\n"
                "• Случайные футбольные карточки\n"
                "• Возможность получить редких игроков\n"
                "• Пополнение вашей коллекции\n\n"
                "💎 <b>Бесплатно и без ограничений!</b>\n"
                "Открывается каждые 3 часа - не пропусти!"
            )
        
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"Не удалось отправить уведомление о бесплатном паке пользователю {user_id}: {e}")

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # Запускаем обе фоновые задачи
    # asyncio.create_task(check_referrals_activity_periodically(bot))
    # asyncio.create_task(check_free_packs_availability(bot))
    print("Фоновые задачи запущены: проверка рефералов и бесплатных паков")

async def main():
    # Инициализация пула соединений с БД
    await create_db_pool()
    
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
            )
        )
    
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутеров
    message_routers = setup_message_routers()
    dp.include_router(message_routers)
    dp.include_router(chat_packs_router)
    
    await on_startup(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())