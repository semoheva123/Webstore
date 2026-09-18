import io
import base64
import logging
import sqlite3
import threading
import telebot
from telebot import types
from flask import Flask
from groq import Groq
from openai import OpenAI
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

# ==============================================================================
# --- 1. الإعدادات والربط مع المفاتيح ---
# ==============================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "FOREX AMT System Status: Operational 🚀"

BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
GROQ_API_KEY = "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"
OPENROUTER_API_KEY = "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"

OFFICIAL_CHANNEL_ID = -1004363402118
SUPPORT_CHAT_ID = -1004488517670
ADMIN_IDS = [966607076]  # معرف الآدمن المصرح له فقط

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = telebot.TeleBot(BOT_TOKEN)

# Groq للنصوص
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# OpenRouter للرؤية البصرية وتحليل الصور (مجاني)
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

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
# --- 3. تصميم القوائم الواجهة الاحترافية (UI Keyboards) ---
# ==============================================================================

def main_menu_markup(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # حظر ظهور زر اللوحة نهائياً لغير الآدمن
    if user_id in ADMIN_IDS:
        markup.row(types.KeyboardButton("👑 لوحة تحكم الإدارة"))

    btn_chart = types.KeyboardButton("📊 تحليل شارت تلقائي")
    btn_lessons = types.KeyboardButton("📚 مكتبة الدروس")
    btn_cert = types.KeyboardButton("🎓 استخراج الشهادة")
    btn_support = types.KeyboardButton("💬 الدعم والاستشارات")
    btn_channel = types.KeyboardButton("📈 القناة الرسمية")
    btn_about = types.KeyboardButton("ℹ️ دليل البوت")

    markup.add(btn_chart, btn_lessons)
    markup.add(btn_support, btn_cert)
    markup.add(btn_channel, btn_about)
    return markup

def back_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 القائمة الرئيسية"))
    return markup

def admin_panel_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_stats = types.InlineKeyboardButton("📊 إحصائيات النظام", callback_data="admin_stats")
    btn_trade = types.InlineKeyboardButton("🎯 نشر توصية", callback_data="admin_post_trade")
    btn_post = types.InlineKeyboardButton("📢 منشور القناة", callback_data="admin_post_channel")
    btn_broadcast = types.InlineKeyboardButton("📣 إذاعة للأعضاء", callback_data="admin_broadcast")
    btn_lessons = types.InlineKeyboardButton("📚 إدارة الدروس", callback_data="admin_manage_lessons")
    btn_close = types.InlineKeyboardButton("❌ إغلاق اللوحة", callback_data="admin_close")
    
    markup.add(btn_trade, btn_lessons)
    markup.add(btn_stats, btn_post)
    markup.add(btn_broadcast, btn_close)
    return markup

# ==============================================================================
# --- 4. أوامر البوت المحدثة مع شرط الحماية للآدمن ---
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_command(message):
    uid = message.from_user.id
    fname = message.from_user.first_name or "المتداول"
    uname = message.from_user.username or ""
    
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)",
            (uid, fname, uname)
        )
        conn.commit()
        
    user_states.pop(uid, None)
    
    welcome_text = (
        f"🏆 **أهلاً بك في أكاديمية FOREX AMT**\n"
        f"─────────────────────────\n"
        f"مرحباً بك يا **{fname}** 👋\n\n"
        f"منصتك الذكية للتحليل المالي وفق مفاهيم **الأموال الذكية (SMC & ICT)**.\n\n"
        f"🔹 **خدمات البوت المتاحة:**\n"
        f"• 📊 **تحليل الشارتات:** أرسل صورة الشارت للحصول على قراءة الذكاء الاصطناعي.\n"
        f"• 📚 **الدروس التعليمية:** مكتبة شاملة لمفاهيم التداول.\n"
        f"• 🎓 **الشهادات:** إصدار شهادة إتمام الدورة فوراً.\n"
        f"• 💬 **الدعم الفني:** استشارات مباشرة مع فريق التحليل.\n\n"
        f"👇 **اختر الخيار المطلوب من القائمة أدناه:**"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(uid), parse_mode="Markdown")

