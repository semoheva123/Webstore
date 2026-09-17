import os
import sqlite3
from flask import Flask, request
import telebot
from telebot import types
from groq import Groq

# ----------------------------------------------------
# Configuration & Setup
# ----------------------------------------------------
BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
ADMIN_ID = 966607076
GROQ_API_KEY = "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"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

DB_NAME = "/home/Acab7/academy_system.db" if os.path.exists("/home/Acab7") else "academy_system.db"

# Initialize Groq Client safely
try:
    groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except Exception:
    groq_client = None

def init_db():
    try:
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
                status TEXT DEFAULT 'open', 
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")

init_db()
user_states = {}

def save_user(user):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                       (user.id, user.username or "", user.first_name or ""))
        conn.commit()
        conn.close()
    except Exception:
        pass

def ask_groq(prompt):
    if not groq_client:
        return "⚡ عذراً، مفتاح الذكاء الاصطناعي غير متصل حالياً."
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "أنت المساعد الذكي والمحترف الرسمي لأكاديمية النيزك (Nayzak Academy). قدم إجابات دقيقة، منظمة، واحترافية باللغة العربية."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="openai/gpt-oss-120b",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"عذراً، حدث خطأ تقني أثناء المعالجة: {str(e)}"

# ----------------------------------------------------
# Keyboards Builder
# ----------------------------------------------------
def main_menu_markup(is_admin=False):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 اسأل الذكاء الاصطناعي", callback_data="mode_ai"),
        types.InlineKeyboardButton("🎫 فتح تذكرة دعم", callback_data="open_ticket"),
        types.InlineKeyboardButton("📚 دورات الأكاديمية", callback_data="courses_info"),
        types.InlineKeyboardButton("🛠 خدماتنا التقنية", callback_data="services_info"),
        types.InlineKeyboardButton("📞 التواصل المباشر", callback_data="contact_human")
    )
    if is_admin:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة تحكم الإدارة", callback_data="admin_panel"))
    return markup

def back_menu_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu"))
    return markup

