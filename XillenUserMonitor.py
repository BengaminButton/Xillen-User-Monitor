import asyncio
import logging
import datetime
import os
import json
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth
from telethon.tl.functions.users import GetFullUserRequest

api_id = 123123
api_hash = '123123'
target_user_input = 123123
POLL_INTERVAL_SECONDS = 25

BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'

session_name = 'user_tracker_session'
client = TelegramClient(session_name, api_id, api_hash)
target_user_id = None
prev_user_data = {}

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s %(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler('user_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка отправки сообщения в Telegram: {resp.status}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения в Telegram: {e}")

def clear_console():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

async def get_full_profile_info(user_id):
    try:
        result = await client(GetFullUserRequest(user_id))
        return result.users[0], result.full_user
    except Exception as e:
        logger.error(f"Ошибка получения информации: {e}")
        return None, None

def format_status(status):
    if isinstance(status, UserStatusOnline):
        return f"🟢 Онлайн (до {status.expires.strftime('%H:%M:%S')})"
    elif isinstance(status, UserStatusOffline):
        return f"🔴 Офлайн (был в сети: {status.was_online.strftime('%Y-%m-%d %H:%M:%S')})"
    elif isinstance(status, UserStatusRecently):
        return "🟡 Был(а) недавно"
    elif isinstance(status, UserStatusLastWeek):
        return "🟡 Был(а) на прошлой неделе"
    elif isinstance(status, UserStatusLastMonth):
        return "🟡 Был(а) в прошлом месяце"
    else:
        return "⚫ Статус неизвестен"

@client.on(events.UserUpdate)
async def handler_user_update(event):
    if event.user_id == target_user_id:
        status_text = format_status(event.status)
        logger.info(f"🔄 ИЗМЕНЕНИЕ СТАТУСА: {status_text}")
        await send_telegram_message(f"🔄 <b>ИЗМЕНЕНИЕ СТАТУСА</b>\n{status_text}")

@client.on(events.Raw)
async def handler_raw_updates(update):
    if hasattr(update, 'users'):
        users_list = update.users if isinstance(update.users, list) else [update.users]
        for user in users_list:
            if user.id == target_user_id:
                pass

async def check_profile_diff(updated_user_obj):
    global prev_user_data
    
    user_data, user_full_data = await get_full_profile_info(target_user_id)
    
    if not user_data or not user_full_data:
        return

    current_data = {
        'first_name': user_data.first_name or "",
        'last_name': user_data.last_name or "",
        'username': user_data.username or "",
        'has_photo': user_data.photo is not None,
        'bio': user_full_data.about or "",
        'premium': getattr(user_data, 'premium', False),
        'verified': getattr(user_data, 'verified', False),
        'restricted': getattr(user_data, 'restricted', False),
        'scam': getattr(user_data, 'scam', False),
        'fake': getattr(user_data, 'fake', False),
        'bot': getattr(user_data, 'bot', False),
    }

    if not prev_user_data:
        prev_user_data = current_data
        logger.info("📁 Начальные данные профиля сохранены")
        return

    changes_detected = False
    changes_message = "📝 <b>ИЗМЕНЕНИЯ В ПРОФИЛЕ:</b>\n"
    
    for key, value in current_data.items():
        old_value = prev_user_data.get(key)
        if old_value != value:
            changes_detected = True
            if key == 'has_photo':
                if value:
                    change_text = "🖼️ Аватарка была добавлена/изменена"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
                else:
                    change_text = "🖼️ Аватарка была удалена"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
            elif key == 'premium':
                if value:
                    change_text = "⭐ Пользователь получил Telegram Premium"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
                else:
                    change_text = "⭐ Пользователь потерял Telegram Premium"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
            elif key == 'verified':
                if value:
                    change_text = "✅ Пользователь получил верификацию"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
                else:
                    change_text = "✅ Пользователь потерял верификацию"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
            elif key in ['restricted', 'scam', 'fake']:
                if value:
                    change_text = f"⚠️ Флаг {key.upper()} установлен"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
                else:
                    change_text = f"⚠️ Флаг {key.upper()} снят"
                    logger.info(change_text)
                    changes_message += f"{change_text}\n"
            else:
                emoji = "📝"
                if key == 'username': emoji = "👤"
                elif key == 'bio': emoji = "📄"
                
                change_text = f"{emoji} {key.upper()}: '{old_value}' → '{value}'"
                logger.info(change_text)
                changes_message += f"{change_text}\n"

    if changes_detected:
        await send_telegram_message(changes_message)
    else:
        logger.debug("✅ Проверка завершена - изменений нет")

    prev_user_data = current_data

async def profile_poller():
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            await check_profile_diff(None)
        except Exception as e:
            logger.error(f"Ошибка в профиль поллере: {e}")

async def save_backup_data():
    if prev_user_data:
        backup = {
            'last_update': datetime.datetime.now().isoformat(),
            'user_data': prev_user_data
        }
        with open('user_backup.json', 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)

async def load_backup_data():
    global prev_user_data
    try:
        if os.path.exists('user_backup.json'):
            with open('user_backup.json', 'r', encoding='utf-8') as f:
                backup = json.load(f)
                prev_user_data = backup.get('user_data', {})
                logger.info("📁 Резервные данные профиля загружены")
    except Exception as e:
        logger.error(f"Ошибка загрузки резервных данных: {e}")

async def main():
    await load_backup_data()
    await client.start()
    clear_console()
    
    print("🕵️ User Monitor by @bengamin_button & @xillenadapter")
    print("=" * 50)
    
    logger.info("Клиент запущен. Загрузка данных...")
    
    logger.info("Загрузка диалогов для кэша...")
    await client.get_dialogs()
    
    target_entity = await client.get_entity(target_user_input)
    global target_user_id
    target_user_id = target_entity.id
    
    await send_telegram_message(f"🔍 <b>Мониторинг активирован</b>\nID: {target_user_id}\nВремя: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    await check_profile_diff(target_entity)

    logger.info(f"🎯 НАБЛЮДЕНИЕ АКТИВИРОВАНО ЗА ID: {target_user_id}")
    logger.info(f"⏱️ Проверка профиля каждые {POLL_INTERVAL_SECONDS} секунд")
    logger.info("📄 Логи сохраняются в user_monitor.log")
    logger.info("⏹️ Ctrl+C для выхода")
    
    asyncio.create_task(profile_poller())
    
    try:
        await client.run_until_disconnected()
    finally:
        await save_backup_data()
        await send_telegram_message(f"🛑 <b>Мониторинг остановлен</b>\nID: {target_user_id}\nВремя: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("🛑 Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
    finally:
        if client.is_connected():
            client.loop.run_until_complete(client.disconnect())
        logger.info("📴 Клиент Telegram отключен")