# التحقق الصارم من معرّف الآدمن
@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "👑 لوحة تحكم الإدارة")
def admin_command(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🛑 **عذراً، هذه اللوحة مخصصة لإدارة الأكاديمية فقط.**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return
        
    bot.send_message(
        message.chat.id,
        "⚙️ **لوحة التحكم والتطوير - FOREX AMT**\n─────────────────────────\nإدارة العمليات والتفاعلات:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🔙 القائمة الرئيسية")
def back_to_main(message):
    uid = message.from_user.id
    user_states.pop(uid, None)
    bot.send_message(message.chat.id, "🔄 تم الانتقال إلى القائمة الرئيسية.", reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda msg: msg.text == "💬 الدعم والاستشارات")
def request_consultation(message):
    uid = message.from_user.id
    user_states[uid] = "WAITING_CONSULTATION"
    bot.send_message(
        message.chat.id,
        "💬 **قسم الدعم والاستشارات الفنية**\n─────────────────────────\n"
        "اكتب استفسارك أو تحليل للزوج الذي تريده في رسالة واحدة، وسيقوم فريق الدعم بالرد عليك فوراً.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 تحليل شارت تلقائي")
def prompt_chart_upload(message):
    bot.send_message(
        message.chat.id,
        "📸 **محلل الشارتات الذكي (SMC Vision)**\n─────────────────────────\n"
        "يرجى إرسال صورة الشارت الآن بدقة واضحة لتحديد الهيكلية والمناطق الاستثمارية.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📈 القناة الرسمية")
def channel_info(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("الانضمام للقناة الرسمية 🚀", url="https://t.me/wwwforexmta"))
    bot.send_message(
        message.chat.id,
        "📢 **القناة الرسمية للأكاديمية**\n─────────────────────────\nتابع التوصيات والتحليلات اليومية الحصرية:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ دليل البوت")
def about_bot(message):
    about_text = (
        "ℹ️ **دليل المنظومة - FOREX AMT**\n"
        "─────────────────────────\n"
        "• **الذكاء البصري:** يحلل مستويات الـ Order Blocks والـ FVG والسيولة تلقائياً.\n"
        "• **محرك النصوص:** مدعوم بواسطة نماذج الجيل الحديث لتوليد الإجابات المباشرة.\n"
        "• **نظام الشهادات:** يولد شهادات توثيق PDF آلية في الذاكرة."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

# ==============================================================================
# --- 5. إصدار الشهادات (PDF) ---
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

@bot.message_handler(func=lambda msg: msg.text == "🎓 استخراج الشهادة")
def send_certificate(message):
    student_name = message.from_user.first_name or "Student"
    msg = bot.reply_to(message, "⏳ **جاري إصدار الشهادة واعتمادها...**", parse_mode="Markdown")
    try:
        pdf_buffer = generate_pdf_certificate_memory(student_name)
        bot.send_document(
            message.chat.id,
            document=("FOREX_AMT_Certificate.pdf", pdf_buffer),
            caption=f"🎓 تهانينا يا **{student_name}**! تم إصدار شهادة التخرج بنجاح.",
            parse_mode="Markdown"
        )
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        logging.error(f"Certificate generation error: {e}")
        bot.edit_message_text("❌ حدث خطأ أثناء إنشاء الشهادة.", message.chat.id, msg.message_id)

# ==============================================================================
# --- 6. عرض إدارة الدروس ---
# ==============================================================================

@bot.message_handler(func=lambda msg: msg.text == "📚 مكتبة الدروس")
def show_lessons_list(message):
    with get_db_connection() as conn:
        lessons = conn.execute("SELECT id, title FROM lessons ORDER BY id ASC").fetchall()
        
    if not lessons:
        bot.send_message(message.chat.id, "📚 **مكتبة الدروس فارغة حالياً.**", parse_mode="Markdown")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for l in lessons:
        markup.add(types.InlineKeyboardButton(f"📖 {l['title']}", callback_data=f"view_lesson_{l['id']}"))
        
    bot.send_message(
        message.chat.id,
        "📚 **فهرس الدروس الشاملة (SMC/ICT)**\n─────────────────────────\nاختر الدرس الذي ترغب بقراءته:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==============================================================================
# --- 7. التفاعل مع الأزرار والمشرفين (Callback Queries) ---
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
            text = f"📘 **{lesson['title']}**\n─────────────────────────\n\n{lesson['content']}"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "الدرس غير موجود!")
        return

    # شرط حظر استجابة الأزرار لغير الآدمن
    if uid not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "🛑 إجراء محظور: للمشرفين فقط.", show_alert=True)
        return

    if data == "admin_stats":
        with get_db_connection() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            consult_count = conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
            lessons_count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            trades_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            
        stats_msg = (
            f"📊 **تقارير النظام والإحصائيات**\n─────────────────────────\n"
            f"👥 **المشتركين:** `{users_count}`\n"
            f"🎯 **التوصيات المنشورة:** `{trades_count}`\n"
            f"💬 **الاستشارات:** `{consult_count}`\n"
            f"📚 **الدروس المضافة:** `{lessons_count}`"
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text(stats_msg, call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin_post_trade":
        user_states[uid] = "WAITING_TRADE_DETAILS"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🎯 **أرسل تفاصيل التوصية للنشر الفوري:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_post_channel":
        user_states[uid] = "WAITING_ADMIN_CHANNEL_POST"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📢 **أرسل المنشور المراد إرساله للقناة الرسمية:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_broadcast":
        user_states[uid] = "WAITING_ADMIN_BROADCAST"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📣 **أرسل نص الإذاعة العامة:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_manage_lessons":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤖 توليد درس تلقائي بالذكاء", callback_data="admin_ai_gen_lesson"),
            types.InlineKeyboardButton("➕ إضافة درس يدوياً", callback_data="admin_add_lesson"),
            types.InlineKeyboardButton("🗑️ حذف درس", callback_data="admin_delete_lesson_list"),
            types.InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_main")
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📚 **قسم إدارة الدروس**\nاختر الإجراء المطلوب:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "admin_ai_gen_lesson":
        user_states[uid] = "WAITING_AI_LESSON_TOPIC"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🤖 **أدخل اسم عنوان الدرس المطلوب توليده ونشره:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

    elif data == "admin_add_lesson":
        user_states[uid] = "WAITING_LESSON_TITLE"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✏️ **أدخل عنوان الدرس:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

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
        bot.edit_message_text("اختر الدرس المراد حذفه:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif data.startswith("delete_lesson_"):
        lesson_id = data.replace("delete_lesson_", "")
        with get_db_connection() as conn:
            conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            conn.commit()
        bot.answer_callback_query(call.id, "✅ تم الحذف.")
        bot.edit_message_text("✅ تم حذف الدرس بنجاح.", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())

    elif data == "admin_main":
        bot.answer_callback_query(call.id)
        bot.edit_message_text("⚙️ **لوحة التحكم والتطوير - FOREX AMT**", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin_close":
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)

# ==============================================================================
# --- 8. معالجة الردود النصية وتوليد الدروس عبر Groq ---
# ==============================================================================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    uid = message.from_user.id
    state = user_states.get(uid)

    if state == "WAITING_AI_LESSON_TOPIC" and uid in ADMIN_IDS:
        topic = message.text
        user_states.pop(uid, None)
        status_msg = bot.send_message(message.chat.id, f"⚡ **جاري صياغة درس ' {topic} ' بواسطة الذكاء الاصطناعي...**", parse_mode="Markdown")
        
        try:
            prompt = (
                f"أنت خبير ومدرس تداول الأموال الذكية (SMC & ICT).\n"
                f"اكتب درساً تعليمياً مختصراً جداً ومباشراً باللغة العربية حول: '{topic}'.\n\n"
                f"الشروط:\n"
                f"1. دخول مباشر في المفاهيم بدون مقدمات طويلة.\n"
                f"2. الطول مناسب للقراءة على الموبايل (150-200 كلمة).\n"
                f"3. التنسيق في نقاط محددة واستخدام Markdown."
            )
            # معالجة النصوص عبر Groq
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-120b"
            )
            ai_content = response.choices[0].message.content
            lesson_title = f"درس: {topic}"

            with get_db_connection() as conn:
                conn.execute("INSERT INTO lessons (title, content) VALUES (?, ?)", (lesson_title, ai_content))
                conn.commit()

            try:
                channel_msg = f"🎓 **[درس تعليمي سريع]**\n\n📘 **{lesson_title}**\n\n{ai_content}\n\n---\n📲 اشترك للبقية عبر البوت الرسمي."
                bot.send_message(OFFICIAL_CHANNEL_ID, channel_msg, parse_mode="Markdown")
            except Exception as ch_err:
                logging.error(f"Failed publishing lesson: {ch_err}")

            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.send_message(message.chat.id, f"✅ **تم نشر الدرس بنجاح!**\n\n📖 **{lesson_title}**\n\n{ai_content}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")

        except Exception as e:
            logging.error(f"AI Lesson Generation Error: {e}")
            bot.edit_message_text(f"❌ حدث خطأ:\n`{e}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")
        return

    elif state == "WAITING_CONSULTATION":
        user_states.pop(uid, None)
        consult_text = message.text
        name = message.from_user.first_name or "المستخدم"
        username = f"@{message.from_user.username}" if message.from_user.username else "بدون معرف"
        
        with get_db_connection() as conn:
            conn.execute("INSERT INTO consultations (user_id, full_name, message) VALUES (?, ?, ?)", (uid, name, consult_text))
            conn.commit()
            
        bot.reply_to(message, "✅ **تم إرسال استفسارك إلى فريق الدعم بنجاح.**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        
        support_msg = f"📥 **استشارة جديدة**\n👤 {name} (`{uid}`)\n🔗 {username}\n\n💬 {consult_text}"
        try:
            bot.send_message(SUPPORT_CHAT_ID, support_msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send support chat: {e}")
        return

    # الرد الآلي على الأسئلة النصية عبر Groq
    if groq_client:
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "أنت مساعد خبير لأكاديمية FOREX AMT المتخصص في SMC/ICT. أجب بإيجاز ودقة باللغة العربية."},
                    {"role": "user", "content": message.text}
                ],
                model="openai/gpt-oss-120b"
            )
            bot.reply_to(message, response.choices[0].message.content, reply_markup=main_menu_markup(uid), parse_mode="Markdown")
            return
        except Exception as e:
            logging.error(f"Groq API Error: {e}")

    bot.send_message(message.chat.id, "الرجاء اختيار خيار من القائمة أدناه:", reply_markup=main_menu_markup(uid))

# ==============================================================================
# --- 9. تحليل الصور عبر OpenRouter Vision (مجاني) ---
# ==============================================================================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')
    status_msg = bot.reply_to(message, "⏳ **جاري تحليل الشارت وقراءة مستويات الـ SMC...**", parse_mode="Markdown")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        base64_image = base64.b64encode(downloaded_file).decode('utf-8')

        prompt_instruction = (
            "أنت خبير محترف في التداول بمفاهيم الأموال الذكية (SMC Senior Analyst).\n"
            "قم بتحليل صورة الشارت المرفقة بشكل مختصر ومباشر واذكر:\n"
            "1. الاتجاه العام وبنية السوق (BOS / CHoCH).\n"
            "2. مناطق FVG والـ Order Blocks الرئيسية.\n"
            "3. مناطق السيولة المستهدفة (BSL / SSL).\n"
            "4. نصيحة سريعة."
        )

        # استدعاء OpenRouter للصور (مع النموذج المجاني)
        response = openrouter_client.chat.completions.create(
            model="google/gemini-2.0-flash-exp:free",
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

        if analysis_result:
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.reply_to(message, f"📊 **[نتيجة تحليل الشارت الذكي]**\n─────────────────────────\n\n{analysis_result}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ تعذر تحليل الصورة، حاول مجدداً.", message.chat.id, status_msg.message_id)

    except Exception as e:
        logging.error(f"Vision Processing Error: {e}")
        bot.edit_message_text(f"❌ حدث خطأ أثناء معالجة الصورة:\n`{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

# ==============================================================================
# --- 10. تشغيل البوت والسيرفر ---
# ==============================================================================

def run_bot():
    logging.info("Starting Telegram Bot Polling thread...")
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run()
