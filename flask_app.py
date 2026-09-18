import io
import base64
import logging
import sqlite3
import threading
import requests
import telebot
from telebot import types
from flask import Flask
from groq import Groq
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

# ==============================================================================
# --- 1. الإعدادات وسيرفر Flask ---
# ==============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "FOREX AMT Bot with Trade Signals & AI Publisher is running!"

# المفاتيح والمعرفات
BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
GROQ_API_KEY = "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"

OFFICIAL_CHANNEL_ID = -1004363402118  # القناة العامة للتوصيات والدروس
SUPPORT_CHAT_ID = -1004488517670      # مجموعة الدعم واستقبال الاستشارات
ADMIN_IDS = [966607076]               # قائمة معرفات الآدمن/المشرفين

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = telebot.TeleBot(BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
user_states = {}

# ==============================================================================
# --- 2. قاعدة البيانات (SQLite) ---
# ==============================================================================

DB_NAME = "forex_amt.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                full_name TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ==============================================================================
# --- 3. توليد الشهادات في الذاكرة (RAM) ---
# ==============================================================================

def generate_pdf_certificate_memory(student_name):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = 792, 612
    
    c.setStrokeColorRGB(0.1, 0.1, 0.3)
    c.setLineWidth(5)
    c.rect(30, 30, width - 60, height - 60)
    
    c.setFont("Helvetica-Bold", 30)
    c.setFillColorRGB(0.1, 0.1, 0.3)
    c.drawCentredString(width / 2, height - 120, "FOREX AMT ACADEMY")
    
    c.setFont("Helvetica", 16)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, height - 160, "Certificate of Completion")
    
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 220, "This is proudly presented to:")
    
    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(0.0, 0.0, 0.0)
    c.drawCentredString(width / 2, height - 270, student_name)
    
    c.setFont("Helvetica", 14)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(width / 2, height - 330, "For successfully mastering Smart Money Concepts (SMC) & Market Structure.")
    
    c.save()
    buffer.seek(0)
    return buffer

# ==============================================================================
# --- 4. الأزرار والقوائم التفاعلية ---
# ==============================================================================

def main_menu_markup(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("📚 الدروس التعليمية"),
        types.KeyboardButton("📊 تحليل شارت (ارسل صورة)"),
        types.KeyboardButton("💬 طلب استشارة / دعم"),
        types.KeyboardButton("📈 القناة الرسمية"),
        types.KeyboardButton("🎓 شهادة الدورة (PDF)"),
        types.KeyboardButton("ℹ️ حول البوت")
    ]
    if user_id in ADMIN_IDS:
        buttons.insert(0, types.KeyboardButton("👑 لوحة تحكم الآدمن"))
        
    markup.add(*buttons)
    return markup

def back_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 العودة للقائمة الرئيسية"))
    return markup

def admin_panel_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_stats = types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")
    btn_trade = types.InlineKeyboardButton("🎯 نشر صفقة جديدة", callback_data="admin_post_trade")
    btn_post = types.InlineKeyboardButton("📢 منشور للقناة", callback_data="admin_post_channel")
    btn_broadcast = types.InlineKeyboardButton("📣 إذاعة للأعضاء", callback_data="admin_broadcast")
    btn_lessons = types.InlineKeyboardButton("📚 إدارة الدروس", callback_data="admin_manage_lessons")
    btn_close = types.InlineKeyboardButton("❌ إغلاق", callback_data="admin_close")
    
    markup.add(btn_trade, btn_lessons)
    markup.add(btn_stats, btn_post)
    markup.add(btn_broadcast, btn_close)
    return markup

