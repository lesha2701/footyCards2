from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.utils.markdown import html_decoration as hd

from db.user_queries import *

router = Router()

@router.callback_query(F.data == "referral_system")
async def show_referral_system(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Показывает реферальную систему"""
    user_id = callback.from_user.id
    
    try:
        # Получаем статистику рефералов
        referral_stats = await get_referral_stats(user_id)
        user_referrals = await get_user_referrals(user_id)
        
        # Создаем реферальную ссылку
        bot_username = (await bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        # Текст с информацией о реферальной системе
        text = (
            "👥 <b>Реферальная система</b>\n\n"
            "💫 <b>Приглашай друзей и получай награды!</b>\n\n"
            
            "🎯 <b>Как это работает:</b>\n"
            "<blockquote>1. Отправь другу свою реферальную ссылку\n"
            "2. Друг должен открыть хотя бы 1 пак карточек\n"
            "3. И сыграть хотя бы в 1 тренировку\n"
            "4. После этого вы оба получите награду!</blockquote>\n\n"
            
            "💰 <b>Система наград:</b>\n"
            "<blockquote>• За 1-го друга: <b>200 монет</b>\n"
            "• За 2-го друга: <b>300 монет</b>\n" 
            "• За 3-го друга: <b>400 монет</b>\n"
            "• И так далее (+100 монет за каждого следующего)\n"
            "• Друг тоже получает <b>200 монет</b>!</blockquote>\n\n"
        )
        
        # Добавляем статистику
        if referral_stats:
            text += (
                f"📊 <b>Ваша статистика:</b>\n"
                f"<blockquote>• Всего приглашено: {referral_stats['total_referrals']}\n"
                f"• Верифицировано: {referral_stats['verified_referrals']}\n"
                f"• Получено наград: {referral_stats['rewarded_referrals']}\n"
                f"• Всего заработано: {referral_stats['total_rewards_earned']} монет</blockquote>\n\n"
            )
        
        # Добавляем реферальную ссылку
        text += f"🔗 <b>Ваша реферальная ссылка:</b>\n<code>{referral_link}</code>\n\n"
        text += "<i>Просто отправь эту ссылку другу!</i>"
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список приглашенных", callback_data="referral_list")],
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", 
                                url=f"https://t.me/share/url?url={referral_link}&text=Присоединяйся%20к%20моей%20коллекции%20футбольных%20карточек!%20⚽")],
            [InlineKeyboardButton(text="🔄 Проверить активность", callback_data="check_referral_activity")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в реферальной системе: {e}")
        await callback.answer("❌ Ошибка загрузки реферальной системы", show_alert=True)

@router.callback_query(F.data == "referral_list")
async def show_referral_list(callback: CallbackQuery):
    """Показывает список приглашенных друзей"""
    user_id = callback.from_user.id
    
    try:
        referrals = await get_user_referrals(user_id)
        
        if not referrals:
            text = "📋 <b>Список приглашенных друзей</b>\n\n📭 Вы еще никого не приглашали."
        else:
            text = "📋 <b>Список приглашенных друзей</b>\n\n"
            
            for i, ref in enumerate(referrals, 1):
                username = ref['username'] or f"Пользователь {ref['referred_id']}"
                status = "✅ Верифицирован" if ref['is_verified'] else "⏳ Ожидает активности"
                reward = f"🎁 {ref['reward_amount']} монет" if ref['reward_given'] else "⏳ Награда ожидает"
                
                text += (
                    f"{i}. <b>{username}</b>\n"
                    f"   📅 {ref['created_at'].strftime('%d.%m.%Y')}\n"
                    f"   📊 {status}\n"
                    f"   {reward}\n\n"
                )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к рефералам", callback_data="referral_system")],
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА в списке рефералов: {e}")
        await callback.answer("❌ Ошибка загрузки списка", show_alert=True)

@router.callback_query(F.data == "check_referral_activity")
async def check_referral_activity(callback: CallbackQuery, bot: Bot):
    """Проверяет активность приглашенных друзей и выдает награды"""
    user_id = callback.from_user.id
    
    try:
        referrals = await get_user_referrals(user_id)
        newly_verified = 0
        total_reward = 0
        
        for referral in referrals:
            if not referral['is_verified']:
                # Проверяем активность приглашенного пользователя
                is_active = await check_user_activity_requirements(referral['referred_id'])
                
                if is_active:
                    # Верифицируем реферала
                    await verify_referral(referral['referred_id'])
                    newly_verified += 1
                    
                    # Вычисляем награду
                    verified_count = await get_referral_stats(user_id)
                    base_reward = 200 + (verified_count['verified_referrals'] - 1) * 100
                    
                    # Выдаем награду приглашающему
                    await update_user_balance(user_id, base_reward)
                    await mark_reward_given(referral['referred_id'], base_reward)
                    total_reward += base_reward
                    
                    # Выдаем награду приглашенному (фиксированные 200 монет)
                    await update_user_balance(referral['referred_id'], 200)
                    
                    # Отправляем уведомление приглашенному с кнопкой меню
                    try:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📋 Открыть меню", callback_data="open_menu")]
                        ])
                        
                        await bot.send_message(
                            chat_id=referral['referred_id'],
                            text=f"🎉 <b>Реферальная награда!</b>\n\n"
                                 f"Вы получили <b>200 монет</b> за активность в боте!\n"
                                 f"Спасибо, что присоединились! ⚽\n\n"
                                 f"<i>Продолжайте собирать карты и участвовать в тренировках!</i>",
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Не удалось отправить уведомление пользователю {referral['referred_id']}: {e}")
        
        if newly_verified > 0:
            # Создаем клавиатуру с кнопкой меню
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="back_to_menu")],
                [InlineKeyboardButton(text="👥 К рефералам", callback_data="referral_system")]
            ])
            
            await callback.message.edit_text(
                text=f"🎉 <b>Проверка завершена!</b>\n\n"
                     f"✅ <b>Стали активными:</b> {newly_verified} друзей\n"
                     f"💰 <b>Вы получили:</b> {total_reward} монет\n\n"
                     f"<i>Награды были начислены на ваш баланс!</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Создаем клавиатуру с кнопкой меню даже когда нет новых активных
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="back_to_menu")],
                [InlineKeyboardButton(text="👥 К рефералам", callback_data="referral_system")]
            ])
            
            await callback.message.edit_text(
                text="ℹ️ <b>Проверка активности</b>\n\n"
                     "📭 Пока нет новых активных друзей.\n\n"
                     "<i>Напомните друзьям открыть пак карточек и пройти тренировку!</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        print(f"[{datetime.now()}] ОШИБКА проверки активности: {e}")
        
        # Даже при ошибке добавляем кнопку меню
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="back_to_menu")]
        ])
        
        await callback.message.edit_text(
            text="❌ <b>Ошибка проверки активности</b>\n\n"
                 "Произошла техническая ошибка. Попробуйте позже.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )