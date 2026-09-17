import os
import sqlite3
from flask import Flask, request
import telebot
from telebot import types
from groq import Groq

BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
ADMIN_ID = 966607076
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

DB_NAME = "/home/Acab7/academy_system.db" if os.path.exists("/home/Acab7") else "academy_system.db"

try:
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception:
    groq_client = None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

init_db()
user_states = {}

def save_user(user):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (user.id, user.username or "", user.first_name or ""))
        conn.commit()
        conn.close()
    except Exception:
        pass

def ask_groq(prompt):
    if not groq_client:
        return "مرحباً بك في أكاديمية النيزك! 🚀\n(تنبيه: مفتاح Groq غير مفعل، يرجى الاستعانة بخيار التذاكر)."
    try:
        sys_msg = "أنت المساعد الذكي الرسمي لأكاديمية النيزك (Nayzak Academy). قدم إجابات سريعة ومحترفة."
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
        )
        return res.choices[0].message.content
    except Exception:
        return "عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ai = types.InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="mode_ai")
    btn_ticket = types.InlineKeyboardButton("🎫 فتح تذكرة دعم", callback_data="open_ticket")
    btn_courses = types.InlineKeyboardButton("📚 دورات الأكاديمية", callback_data="courses_info")
    btn_contact = types.InlineKeyboardButton("📞 التواصل مع الإدارة", callback_data="contact_human")
    markup.add(btn_ai, btn_ticket, btn_courses, btn_contact)
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel"))

    text = f"مرحباً بك {message.from_user.first_name} في **أكاديمية النيزك**! 🚀\nأنا بوت الدعم الفني الذكي، كيف يمكنني مساعدتك؟"
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data == "mode_ai":
            bot.answer_callback_query(call.id, "الذكاء الاصطناعي فعال!")
            bot.send_message(call.message.chat.id, "💬 تفضل بكتابة سؤالك وسيقوم المساعد الذكي بالرد عليك:")
        elif call.data == "courses_info":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📚 **دورات أكاديمية النيزك:**\n• البرمجة\n• التداول\n• الشبكات", parse_mode="Markdown")
        elif call.data == "open_ticket":
            user_states[call.from_user.id] = "WAITING_TICKET"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "🎫 اكتب تفاصيل مشكلتك لإرسالها للدعم:")
    except Exception:
        pass

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    uid = message.from_user.id
    save_user(message.from_user)
    if user_states.get(uid) == "WAITING_TICKET":
        user_states.pop(uid, None)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO tickets (user_id, subject) VALUES (?, ?)", (uid, message.text))
        tid = c.lastrowid
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ تم فتح تذكرتك برقم **#{tid}**.")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, ask_groq(message.text))

@app.route('/')
def index():
    return "Nayzak Bot Active", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        if update:
            bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
