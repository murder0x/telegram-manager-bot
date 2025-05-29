from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from database import add_application

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    kb = [[KeyboardButton(text="Оставить заявку")] ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "Добро пожаловать! 👋\n"
        "Я помогу вам оставить заявку на консультацию.\n"
        "Нажмите кнопку ниже, чтобы начать.",
        reply_markup=keyboard
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Я бот для сбора заявок на консультацию. 📝\n"
        "Вы можете оставить заявку, указав ваше имя, телефон и тему консультации.\n"
        "Для начала, используйте команду /start или нажмите кнопку 'Оставить заявку'."
    )

class ApplicationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_topic = State()
    waiting_for_confirmation = State()

# Используем магический фильтр F для "Оставить заявку"
@router.message(F.text.func(lambda text: text.lower().strip() == "оставить заявку"))
async def start_application_form(message: Message, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Пожалуйста, введите ваше имя:", reply_markup=ReplyKeyboardRemove())

@router.message(ApplicationForm.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ApplicationForm.waiting_for_phone)
    await message.answer("Спасибо! Теперь введите ваш номер телефона:")

@router.message(ApplicationForm.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(ApplicationForm.waiting_for_topic)
    await message.answer("Отлично! Укажите тему консультации:")

@router.message(ApplicationForm.waiting_for_topic)
async def process_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    user_data = await state.get_data()
    await message.answer(
        f"Спасибо! Давайте проверим данные:\n"
        f"Имя: {user_data['name']}\n"
        f"Телефон: {user_data['phone']}\n"
        f"Тема: {user_data['topic']}\n\n"
        f"Все верно?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да, отправить"), KeyboardButton(text="Нет, начать заново")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(ApplicationForm.waiting_for_confirmation)

@router.message(ApplicationForm.waiting_for_confirmation, F.text.func(lambda text: text.lower().strip() == "да, отправить"))
async def process_confirmation_yes(message: Message, state: FSMContext, bot: Bot, notification_bot_token: str, admin_ids_for_notifications: list[str]):
    user_data = await state.get_data()
    try:
        add_application(user_data['name'], user_data['phone'], user_data['topic'])
        await message.answer(
            "Спасибо! Ваша заявка принята. Мы скоро с вами свяжемся. ✅",
            reply_markup=ReplyKeyboardRemove()
        )

        if notification_bot_token and admin_ids_for_notifications:
            notification_bot = Bot(token=notification_bot_token)
            try:
                admin_message_text = (
                    f"📬 Новая заявка на консультацию (через @{bot.id}):\n"
                    f"👤 Имя: {user_data['name']}\n"
                    f"📞 Телефон: {user_data['phone']}\n"
                    f"📌 Тема: {user_data['topic']}"
                )
                for admin_id_str in admin_ids_for_notifications:
                    try:
                        await notification_bot.send_message(admin_id_str, admin_message_text)
                        logging.info(f"Notification sent to admin ID {admin_id_str} via notification bot.")
                    except Exception as e_send_individual:
                        logging.error(f"Error sending notification to admin ID {admin_id_str}: {e_send_individual}")
            except Exception as e_notify_setup:
                logging.error(f"Error setting up notification sender or sending notifications: {e_notify_setup}")
            finally:
                await notification_bot.session.close()
        else:
            logging.warning("NOTIFICATION_BOT_TOKEN or ADMIN_IDS for notifications not set/empty. Admin(s) will not be notified.")

    except Exception as e_main:
        logging.error(f"Error saving application: {e_main}")
        await message.answer(
            "Произошла ошибка при сохранении вашей заявки. Пожалуйста, попробуйте еще раз позже. ⚠️",
            reply_markup=ReplyKeyboardRemove()
        )
    finally:
        await state.clear()
        kb_start = [[KeyboardButton(text="Оставить заявку")]]
        keyboard_start = ReplyKeyboardMarkup(keyboard=kb_start, resize_keyboard=True)
        await message.answer("Вы можете оставить еще одну заявку или использовать команду /help.", reply_markup=keyboard_start)

@router.message(ApplicationForm.waiting_for_confirmation, F.text.func(lambda text: text.lower().strip() == "нет, начать заново"))
async def process_confirmation_no(message: Message, state: FSMContext):
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer("Хорошо, давайте начнем заново. Введите ваше имя:", reply_markup=ReplyKeyboardRemove())

@router.message(ApplicationForm.waiting_for_confirmation)
async def process_confirmation_invalid(message: Message, state: FSMContext):
    await message.answer(
        "Пожалуйста, используйте кнопки для ответа: 'Да, отправить' или 'Нет, начать заново'.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да, отправить"), KeyboardButton(text="Нет, начать заново")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )