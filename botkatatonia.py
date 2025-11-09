import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import re

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Токен бота від BotFather
BOT_TOKEN = "8509936252:AAENpPyHXcVI_7qATchZ3-thUezKI9v9M54"

# ID адміністратора (ваш Telegram ID)
ADMIN_ID = 5867900935

# Номер картки для оплати
PAYMENT_CARD = "253052990000026001030703324"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Стани для FSM (Finite State Machine)
class OrderStates(StatesGroup):
    waiting_for_product_name = State()
    waiting_for_size = State()
    waiting_for_phone = State()
    waiting_for_full_name = State()
    waiting_for_city = State()
    waiting_for_post_office = State()
    waiting_for_payment = State()


# База даних замовлень (в реальному проекті використовуйте SQLite, PostgreSQL тощо)
orders_db = {}


# Головне меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Придбати продукт")],
            [KeyboardButton(text="Задати питання")]
        ],
        resize_keyboard=True
    )
    return keyboard


# Кнопки з розмірами
def get_size_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="XS", callback_data="size_XS"),
                InlineKeyboardButton(text="S", callback_data="size_S"),
                InlineKeyboardButton(text="M", callback_data="size_M")
            ],
            [
                InlineKeyboardButton(text="L", callback_data="size_L"),
                InlineKeyboardButton(text="XL", callback_data="size_XL"),
                InlineKeyboardButton(text="XXL", callback_data="size_XXL")
            ],
            [
                InlineKeyboardButton(text="XXXL", callback_data="size_XXXL")
            ]
        ]
    )
    return keyboard


# Кнопка "Готово"
def get_payment_confirmation_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Готово ✅", callback_data="payment_done")]
        ]
    )
    return keyboard


# Команда /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"Вітаю, {message.from_user.first_name}! 👋\n\n"
        "Оберіть дію:",
        reply_markup=get_main_menu()
    )


# Кнопка "Придбати продукт"
@dp.message(F.text == "Придбати продукт")
async def buy_product(message: Message, state: FSMContext):
    await message.answer(
        "📦 Введіть назву продукту:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state(OrderStates.waiting_for_product_name)


# Кнопка "Задати питання"
@dp.message(F.text == "Задати питання")
async def ask_question(message: Message, state: FSMContext):
    await message.answer(
        "❓ Напишіть ваше питання, і я передам його адміністратору:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Назад")]],
            resize_keyboard=True
        )
    )
    await state.set_state("waiting_for_question")


# Отримання питання від користувача
@dp.message(lambda message: message.text and message.text != "◀️ Назад", StateFilter("waiting_for_question"))
async def forward_question_to_admin(message: Message, state: FSMContext):
    user = message.from_user
    question_text = (
        f"❓ Нове питання від користувача:\n\n"
        f"👤 Ім'я: {user.first_name} {user.last_name or ''}\n"
        f"🆔 Username: @{user.username or 'немає'}\n"
        f"🔢 ID: {user.id}\n\n"
        f"Питання: {message.text}"
    )
    
    try:
        await bot.send_message(ADMIN_ID, question_text)
        await message.answer(
            "✅ Ваше питання успішно надіслано адміністратору!\n"
            "Очікуйте на відповідь.",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        await message.answer(
            "❌ Помилка відправки питання. Спробуйте пізніше.",
            reply_markup=get_main_menu()
        )
    
    await state.clear()


# Отримання назви продукту
@dp.message(OrderStates.waiting_for_product_name)
async def process_product_name(message: Message, state: FSMContext):
    if message.text == "◀️ Назад":
        await state.clear()
        await message.answer("Повернулись до головного меню", reply_markup=get_main_menu())
        return
    
    await state.update_data(product_name=message.text)
    await message.answer(
        f"Ви обрали: {message.text}\n\n"
        "👕 Оберіть розмір:",
        reply_markup=get_size_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_size)


# Обробка вибору розміру
@dp.callback_query(F.data.startswith("size_"))
async def process_size(callback: CallbackQuery, state: FSMContext):
    size = callback.data.split("_")[1]
    await state.update_data(size=size)
    
    await callback.message.edit_text(
        f"✅ Розмір обрано: {size}\n\n"
        f"👕 Оберіть розмір:",
        reply_markup=get_size_keyboard()
    )
    
    await callback.message.answer(
        "📱 Введіть ваш номер телефону (від 9 до 12 цифр):\n"
        "Приклад: 380501234567"
    )
    await state.set_state(OrderStates.waiting_for_phone)
    await callback.answer()


# Отримання номера телефону
@dp.message(OrderStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = re.sub(r'\D', '', message.text)  # Видаляємо все крім цифр
    
    if len(phone) < 9 or len(phone) > 12:
        await message.answer(
            "❌ Невірний формат номера телефону.\n"
            "Введіть від 9 до 12 цифр:"
        )
        return
    
    await state.update_data(phone=phone)
    await message.answer(
        "👤 Введіть ваше ім'я та прізвище:"
    )
    await state.set_state(OrderStates.waiting_for_full_name)


# Отримання імені та прізвища
@dp.message(OrderStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer(
        "🏙 Введіть назву міста:"
    )
    await state.set_state(OrderStates.waiting_for_city)


# Отримання міста
@dp.message(OrderStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "📮 Введіть назву/номер відділення пошти:"
    )
    await state.set_state(OrderStates.waiting_for_post_office)


# Отримання відділення пошти
@dp.message(OrderStates.waiting_for_post_office)
async def process_post_office(message: Message, state: FSMContext):
    await state.update_data(post_office=message.text)
    
    data = await state.get_data()
    
    # Зберігаємо замовлення
    order_id = len(orders_db) + 1
    orders_db[order_id] = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        **data
    }
    
    await state.update_data(order_id=order_id)
    
    await message.answer(
        f"💳 Переведіть кошти на картку:\n\n"
        f"<code>{PAYMENT_CARD}</code>\n\n"
        f"Після оплати натисніть кнопку 'Готово'",
        parse_mode="HTML",
        reply_markup=get_payment_confirmation_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_payment)


# Підтвердження оплати
@dp.callback_query(F.data == "payment_done")
async def payment_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('order_id')
    
    # Повідомлення адміністратору
    admin_message = (
        f"🛍 НОВЕ ЗАМОВЛЕННЯ #{order_id}\n\n"
        f"📦 Продукт: {data['product_name']}\n"
        f"👕 Розмір: {data['size']}\n"
        f"📱 Телефон: {data['phone']}\n"
        f"👤 ПІБ: {data['full_name']}\n"
        f"🏙 Місто: {data['city']}\n"
        f"📮 Відділення: {data['post_office']}\n\n"
        f"👤 Користувач: @{callback.from_user.username or 'немає'} (ID: {callback.from_user.id})"
    )
    
    try:
        await bot.send_message(ADMIN_ID, admin_message)
    except Exception as e:
        logging.error(f"Помилка відправки адміну: {e}")
    
    await callback.message.edit_text(
        "✅ Дякуємо за замовлення!\n\n"
        "⏳ Ваше замовлення прийнято в обробку.\n"
        "Очікуйте на підтвердження від адміністратора."
    )
    
    await callback.message.answer(
        "Бажаєте щось ще?",
        reply_markup=get_main_menu()
    )
    
    await state.clear()
    await callback.answer()


# Кнопка "Назад"
@dp.message(F.text == "◀️ Назад")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Повернулись до головного меню", reply_markup=get_main_menu())


# Імпорт StateFilter для обробки питань
from aiogram.filters import StateFilter


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())