# ==============================================================================
# --- 5. معالجة الأوامر الرئيسية والقوائم ---
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_command(message):
    uid = message.from_user.id
    fname = message.from_user.first_name or "المستخدم"
    uname = message.from_user.username or ""
    
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
            (uid, fname, uname)
        )
        conn.commit()
        
    user_states.pop(uid, None)
    welcome_text = (
        f"أهلاً بك يا **{fname}** في بوت **FOREX AMT** الذكي 📈\n\n"
        "يمكنك الآن تصفح الدروس التعليمية، إرسال الشارتات لتحليلها بالذكاء الاصطناعي، أو طلب دعم واستشارة مباشرة."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(uid), parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bot.send_message(
        message.chat.id,
        "👑 **مرحباً بك في لوحة تحكم الآدمن**\nاختر من القائمة أدناه الإجراء المطلوب:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "👑 لوحة تحكم الآدمن")
def admin_button_click(message):
    if message.from_user.id in ADMIN_IDS:
        admin_command(message)

@bot.message_handler(func=lambda msg: msg.text == "🔙 العودة للقائمة الرئيسية")
def back_to_main(message):
    uid = message.from_user.id
    user_states.pop(uid, None)
    bot.send_message(message.chat.id, "تمت العودة للقائمة الرئيسية.", reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda msg: msg.text == "💬 طلب استشارة / دعم")
def request_consultation(message):
    uid = message.from_user.id
    user_states[uid] = "WAITING_CONSULTATION"
    bot.send_message(
        message.chat.id,
        "✏️ **اكتب استشارتك أو سؤالك الآن في رسالة واحدة:**\nوسيقوم فريق الدعم بالرد عليك مباشرة.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 تحليل شارت (ارسل صورة)")
def prompt_chart_upload(message):
    bot.send_message(
        message.chat.id,
        "📸 **يرجى إرسال صورة الشارت الآن** مباشرة ليصلك التحليل الفني ومستويات الـ SMC بواسطة الذكاء الاصطناعي.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📈 القناة الرسمية")
def channel_info(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("الانضمام للقناة 🚀", url="https://t.me/wwwforexmta"))
    bot.send_message(message.chat.id, "تابع قناتنا الرسمية FOREX AMT للتوصيات والتحليلات اليومية:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ حول البوت")
def about_bot(message):
    about_text = (
        "🤖 **بوت FOREX AMT الذكي**\n\n"
        "• يحلل الشارتات الفنية باستخدام الذكاء الاصطناعي البصري (Groq Vision).\n"
        "• يقدم دروساً تفاعلية لمفاهيم SMC و ICT مدمجة بالذكاء الاصطناعي.\n"
        "• يتيح التواصل المباشر مع فريق الدعم والاستشارات."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🎓 شهادة الدورة (PDF)")
def send_certificate(message):
    student_name = message.from_user.first_name or "Student"
    msg = bot.reply_to(message, "⏳ جاري إصدار وتهيئة شهادتك...")
    try:
        pdf_buffer = generate_pdf_certificate_memory(student_name)
        bot.send_document(
            message.chat.id,
            document=("FOREX_AMT_Certificate.pdf", pdf_buffer),
            caption=f"🎓 مبارك يا **{student_name}**! إليك شهادة إتمام الدورة.",
            parse_mode="Markdown"
        )
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        logging.error(f"Certificate generation error: {e}")
        bot.edit_message_text("❌ حدث خطأ أثناء إصدار الشهادة.", message.chat.id, msg.message_id)

# ==============================================================================
# --- 6. قسم الدروس التعليمية للطلاب ---
# ==============================================================================

@bot.message_handler(func=lambda msg: msg.text == "📚 الدروس التعليمية")
def show_lessons_list(message):
    with get_db_connection() as conn:
        lessons = conn.execute("SELECT id, title FROM lessons ORDER BY id ASC").fetchall()
        
    if not lessons:
        bot.send_message(message.chat.id, "📚 لم يتم إضافة أي دروس تعليمية حتى الآن.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for l in lessons:
        markup.add(types.InlineKeyboardButton(f"📖 {l['title']}", callback_data=f"view_lesson_{l['id']}"))
        
    bot.send_message(message.chat.id, "🎓 **قائمة دروس دورة SMC الشاملة:**\nاختر الدرس الذي ترغب بقراءته:", reply_markup=markup, parse_mode="Markdown")

# ==============================================================================
# --- 7. معالجة نقرات أزرار اللوحة (Callback Queries) ---
# ==============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data.startswith("view_lesson_"):
        lesson_id = data.replace("view_lesson_", "")
        with get_db_connection() as conn:
            lesson = conn.execute("SELECT title, content FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
            
        if lesson:
            bot.answer_callback_query(call.id)
            text = f"📘 **{lesson['title']}**\n\n{lesson['content']}"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "الدرس غير موجود!")
        return

    if uid not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ هذا الزر للمشرفين فقط.")
        return

    if data == "admin_stats":
        with get_db_connection() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            consult_count = conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
            lessons_count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            
        stats_msg = (
            f"📊 **إحصائيات البوت الحالية:**\n\n"
            f"👥 عدد المشتركين: `{users_count}`\n"
            f"🎯 الصفقات المنشورة: `{trades_count}`\n"
            f"💬 طلبات الاستشارة: `{consult_count}`\n"
            f"📚 عدد الدروس المضافة: `{lessons_count}`"
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text(stats_msg, call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin_post_trade":
        user_states[uid] = "WAITING_TRADE_DETAILS"
        bot.answer_callback_query(call.id)
        template_text = (
            "🎯 **نشر صفقة / توصية جديدة**\n\n"
            "أرسل تفاصيل الصفقة بالتنسيق المباشر أو انسخ القالب التالي وعدله:\n\n"
            "🎯 **توصية تداول جديدة (SMC Signal)**\n"
            "🔹 **الزوج:** XAU/USD (الذهب)\n"
            "🔹 **النوع:** شراء (BUY LIMIT)\n"
            "📍 **منطقة الدخول:** 2650.00 - 2652.00\n"
            "🎯 **الهدف الأول:** 2662.00\n"
            "🎯 **الهدف الثاني:** 2675.00\n"
            "🛑 **إيقاف الخسارة:** 2642.00\n"
            "💡 **ملاحظة:** بناءً على Order Block فريم 15m + Liquidity Sweep"
        )
        bot.send_message(call.message.chat.id, template_text, reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_post_channel":
        user_states[uid] = "WAITING_ADMIN_CHANNEL_POST"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **أرسل الآن نص المنشور** الذي تريد نشره فوراً في القناة الرسمية:", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_broadcast":
        user_states[uid] = "WAITING_ADMIN_BROADCAST"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📣 **أرسل الآن الرسالة** التي تريد إذاعتها لجميع مستخدمي البوت:", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_manage_lessons":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤖 توليد درس تلقائي ونشره بالقناة", callback_data="admin_ai_gen_lesson"),
            types.InlineKeyboardButton("➕ إضافة درس يدوياً", callback_data="admin_add_lesson"),
            types.InlineKeyboardButton("🗑️ حذف درس", callback_data="admin_delete_lesson_list"),
            types.InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="admin_main")
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📚 **إدارة الدروس التعليمية:**\nاختر كيف تريد إضافة أو إدارة الدروس:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "admin_ai_gen_lesson":
        user_states[uid] = "WAITING_AI_LESSON_TOPIC"
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🤖 **توليد درس ونشره بالقناة وبالبوت**\n\nأرسل اسم الموضوع الذي تريد كتابته (مثال: `Order Block` أو `Liquidity Sweeps`):",
            reply_markup=back_menu_markup(),
            parse_mode="Markdown"
        )

    elif data == "admin_add_lesson":
        user_states[uid] = "WAITING_LESSON_TITLE"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✏️ **أدخل عنوان الدرس الجديد:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_delete_lesson_list":
        with get_db_connection() as conn:
            lessons = conn.execute("SELECT id, title FROM lessons").fetchall()
            
        if not lessons:
            bot.answer_callback_query(call.id, "لا توجد دروس لحذفها.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for l in lessons:
            markup.add(types.InlineKeyboardButton(f"❌ حذف: {l['title']}", callback_data=f"delete_lesson_{l['id']}"))
        markup.add(types.InlineKeyboardButton("🔙 العودة", callback_data="admin_manage_lessons"))
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text("اختر الدرس المراد حذفه نهائياً:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("delete_lesson_"):
        lesson_id = data.replace("delete_lesson_", "")
        with get_db_connection() as conn:
            conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            conn.commit()
        bot.answer_callback_query(call.id, "✅ تم حذف الدرس بنجاح.")
        bot.edit_message_text("✅ تم حذف الدرس بنجاح.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

    elif data == "admin_main":
        bot.answer_callback_query(call.id)
        bot.edit_message_text("👑 **مرحباً بك في لوحة تحكم الآدمن**\nاختر من القائمة أدناه الإجراء المطلوب:", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin_close":
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)

# ==============================================================================
# --- 8. معالجة ردود الآدمن المباشرة من مجموعة الدعم ---
# ==============================================================================

@bot.message_handler(func=lambda msg: msg.chat.id == SUPPORT_CHAT_ID and msg.reply_to_message is not None)
def reply_to_user_consultation(message):
    try:
        original_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if "(" in original_text and ")" in original_text:
            target_uid = int(original_text.split("(`")[1].split("`)")[0])
            bot.send_message(target_uid, f"💬 **رد من فريق الدعم:**\n\n{message.text}", parse_mode="Markdown")
            bot.reply_to(message, "✅ تم إرسال الرد إلى الطالب بنجاح.")
    except Exception as e:
        bot.reply_to(message, f"❌ تعذر إرسال الرد للمستخدم: {e}")

# ==============================================================================
# --- 9. معالجة مدخلات النصوص وتوليد الصفقة/الدرس للنشر ---
# ==============================================================================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    uid = message.from_user.id
    state = user_states.get(uid)

    # 1. معالجة ونشر الصفقة في القناة وحفظها في قاعدة البيانات
    if state == "WAITING_TRADE_DETAILS" and uid in ADMIN_IDS:
        trade_content = message.text
        user_states.pop(uid, None)
        
        with get_db_connection() as conn:
            conn.execute("INSERT INTO trades (details) VALUES (?)", (trade_content,))
            conn.commit()
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("مناقشة التحليل والدعم 💬", url="https://t.me/wwwforexmta"))
        
        published_to_channel = False
        try:
            bot.send_message(OFFICIAL_CHANNEL_ID, trade_content, reply_markup=markup, parse_mode="Markdown")
            published_to_channel = True
        except Exception as e:
            logging.error(f"Failed publishing trade to channel: {e}")

        status = "✅ **تم نشر الصفقة بنجاح في القناة الرسمية وقاعدة البيانات!**" if published_to_channel else "⚠️ **تم حفظ الصفقة لكن تعذر نشرها في القناة (تأكد من صلاحيات البوت كآدمن هناك).**"
        bot.send_message(message.chat.id, status, reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return

    # 2. توليد الدرس بالذكاء الاصطناعي ونشره بالقناة
    elif state == "WAITING_AI_LESSON_TOPIC" and uid in ADMIN_IDS:
        topic = message.text
        user_states.pop(uid, None)
        status_msg = bot.send_message(message.chat.id, f"⚡ **جاري صياغة الدرس حول '{topic}' ونشره تلقائياً...**", parse_mode="Markdown")
        
        try:
            prompt = (
                f"أنت كبير المحاضرين في تداول الأموال الذكية (SMC & ICT).\n"
                f"اكتب درساً تعليمياً احترافياً متكاملاً باللغة العربية حول الموضوع: '{topic}'.\n\n"
                f"شروط الصياغة:\n"
                f"1. ابدأ الشرح بمقدمة مفهومة للمبتدئ.\n"
                f"2. وضح كيفية التعرف عليه في الشارت الفني خطوة بخطوة.\n"
                f"3. اذكر طريقة التداول عليه مع إدارة المخاطر.\n"
                f"4. نسق الدرس بشكل ممتاز باستخدام النقاط والخط العريض Markdown."
            )
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192"
            )
            ai_content = response.choices[0].message.content
            lesson_title = f"درس: {topic}"

            with get_db_connection() as conn:
                conn.execute("INSERT INTO lessons (title, content) VALUES (?, ?)", (lesson_title, ai_content))
                conn.commit()

            channel_published = False
            try:
                channel_msg = f"🎓 **[درس تعليمي جديد]**\n\n📘 **{lesson_title}**\n\n{ai_content}\n\n---\n📲 للمزيد من الدروس والتحليلات، اشترك في البوت الرسمي."
                bot.send_message(OFFICIAL_CHANNEL_ID, channel_msg, parse_mode="Markdown")
                channel_published = True
            except Exception as ch_err:
                logging.error(f"Failed publishing lesson to channel: {ch_err}")

            bot.delete_message(message.chat.id, status_msg.message_id)
            status_text = "✅ **تم حفظ الدرس ونشره في القناة الرسمية بنجاح!** 🚀" if channel_published else "⚠️ **تم حفظ الدرس في البوت ولكن تعذر نشره في القناة.**"
            
            preview_text = f"{status_text}\n\n📖 **العنوان:** {lesson_title}\n\n---\n{ai_content}"
            bot.send_message(message.chat.id, preview_text, reply_markup=main_menu_markup(uid), parse_mode="Markdown")

        except Exception as e:
            logging.error(f"AI Lesson Generation Error: {e}")
            bot.edit_message_text(f"❌ حدث خطأ أثناء توليد الدرس عبر الذكاء الاصطناعي:\n`{e}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        return

    # 3. إدخال عنوان درس جديد يدوياً
    elif state == "WAITING_LESSON_TITLE" and uid in ADMIN_IDS:
        user_states[uid] = {"state": "WAITING_LESSON_CONTENT", "title": message.text}
        bot.send_message(message.chat.id, f"📝 عنوان الدرس: **{message.text}**\n\nأرسل الآن **محتوى الدرس بالتفصيل**:", parse_mode="Markdown")
        return

    # 4. إدخال محتوى الدرس اليدوي وحفظه
    elif isinstance(state, dict) and state.get("state") == "WAITING_LESSON_CONTENT" and uid in ADMIN_IDS:
        title = state["title"]
        content = message.text
        with get_db_connection() as conn:
            conn.execute("INSERT INTO lessons (title, content) VALUES (?, ?)", (title, content))
            conn.commit()
        user_states.pop(uid, None)
        bot.send_message(message.chat.id, f"✅ **تم نشر وإضافة الدرس بنجاح!**\nالعنوان: {title}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return

    # 5. نشر منشور في القناة عبر اللوحة
    elif state == "WAITING_ADMIN_CHANNEL_POST" and uid in ADMIN_IDS:
        user_states.pop(uid, None)
        try:
            bot.send_message(OFFICIAL_CHANNEL_ID, message.text, parse_mode="Markdown")
            bot.send_message(message.chat.id, "✅ **تم نشر منشورك في القناة الرسمية بنجاح!**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ فشل النشر في القناة: {e}", reply_markup=main_menu_markup(uid))
        return

    # 6. إذاعة عامة لكل مستخدمي البوت
    elif state == "WAITING_ADMIN_BROADCAST" and uid in ADMIN_IDS:
        user_states.pop(uid, None)
        bot.send_message(message.chat.id, "⏳ جاري تنفيذ الإذاعة لجميع المشتركين...")
        with get_db_connection() as conn:
            users = conn.execute("SELECT user_id FROM users").fetchall()
        
        success, failed = 0, 0
        for u in users:
            try:
                bot.send_message(u['user_id'], message.text, parse_mode="Markdown")
                success += 1
            except Exception:
                failed += 1
                
        bot.send_message(message.chat.id, f"📊 **اكتملت الإذاعة:**\n\n✅ وصل بنجاح: `{success}`\n❌ فشل: `{failed}`", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return

    # 7. طلب دعم/استشارة من طالب
    elif state == "WAITING_CONSULTATION":
        user_states.pop(uid, None)
        consult_text = message.text
        name = message.from_user.first_name or "المستخدم"
        username = f"@{message.from_user.username}" if message.from_user.username else "بدون معرف"
        
        with get_db_connection() as conn:
            conn.execute("INSERT INTO consultations (user_id, full_name, message) VALUES (?, ?, ?)", (uid, name, consult_text))
            conn.commit()
            
        bot.reply_to(message, "✅ تم إرسال رسالتك إلى فريق الدعم بنجاح!", reply_markup=main_menu_markup(uid))
        
        support_msg = (
            f"📥 **رسالة استشارة / دعم جديدة**\n\n"
            f"👤 **الاسم:** {name}\n"
            f"🆔 **المعرف:** {username} (`{uid}`)\n\n"
            f"💬 **الرسالة:**\n{consult_text}"
        )
        try:
            bot.send_message(SUPPORT_CHAT_ID, support_msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed sending to support chat: {e}")
        return

    # 8. رد AI عادي عبر Groq
    if groq_client:
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            system_prompt = (
                "أنت المساعد الذكي الخبير لأكاديمية FOREX AMT المتخصص في مفاهيم الأموال الذكية (SMC / ICT).\n"
                "أجب على أسئلة المستخدم بدقة وبأسلوب تعليمي مبسط، وركز على مفاهيم Structure, Order Blocks, FVG, Liquidity."
            )
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message.text}
                ],
                model="llama3-70b-8192"
            )
            bot.reply_to(message, response.choices[0].message.content, reply_markup=main_menu_markup(uid))
            return
        except Exception as e:
            logging.error(f"Groq API Error: {e}")

    bot.send_message(message.chat.id, "الرجاء اختيار أحد الخيارات من القائمة أدناه:", reply_markup=main_menu_markup(uid))

# ==============================================================================
# --- 10. تحليل الصور (Groq Vision) ---
# ==============================================================================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')
    status_msg = bot.reply_to(message, "⏳ **جاري تحليل الشارت وقراءة مستويات الـ SMC بالذكاء الاصطناعي...**", parse_mode="Markdown")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        prompt_instruction = (
            "أنت خبير محترف في التداول بمفاهيم الأموال الذكية (SMC Senior Analyst).\n"
            "قم بتحليل صورة الشارت المرفقة بدقة واذكر:\n"
            "1. الاتجاه العام وبنية السوق (BOS / CHoCH).\n"
            "2. مناطق FVG والـ Order Blocks الرئيسية.\n"
            "3. مناطق السيولة المستهدفة (BSL / SSL).\n"
            "4. نصيحة تعليمية موجزة."
        )

        vision_models = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]
        analysis_result = None
        last_error = ""

        for model_name in vision_models:
            try:
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_instruction},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=800
                )
                analysis_result = response.choices[0].message.content
                break
            except Exception as err:
                last_error = str(err)
                continue

        if analysis_result:
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.reply_to(message, f"🎯 **[نتيجة تحليل الشارت الذكي]**\n\n{analysis_result}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        else:
            bot.edit_message_text(f"❌ تعذر التحليل عبر Groq:\n`{last_error}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Vision Processing Error: {e}")
        bot.edit_message_text(f"❌ حدث خطأ أثناء المعالجة:\n`{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

    try:
        caption = f"📸 **شارت جديد للتحليل** من: {message.from_user.first_name} (`{uid}`)"
        bot.send_photo(SUPPORT_CHAT_ID, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed forwarding chart to support: {e}")

# ==============================================================================
# --- 11. تشغيل البوت في الخلفية لسيرفر Web ---
# ==============================================================================

def run_bot():
    logging.info("Starting Telegram Bot Polling thread...")
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run()
