import asyncio
import logging
import configparser
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramAPIError
from rich.console import Console
from rich.prompt import Prompt
from handlers import router as main_router
from database import init_db

console = Console()

EMOJI_CHECK = ":white_check_mark:"
EMOJI_CROSS = ":cross_mark:"
EMOJI_KEY = ":key:"
EMOJI_WARNING = ":warning:"
EMOJI_INFO = ":information_source:"

async def validate_token(token: str, token_name: str, silent_if_valid: bool = False) -> bool:
    """Проверяет формат токена и его действительность через Telegram API."""
    if not token or ':' not in token:
        if not silent_if_valid: console.print(f"    {EMOJI_CROSS} Формат токена [bold magenta]{token_name}[/bold magenta] неверный. Он должен содержать ':'.", style="red")
        return False
    
    bot_id_part = token.split(':', 1)[0]
    if not bot_id_part.isdigit():
        if not silent_if_valid: console.print(f"    {EMOJI_CROSS} Формат ID в токене [bold magenta]{token_name}[/bold magenta] неверный (часть перед ':' должна быть числовой).", style="red")
        return False

    temp_bot = Bot(token=token)
    try:
        await temp_bot.get_me()
        if not silent_if_valid: console.print(f"    {EMOJI_CHECK} Токен [bold magenta]{token_name}[/bold magenta] действителен.", style="green")
        return True
    except TelegramAPIError as e:
        if not silent_if_valid:
            error_message = str(e).lower()
            if "token is invalid" in error_message or "unauthorized" in error_message:
                 console.print(f"    {EMOJI_CROSS} Токен [bold magenta]{token_name}[/bold magenta] недействителен (API: Авторизация не удалась). Попробуйте снова.", style="red")
            elif "bot token is already in use" in error_message:
                console.print(f"    {EMOJI_WARNING} Токен [bold magenta]{token_name}[/bold magenta] уже используется. Если это неожиданно, проверьте другие запущенные экземпляры.", style="yellow")
                return False 
            else:
                console.print(f"    {EMOJI_CROSS} Ошибка при проверке токена [bold magenta]{token_name}[/bold magenta]: {e}. Попробуйте снова.", style="red")
        return False
    finally:
        await temp_bot.session.close()

async def request_token_interactive(token_name: str, purpose_message: str, is_mandatory: bool) -> str:
    while True:
        prompt_msg = f"    Введите [bold white]{token_name}[/bold white] ({purpose_message})"
        if not is_mandatory:
            prompt_msg += " (можно оставить пустым, нажав Enter)"
        
        token_input = Prompt.ask(prompt_msg)

        if not token_input.strip():
            if not is_mandatory:
                return "" 
            else:
                console.print(f"    {EMOJI_CROSS} {token_name} не может быть пустым. Пожалуйста, введите действительный токен.", style="red")
                continue
        
        if await validate_token(token_input, token_name):
            return token_input

