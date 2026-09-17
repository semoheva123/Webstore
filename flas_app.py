python3.11 -c '
code = """import os
import sqlite3
import logging
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
except Exception as e:
    groq_client = None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT,
            status TEXT DEFAULT "open",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()
user_states = {}

def save_user(user):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user.id, user.username or "", user.first_name or ""))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def ask_groq(prompt):
    if not groq_client:
        return "مرحباً بك في أكاديمية النيزك! 🚀\\n(تنبيه: مفتاح Groq غير مفعل حالياً، يمكنك اختيار فتح تذكرة دعم لمساعدتك)."
    try:
        system_instruction = (
            "أنت المساعد الذكي الرسمي لأكاديمية النيزك (Nayzak Academy).\\n"
            "دورك هو تقديم الدعم الفني والإجابة على استفسارات الطلاب بأسلوب مهذب ومحترف وسريع باللغة العربية.\\n"
            "تخصصات الأكاديمية: الدورات التدريبية، البرمجة، والتداول، والخدمات التقنية.\\n"
            "إذا كان السؤال يتطلب تدخلاً بشرياً، وجه المستخدم لفتح تذكرة دعم فني."
        )
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"عذراً، حدث خطأ أثناء الاتصال بالذكاء الاصطناعي. يرجى استخدام أمر التذاكر للمساعدة."

@bot.message_handler(commands=["start"])
def send_welcome(message):
    save_user(message.from_user)
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ai = types.InlineKeyboardButton("🤖 الذكاء الاصطناعي", callback_data="mode_ai")
    btn_ticket = types.InlineKeyboardButton("🎫 فتح تذكرة دعم", callback_data="open_ticket")
    btn_courses = types.InlineKeyboardButton("📚 دورات الأكاديمية", callback_data="courses_info")
    btn_contact = types.InlineKeyboardButton("📞 التواصل مع الإدارة", callback_data="contact_human")
    markup.add(btn_ai, btn_ticket, btn_courses, btn_contact)

    if message.from_user.id == ADMIN_ID:
        btn_admin = types.InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data="admin_panel")
        markup.add(btn_admin)

    text = (
        f"مرحباً بك {message.from_user.first_name} في **أكاديمية النيزك**! 🚀\\n\\n"
        "أنا بوت الدعم الفني الذكي، كيف يمكنني مساعدتك اليوم؟\\n"
        "اختر من القائمة أدناه أو اكتب استفسارك مباشرة لتلقي الإجابة."
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⚠️ عذراً، هذا الأمر مخصص لأدمن النظام فقط.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_users = types.InlineKeyboardButton("👥 عدد المستخدمين", callback_data="admin_users_count")
    btn_tickets = types.InlineKeyboardButton("📋 التذاكر المفتوحة", callback_data="admin_view_tickets")
    btn_broadcast = types.InlineKeyboardButton("📢 إذاعة عامة", callback_data="admin_broadcast")
    markup.add(btn_users, btn_tickets, btn_broadcast)

    bot.reply_to(message, "🛠 **لوحة التحكم والإدارة - أكاديمية النيزك**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data == "mode_ai":
            bot.answer_callback_query(call.id, "نموذج الذكاء الاصطناعي فعال!")
            bot.send_message(call.message.chat.id, "💬 تفضل بكتابة سؤالك وسيقوم مساعد Groq الذكي بالرد عليك فوراً:")
        
        elif call.data == "courses_info":
            bot.answer_callback_query(call.id)
            text = (
                "📚 **دورات وخدمات أكاديمية النيزك:**\\n\\n"
                "• البرمجة وتطوير التطبيقات\\n"
                "• تحليل الأسواق والتداول (SMC / Price Action)\\n"
                "• خدمات الشبكات والسيرفرات\\n\\n"
                "للاستفسار عن التسجيل، اكتب سؤالك هنا مباشرة!"
            )
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

        elif call.data == "open_ticket":
            user_states[call.from_user.id] = "WAITING_TICKET_MSG"
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "🎫 يرجى كتابة تفاصيل مشكلتك أو استفسارك لإرسالها لفريق الدعم الفني:")

        elif call.data == "contact_human":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "📞 يمكنك التواصل المباشر مع المسؤول أو فتح تذكرة دعم ليتم متابعتك.")

        elif call.data == "admin_panel":
            if call.from_user.id == ADMIN_ID:
                admin_command(call.message)

        elif call.data == "admin_users_count":
            if call.from_user.id == ADMIN_ID:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                conn.close()
                bot.answer_callback_query(call.id, f"عدد المشتركين: {count}", show_alert=True)

        elif call.data == "admin_view_tickets":
            if call.from_user.id == ADMIN_ID:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT id, user_id, subject FROM tickets WHERE status=\'open\' ORDER BY id DESC LIMIT 10")
                tickets = cursor.fetchall()
                conn.close()
                if not tickets:
                    bot.send_message(call.message.chat.id, "✅ لا يوجد تذاكر مفتوحة حالياً.")
                else:
                    msg = "📋 **التذاكر المفتوحة:**\\n\\n"
                    for t in tickets:
                        msg += f"🔹 تذكرة #{t[0]} | مستخدم: `{t[1]}`\\nالنص: {t[2]}\\n------------------\\n"
                    bot.send_message(call.message.chat.id, msg, parse_mode="Markdown")

        elif call.data == "admin_broadcast":
            if call.from_user.id == ADMIN_ID:
                user_states[call.from_user.id] = "WAITING_BROADCAST_MSG"
                bot.send_message(call.message.chat.id, "📢 أرسل الرسالة التي ترغب بنشرها لجميع المستخدمين:")

    except Exception as e:
        pass

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    save_user(message.from_user)

    state = user_states.get(user_id)

    if state == "WAITING_TICKET_MSG":
        user_states.pop(user_id, None)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tickets (user_id, subject) VALUES (?, ?)", (user_id, message.text))
        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ تم فتح تذكرتك بنجاح برقم **#{ticket_id}**. سيقوم فريق الدعم بالرد عليك قريباً.")
        try:
            bot.send_message(ADMIN_ID, f"🔔 **تذكرة جديدة #{ticket_id}** من `{user_id}` ({message.from_user.first_name}):\\n\\n{message.text}", parse_mode="Markdown")
        except Exception:
            pass
        return

    if state == "WAITING_BROADCAST_MSG" and user_id == ADMIN_ID:
        user_states.pop(user_id, None)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        count = 0
        for u in users:
            try:
                bot.send_message(u[0], message.text)
                count += 1
            except Exception:
                pass
        bot.reply_to(message, f"📢 تم إرسال الإذاعة بنجاح إلى {count} مستخدم.")
        return

    bot.send_chat_action(message.chat.id, "typing")
    ai_reply = ask_groq(message.text)
    bot.reply_to(message, ai_reply)

@app.route("/")
def index():
    return "Nayzak Bot Webhook Active", 200

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        if update:
            bot.process_new_updates([update])
        return "OK", 200
    else:
        return "Forbidden", 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
"""

with open("flask_app.py", "w", encoding="utf-8") as f:
    f.write(code.strip())
print("✅ FILE CREATED SUCCESSFULLY!")
'
