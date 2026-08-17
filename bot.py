import logging, sqlite3, os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('API_TOKEN') 
ADMIN_ID = 8588301820       
BONUS_AMOUNT = 3000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class UserState(StatesGroup):
    waiting_for_message = State()

# --- BAZA BILAN ISHLASH ---
def db_start():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            balance REAL DEFAULT 0, 
            referrals INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance, referrals FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_balance(referrer_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE user_id = ?', (BONUS_AMOUNT, referrer_id))
    conn.commit()
    conn.close()

# --- START ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    db_start()
    user_id = message.from_user.id
    add_user(user_id)
    args = message.get_args()
    
    if args and args.isdigit() and int(args) != user_id:
        update_balance(int(args))
        try:
            await bot.send_message(int(args), f"🎉 Yangi do'stingiz qo'shildi! Hisobingizga {BONUS_AMOUNT} so'm qo'shildi.")
        except:
            pass

    await main_menu(message)

async def main_menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('💰 Pul ishlash', '👤 Profil')
    markup.row('📞 Admin bilan bog\'lanish')
    await message.answer("Asosiy menyu:", reply_markup=markup)

# --- MENYU TUGMALARI ---
@dp.message_handler(text='💰 Pul ishlash')
async def earn_money(message: types.Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    await message.answer(
        f"💰 **Pul ishlash bo'limi**\n\n"
        f"Do'stlaringizni taklif qiling va har bir taklif uchun **{BONUS_AMOUNT} so'm** oling!\n\n"
        f"🔗 Sizning referal havolangiz:\n{ref_link}"
    )

@dp.message_handler(text='👤 Profil')
async def profile(message: types.Message):
    user_data = get_user(message.from_user.id)
    if user_data:
        balance, referrals = user_data[0], user_data[1]
        await message.answer(
            f"👤 **Sizning profilingiz:**\n\n"
            f"💳 Balansingiz: {balance} so'm\n"
            f"👥 Taklif qilganlaringiz: {referrals} ta"
        )

@dp.message_handler(text='📞 Admin bilan bog\'lanish')
async def contact_admin(message: types.Message):
    await message.answer("Admin uchun yubormoqchi bo'lgan xabaringizni yozing:")
    await UserState.waiting_for_message.set()

@dp.message_handler(state=UserState.waiting_for_message)
async def send_message_to_admin(message: types.Message, state: FSMContext):
    user = message.from_user
    username_text = f"@{user.username}" if user.username else "Username yo'q"
    
    await bot.send_message(
        ADMIN_ID,
        f"📩 **Yangi xabar!**\n\n"
        f"Foydalanuvchi: {user.full_name} ({username_text})\n"
        f"ID: `{user.id}`\n\n"
        f"Xabar: {message.text}"
    )
    await message.answer("Xabaringiz adminga muvaffaqiyatli yuborildi! Tez orada javob berishadi.")
    await state.finish()

if __name__ == '__main__':
    db_start()
    executor.start_polling(dp, skip_updates=True)