async def load_or_request_config():
    config = configparser.ConfigParser()
    config_file = 'config.ini'
    needs_saving = False

    if not config.read(config_file):
        console.print(f"{EMOJI_WARNING} Файл '{config_file}' не найден. Будет создан новый.", style="yellow")
        config.add_section('Tokens')
        needs_saving = True
        current_user_token = None
        current_notif_token = None
        current_admin_ids = None
    else:
        if not config.has_section('Tokens'):
            console.print(f"{EMOJI_WARNING} Секция [Tokens] отсутствует в '{config_file}'. Создаю...", style="yellow")
            config.add_section('Tokens')
            needs_saving = True
        current_user_token = config.get('Tokens', 'USER_FACING_BOT_TOKEN', fallback=None)
        current_notif_token = config.get('Tokens', 'NOTIFICATION_BOT_TOKEN', fallback=None)
        current_admin_ids = config.get('Tokens', 'ADMIN_IDS', fallback=None)

    valid_user_token = False
    if current_user_token:
        console.print(f"{EMOJI_INFO} Проверка USER_FACING_BOT_TOKEN из config.ini...", style="dim")
        if await validate_token(current_user_token, "USER_FACING_BOT_TOKEN (из config.ini)", silent_if_valid=True):
            valid_user_token = True
        else:
            console.print(f"    {EMOJI_WARNING} USER_FACING_BOT_TOKEN из config.ini недействителен или не прошел проверку.", style="yellow")
            needs_saving = True
            
    if not valid_user_token:
        console.print(f"{EMOJI_KEY} Запрос USER_FACING_BOT_TOKEN.", style="cyan")
        current_user_token = await request_token_interactive("USER_FACING_BOT_TOKEN", "для взаимодействия с пользователями", is_mandatory=True)
        needs_saving = True
    config.set('Tokens', 'USER_FACING_BOT_TOKEN', current_user_token)

    valid_notif_token_or_empty = False
    if current_notif_token: 
        console.print(f"{EMOJI_INFO} Проверка NOTIFICATION_BOT_TOKEN из config.ini...", style="dim")
        if await validate_token(current_notif_token, "NOTIFICATION_BOT_TOKEN (из config.ini)", silent_if_valid=True):
            valid_notif_token_or_empty = True
        else:
            console.print(f"    {EMOJI_WARNING} NOTIFICATION_BOT_TOKEN из config.ini недействителен или не прошел проверку.", style="yellow")
            needs_saving = True 
    elif current_notif_token == "": 
        console.print(f"{EMOJI_INFO} NOTIFICATION_BOT_TOKEN в config.ini пуст (пропускается).", style="dim")
        valid_notif_token_or_empty = True
        
    if not valid_notif_token_or_empty: 
        console.print(f"{EMOJI_KEY} Запрос NOTIFICATION_BOT_TOKEN.", style="cyan")
        current_notif_token = await request_token_interactive("NOTIFICATION_BOT_TOKEN", "для отправки уведомлений администраторам", is_mandatory=False)
        needs_saving = True
    config.set('Tokens', 'NOTIFICATION_BOT_TOKEN', current_notif_token)

    if current_admin_ids is None or current_admin_ids == '': 
        console.print(f"{EMOJI_KEY} Запрос ADMIN_IDS (можно оставить пустым).", style="cyan")
        current_admin_ids = Prompt.ask(f"    Введите [bold white]ADMIN_IDS[/bold white] (Telegram ID администраторов, через запятую)")
        needs_saving = True
    config.set('Tokens', 'ADMIN_IDS', current_admin_ids)

    if needs_saving:
        save_config(config, config_file)

    return config

def save_config(config, filename='config.ini'):
    with open(filename, 'w') as configfile:
        config.write(configfile)
    console.print(f"{EMOJI_CHECK} Конфигурация сохранена в [bold cyan]{filename}[/bold cyan]", style="green")

async def get_entity_details(user_facing_bot_token: str, notification_bot_token: str | None, admin_ids: list[str]):
    details = {
        "user_bot_id": None,
        "user_bot_name": None,
        "notification_bot_id": None,
        "notification_bot_name": None,
        "admin_details": []
    }

    if user_facing_bot_token:
        details["user_bot_id"] = user_facing_bot_token.split(':')[0]
        temp_user_bot = Bot(token=user_facing_bot_token)
        try:
            me = await temp_user_bot.get_me()
            details["user_bot_name"] = me.full_name
            if me.username:
                details["user_bot_name"] += f" (@{me.username})"
        except TelegramAPIError as e:
            console.print(f"    {EMOJI_WARNING} Не удалось получить имя основного бота (ID: {details['user_bot_id']}): {e}", style="yellow")
            details["user_bot_name"] = "[не удалось получить имя]"
        finally:
            await temp_user_bot.session.close()

    if notification_bot_token:
        details["notification_bot_id"] = notification_bot_token.split(':')[0]
        if details["notification_bot_id"] == details["user_bot_id"] and details["user_bot_name"] and "не удалось" not in details["user_bot_name"]:
             details["notification_bot_name"] = details["user_bot_name"]
        else:
            temp_notif_bot = Bot(token=notification_bot_token)
            try:
                me = await temp_notif_bot.get_me()
                details["notification_bot_name"] = me.full_name
                if me.username:
                    details["notification_bot_name"] += f" (@{me.username})"
            except TelegramAPIError as e:
                console.print(f"    {EMOJI_WARNING} Не удалось получить имя бота для уведомлений (ID: {details['notification_bot_id']}): {e}", style="yellow")
                details["notification_bot_name"] = "[не удалось получить имя]"
            finally:
                await temp_notif_bot.session.close()
    
    if admin_ids and user_facing_bot_token:
        query_bot = Bot(token=user_facing_bot_token)
        try:
            for admin_id in admin_ids:
                admin_info = {"id": admin_id, "name": "[не удалось получить имя]"}
                try:
                    chat = await query_bot.get_chat(chat_id=admin_id)
                    admin_info["name"] = chat.full_name
                    if chat.username:
                        admin_info["name"] += f" (@{chat.username})"
                except TelegramAPIError as e:
                    console.print(f"    {EMOJI_WARNING} Не удалось получить имя для админа ID {admin_id}: {e}", style="yellow")
                details["admin_details"].append(admin_info)
        finally:
            await query_bot.session.close()
            
    return details

