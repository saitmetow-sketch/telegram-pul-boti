import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

# ==========================================
# ⚙️ BU YERGA O'Z SOZLAMALARINGIZNI YOZING
# ==========================================
API_TOKEN = 'SIZNING_BOT_TOKENINGIZ'  # BotFather'dan olingan token
CHANNEL_USERNAME = (
    '@sizning_kanal_username'  # Majburiy obuna kanal (masalan: @kanal_nomi)
)
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingiz (masalan: 987654321)
BONUS_AMOUNT = 500  # Har bir taklif uchun beriladigan bonus (so'm)
MIN_WITHDRAW = 10000  # Pul chiqarish uchun minimal summa (so'm)
# ==========================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# --- FSM (Rassilka uchun holatlar) ---
class AdminState(StatesGroup):
  waiting_for_broadcast = State()


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
  cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
  user = cursor.fetchone()
  if not user:
    cursor.execute(
        'INSERT INTO users (user_id, balance, referrals) VALUES (?, ?, ?)',
        (user_id, 0, 0),
    )
    conn.commit()
  conn.close()


def get_user(user_id):
  conn = sqlite3.connect('bot_database.db')
  cursor = conn.cursor()
  cursor.execute('SELECT balance, referrals FROM users WHERE user_id = ?', (user_id,))
  user = cursor.fetchone()
  conn.close()
  return user


def update_balance_and_ref(referrer_id):
  conn = sqlite3.connect('bot_database.db')
  cursor = conn.cursor()
  cursor.execute(
      'UPDATE users SET balance = balance + ?, referrals = referrals + 1 WHERE'
      ' user_id = ?',
      (BONUS_AMOUNT, referrer_id),
  )
  conn.commit()
  conn.close()


def get_total_users():
  conn = sqlite3.connect('bot_database.db')
  cursor = conn.cursor()
  cursor.execute('SELECT COUNT(*) FROM users')
  count = cursor.fetchone()[0]
  conn.close()
  return count


def get_all_users():
  conn = sqlite3.connect('bot_database.db')
  cursor = conn.cursor()
  cursor.execute('SELECT user_id FROM users')
  users = cursor.fetchall()
  conn.close()
  return users


# --- OBUNANI TEKSHIRISH ---
async def check_subscription(user_id: int):
  try:
    member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
    if member.status in ['member', 'creator', 'administrator']:
      return True
  except Exception:
    return False
  return False


# --- START BUYrug'I ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
  db_start()
  user_id = message.from_user.id
  args = message.get_args()

  add_user(user_id)

  # Referal orqali kirgan bo'lsa
  if args and args.isdigit():
    referrer_id = int(args)
    if referrer_id != user_id:
      try:
        update_balance_and_ref(referrer_id)
        await bot.send_message(
            referrer_id,
            f'🎉 Tabriklaymiz! Sizning havolangiz orqali 1 kishi qo\'shildi.'
            f' Balansingizga {BONUS_AMOUNT} so\'m qo\'shildi!',
        )
      except:
        pass

  # Obunani tekshirish
  is_subscribed = await check_subscription(user_id)
  if not is_subscribed:
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            'Kanalga obuna bo\'lish 🔔', url=f'https://t.me/{CHANNEL_USERNAME[1:]}'
        )
    )
    markup.add(
        types.InlineKeyboardButton('Azo bo\'ldim ✅', callback_data='check_sub')
    )
    await message.reply(
        'Botdan foydalanish uchun quyidagi homiy kanalimizga obuna bo\'ling va'
        ' "Azo bo\'ldim" tugmasini bosing:',
        reply_markup=markup,
    )
    return

  await send_main_menu(message)


async def send_main_menu(message: types.Message):
  user_id = message.from_user.id
  user_data = get_user(user_id)

  bot_info = await bot.get_me()
  ref_link = f'https://t.me/{bot_info.username}?start={user_id}'

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.row('💳 Balans', '🔗 Referal havola')
  markup.row('📤 Pul chiqarish')

  if user_id == ADMIN_ID:
    markup.row('🛠 Admin Paneli')

  await message.answer(
      f'👋 Salom, {message.from_user.first_name}!\n\n'
      'Botimiz yordamida do\'stlaringizni taklif qilib pul topishingiz'
      ' mumkin.\n'
      f'📌 Har bir taklif qilingan do\'st uchun: **{BONUS_AMOUNT} so\'m**\n\n'
      f'🔗 Sizning referal havolangiz:\n{ref_link}',
      reply_markup=markup,
  )