# ----------------------------------------------------
# Telegram Handlers
# ----------------------------------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_user(message.from_user)
    is_admin = (message.from_user.id == ADMIN_ID)
    
    welcome_text = (
        f"أهلاً بك يا أستاذ/ـه **{message.from_user.first_name}** في بوابة **أكاديمية النيزك (Nayzak Academy)** 🚀\n\n"
        "نحن بوابتك الاحترافية نحو إتقان البرمجة، والتقنية، وتحليل الأسواق المالية.\n"
        "اختر أحد الخيارات أدناه للبدء:"
    )
    bot.reply_to(message, welcome_text, reply_markup=main_menu_markup(is_admin), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    uid = call.from_user.id
    is_admin = (uid == ADMIN_ID)
    
    try:
        if call.data == "main_menu":
            user_states.pop(uid, None)
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "القائمة الرئيسية لأكاديمية النيزك 🚀:\nاختر ما يناسب احتياجك:", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=main_menu_markup(is_admin)
            )

        elif call.data == "mode_ai":
            user_states[uid] = "AI_CHAT"
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "🤖 **وضع المحادثة الذكية مفعل**\n\n"
                "يمكنك الآن إرسال أي سؤال وسيقوم المساعد الذكي بالإجابة عليك فوراً بذكاء واحترافية.",
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=back_menu_markup(), 
                parse_mode="Markdown"
            )

        elif call.data == "courses_info":
            courses_text = (
                "📚 **دورات أكاديمية النيزك المعتمدة:**\n\n"
                "1️⃣ **تطوير وتصميم الويب والتطبيقات:** (JavaScript, Node.js, React, Python, Flutter)\n"
                "2️⃣ **تحليل الأسواق المالية والذهب (XAU/USD):** (Smart Money Concepts, Price Action)\n"
                "3️⃣ **إدارة السيرفرات والشبكات المتقدمة:** (Ubiquiti, Linux, Cloud Deployments)\n\n"
                "💡 للتسجيل في أي دورة، يرجى فتح تذكرة دعم."
            )
            bot.answer_callback_query(call.id)
            bot.edit_message_text(courses_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=back_menu_markup(), parse_mode="Markdown")

        elif call.data == "services_info":
            services_text = (
                "🛠 **خدمات أكاديمية النيزك التقنية:**\n\n"
                "• برمجة وتطوير المتاجر الإلكترونية ومنصات الويب.\n"
                "• بناء بوتات تيليجرام احترافية متكاملة.\n"
                "• هندسة الشبكات اللاسلكية وبرمجة أنظمة ربط الإشارات.\n"
            )
            bot.answer_callback_query(call.id)
            bot.edit_message_text(services_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=back_menu_markup(), parse_mode="Markdown")

        elif call.data == "open_ticket":
            user_states[uid] = "WAITING_TICKET"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="main_menu"))
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "🎫 **فتح تذكرة دعم جديدة**\n\n"
                "اكتب تفاصيل استفسارك أو مشكلتك في رسالة واحدة وسيقوم فريق الإدارة بمتابعتها:",
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=markup, 
                parse_mode="Markdown"
            )

        elif call.data == "contact_human":
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "📞 يمكنك التواصل المباشر عبر فتح تذكرة دعم وسيتواصل معك مشرف الأكاديمية قريباً.",
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id, 
                reply_markup=back_menu_markup(), 
                parse_mode="Markdown"
            )

        elif call.data == "admin_panel" and is_admin:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            users_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
            open_tickets = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM tickets WHERE status='closed'")
            closed_tickets = c.fetchone()[0]
            conn.close()

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("📢 إرسال إشعار عام (Broadcast)", callback_data="admin_broadcast"),
                types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
            )
            
            admin_text = (
                f"⚙️ **لوحة تحكم الإدارة المتقدمة:**\n\n"
                f"👥 إجمالي المشتركين: `{users_count}`\n"
                f"🎫 التذاكر المفتوحة: `{open_tickets}`\n"
                f"🔒 التذاكر المغلقة: `{closed_tickets}`\n"
            )
            bot.answer_callback_query(call.id)
            bot.edit_message_text(admin_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

        elif call.data == "admin_broadcast" and is_admin:
            user_states[uid] = "WAITING_BROADCAST"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel"))
            bot.answer_callback_query(call.id)
            bot.edit_message_text("📢 أرسل نص الرسالة التي تريد إذاعتها لكل المشتركين الآن:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)

        elif call.data.startswith("close_ticket_") and is_admin:
            tid = call.data.split("_")[2]
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
            conn.commit()
            conn.close()
            bot.answer_callback_query(call.id, f"تم إغلاق التذكرة #{tid}")
            bot.edit_message_text(call.message.text + f"\n\n🔒 **[تم إغلاق هذه التذكرة بواسطة الإدارة]**", chat_id=call.message.chat.id, message_id=call.message.message_id)

    except Exception:
        pass

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    uid = message.from_user.id
    is_admin = (uid == ADMIN_ID)
    save_user(message.from_user)

    state = user_states.get(uid)

    # 1. معالجة الإذاعة العامة للأدمن
    if is_admin and state == "WAITING_BROADCAST":
        user_states.pop(uid, None)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        all_users = c.fetchall()
        conn.close()

        success = 0
        failed = 0
        for u in all_users:
            try:
                bot.send_message(u[0], f"📢 **إشعار هام من إدارة الأكاديمية:**\n\n{message.text}", parse_mode="Markdown")
                success += 1
            except Exception:
                failed += 1
        
        bot.reply_to(message, f"✅ تمت الإذاعة بنجاح:\n- وصل إلى: `{success}` مشترك\n- فشل لدى: `{failed}` مشترك", parse_mode="Markdown")
        return

    # 2. معالجة فتح تذكرة دعم جديدة
    if state == "WAITING_TICKET":
        user_states.pop(uid, None)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO tickets (user_id, subject) VALUES (?, ?)", (uid, message.text))
        tid = c.lastrowid
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ تم فتح تذكرتك برقم **#{tid}** بنجاح.\nسيتواصل معك فريق الدعم قريباً.", parse_mode="Markdown")
        
        try:
            admin_markup = types.InlineKeyboardMarkup()
            admin_markup.add(types.InlineKeyboardButton(f"🔒 إغلاق التذكرة #{tid}", callback_data=f"close_ticket_{tid}"))
            bot.send_message(
                ADMIN_ID, 
                f"🔔 **تذكرة دعم جديدة [#{tid}]**\n👤 من: `{message.from_user.first_name}` (ID: `{uid}`)\n\n💬 النص:\n{message.text}", 
                reply_markup=admin_markup, 
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # 3. الرد الآلي عبر الذكاء الاصطناعي (مفعل افتراضياً لأي رسالة مرسلة)
    bot.send_chat_action(message.chat.id, 'typing')
    ai_response = ask_groq(message.text)
    
    bot.reply_to(message, ai_response, reply_markup=back_menu_markup(), parse_mode="Markdown")

# ----------------------------------------------------
# Flask Webhook Routes
# ----------------------------------------------------
@app.route('/')
def index():
    return "Nayzak Academy Super Bot is Active & Running", 200

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