async def main():
    init_db()
    config = await load_or_request_config()
    user_facing_bot_token = config.get('Tokens', 'USER_FACING_BOT_TOKEN', fallback='')
    notification_bot_token = config.get('Tokens', 'NOTIFICATION_BOT_TOKEN', fallback=None)
    admin_ids_str = config.get('Tokens', 'ADMIN_IDS', fallback='')
    if not user_facing_bot_token:
        console.print(f"{EMOJI_CROSS} ОШИБКА: USER_FACING_BOT_TOKEN не установлен или недействителен. Завершение работы.", style="bold red")
        return
    parsed_admin_ids = []
    if admin_ids_str:
        parsed_admin_ids = [id_str.strip() for id_str in admin_ids_str.split(',') if id_str.strip()]
        
    console.print(f"{EMOJI_CHECK} Токены обработаны, бот готовится к запуску.", style="bold green")

    entity_details = await get_entity_details(user_facing_bot_token, notification_bot_token, parsed_admin_ids)

    if entity_details["user_bot_id"]:
        bot_name_display = entity_details['user_bot_name'] if entity_details['user_bot_name'] else "[имя не определено]"
        console.print(f"    {EMOJI_INFO} Основной бот: [bold cyan]{bot_name_display}[/bold cyan] (ID: {entity_details['user_bot_id']})")

    if entity_details["notification_bot_id"]:
        bot_name_display = entity_details['notification_bot_name'] if entity_details['notification_bot_name'] else "[имя не определено]"
        console.print(f"    {EMOJI_INFO} Бот для уведомлений: [bold cyan]{bot_name_display}[/bold cyan] (ID: {entity_details['notification_bot_id']})")
    elif notification_bot_token: 
        console.print(f"    {EMOJI_WARNING} Токен бота для уведомлений указан, но не удалось получить его детали (возможно, недействителен).", style="yellow")
    else:
         console.print(f"    {EMOJI_INFO} Токен бота для уведомлений не указан.", style="dim")

    if parsed_admin_ids:
        console.print(f"    {EMOJI_INFO} Администраторы:")
        for admin_detail in entity_details["admin_details"]:
            console.print(f"        ID: [bold yellow]{admin_detail['id']}[/bold yellow], Имя: [bold yellow]{admin_detail['name']}[/bold yellow]")
    else:
        console.print(f"    {EMOJI_INFO} ID администраторов не указаны.", style="dim")

    bot = Bot(token=user_facing_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(main_router)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True, show_time=False, show_level=False, show_path=False)]
    )
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(logging.WARNING) 
    if not any(isinstance(h, RichHandler) for h in aiogram_logger.handlers):
         aiogram_logger.addHandler(RichHandler(console=console, rich_tracebacks=True, markup=True, show_time=False, show_level=False, show_path=False))
    aiogram_logger.propagate = False

    console.print(f"{EMOJI_CHECK} Бот запускается...", style="bold green")
    try:
        await dp.start_polling(bot, notification_bot_token=notification_bot_token, admin_ids_for_notifications=parsed_admin_ids)
    except Exception as e:
        console.print_exception(show_locals=True)
    finally:
        await bot.session.close()
        console.print(f"{EMOJI_CROSS} Бот остановлен.", style="bold red")

from rich.logging import RichHandler

if __name__ == '__main__':
    asyncio.run(main()) 