@dp.callback_query_handler(text='check_sub')
async def cb_check_sub(call: types.CallbackQuery):
  is_subscribed = await check_subscription(call.from_user.id)
  if is_subscribed:
    await call.message.delete()
    await send_main_menu(call.message)
  else:
    await call.answer(
        'Siz hali kanalga obuna bo\'lmadingiz!', show_alert=True
    )


# --- ASOSIY MENYU TUGMALARI ---
@dp.message_handler(text='💳 Balans')
async def show_balance(message: types.Message):
  user_data = get_user(message.from_user.id)
  if user_data:
    balance, referrals = user_data[0], user_data[1]
    await message.reply(
        f'💳 Sizning balansingiz: {balance} so\'m\n👥 Taklif qilgan do\'stlaringiz'
        f' soni: {referrals} ta'
    )


@dp.message_handler(text='🔗 Referal havola')
async def show_link(message: types.Message):
  bot_info = await bot.get_me()
  user_id = message.from_user.id
  ref_link = f'https://t.me/{bot_info.username}?start={user_id}'
  await message.reply(
      '👥 Do\'stlaringizni taklif qilish uchun maxsus havola:\n\n'
      f'{ref_link}\n\nUshbu havolani do\'stlaringizga yuboring!'
  )


@dp.message_handler(text='📤 Pul chiqarish')
async def withdraw_money(message: types.Message):
  user_data = get_user(message.from_user.id)
  if user_data:
    balance = user_data[0]
    if balance >= MIN_WITHDRAW:
      await message.reply(
          '📤 Pul chiqarish uchun karta raqamingiz va F.I.Sh ni yuboring'
          ' (Masalan: 8600... Alisherov):\nAdminlar tez orada ko\'rib chiqadi.'
      )
    else:
      await message.reply(
          f'❌ Balansingiz yetarli emas!\nMinimal chiqarish summasi:'
          f' {MIN_WITHDRAW} so\'m.'
      )


# --- ADMIN MENYU VA FUNKSIYALARI ---
@dp.message_handler(text='🛠 Admin Paneli')
async def admin_panel(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.row('📊 Statistika', '📢 Xabar yuborish (Rassilka)')
  markup.row('🔙 Asosiy menyu')

  await message.reply(
      '🛠 Admin paneliga xush kelibsiz!', reply_markup=markup
  )


@dp.message_handler(text='📊 Statistika')
async def admin_stats(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return

  total_users = get_total_users()
  await message.reply(f'📊 **Bot statistikasi:**\n\n👥 Jami foydalanuvchilar: {total_users} ta')


@dp.message_handler(text='📢 Xabar yuborish (Rassilka)')
async def admin_broadcast(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return

  await AdminState.waiting_for_broadcast.set()
  await message.reply(
      '📢 Barcha foydalanuvchilarga yubormoqchi bo\'lgan xabaringizni yuboring'
      ' (Matn, rasm yoki video):'
  )


@dp.message_handler(
    state=AdminState.waiting_for_broadcast, content_types=types.ContentTypes.ANY
)
async def process_broadcast(message: types.Message, state: FSMContext):
  if message.from_user.id != ADMIN_ID:
    return

  users = get_all_users()
  success = 0
  failed = 0

  await message.reply('⏳ Xabar yuborish boshlandi...')

  for row in users:
    u_id = row[0]
    try:
      await message.send_copy(chat_id=u_id)
      success += 1
    except:
      failed += 1

  await state.finish()
  await message.reply(
      f'✅ Xabar yuborish yakunlandi!\n\nMuvaffaqiyatli: {success} ta\nXatolik'
      f' (bloklaganlar): {failed} ta'
  )


@dp.message_handler(text='🔙 Asosiy menyu')
async def back_to_main(message: types.Message):
  await send_main_menu(message)


if __name__ == '__main__':
  db_start()
  executor.start_polling(dp, skip_updates=True)
