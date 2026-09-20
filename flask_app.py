import io
import os
import re
import logging
import sqlite3
import base64
import urllib.parse
import requests
import telebot
from telebot import types
from flask import Flask, request
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

# ==============================================================================
# --- 1. إعداد تطبيق Flask والـ Bot ---
# ==============================================================================

app = Flask(__name__)

# قراءة التوكن بأمان من متغيرات البيئة الخاصة بالسيرفر
BOT_TOKEN = os.getenv("BOT_TOKEN")
OFFICIAL_CHANNEL_ID = int(os.getenv("OFFICIAL_CHANNEL_ID", "-1004363402118"))
ADMIN_IDS = [966607076, 688331791]  # معرفات المشرفين المعتمدين

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# تهيئة البوت بوضع غير متزامن متوافق مع Webhook
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ضبط قائمة أوامر البوت تلقائياً في التليجرام
try:
    bot.set_my_commands([
        telebot.types.BotCommand("start", "🏠 القائمة الرئيسية والبدء"),
        telebot.types.BotCommand("admin", "👑 لوحة التحكم (للمشرفين فقط)")
    ])
except Exception as cmd_err:
    logging.warning(f"Failed to set bot commands: {cmd_err}")

user_states = {}

# ==============================================================================
# --- 2. دمج خدمات Pollinations AI (نصوص + صور + رؤية Base64) ---
# ==============================================================================

def poll_generate_text(prompt, system_prompt="أنت خبير تداول ومدرس SMC/ICT في أكاديمية FOREX AMT."):
    """توليد الردود والنصوص المجانية عبر Pollinations AI"""
    url = "https://text.pollinations.ai/"
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "model": "openai"
    }
    headers = {"Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200 and res.text.strip():
            return res.text
    except Exception as e:
        logging.error(f"Pollinations Text Error: {e}")
    return "عذراً، خادم الذكاء الاصطناعي مشغول حالياً. يرجى إعادة إرسال سؤالك."

def poll_generate_chart_image_url(topic):
    """توليد رابط صورة/شارت توضيحي تعليمي"""
    clean_topic = urllib.parse.quote(f"Educational forex trading chart diagram illustrating {topic}, Smart Money Concepts, SMC, ICT order block liquidity, clean financial graphic, high resolution")
    return f"https://image.pollinations.ai/prompt/{clean_topic}?width=1024&height=768&nologo=true&seed=42"

def poll_analyze_chart_vision(image_base64):
    """تحليل صورة الشارت باستخدام Base64 لضمان قراءة الصورة بالذكاء الاصطناعي"""
    url = "https://text.pollinations.ai/"
    prompt_instruction = (
        "أنت خبير محترف في التداول بمفاهيم الأموال الذكية (SMC Senior Analyst).\n"
        "قم بتحليل صورة الشارت المرفقة بشكل مختصر ومباشر واذكر:\n"
        "1. الاتجاه العام وبنية السوق (BOS / CHoCH).\n"
        "2. مناطق FVG والـ Order Blocks الرئيسية.\n"
        "3. مناطق السيولة المستهدفة (BSL / SSL).\n"
        "4. نصيحة سريعة للتداول."
    )
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_instruction},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "model": "openai"
    }
    headers = {"Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=35)
        if res.status_code == 200 and res.text.strip():
            return res.text
    except Exception as e:
        logging.error(f"Pollinations Vision Error: {e}")
    return None

# ==============================================================================
# --- 3. إدارة قاعدة البيانات (SQLite) ---
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
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ==============================================================================
# --- 4. تصميم واجهات القوائم والأزرار ---
# ==============================================================================

def main_menu_markup(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
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
    btn_lessons = types.InlineKeyboardButton("📚 إدارة وتوليد الدروس", callback_data="admin_manage_lessons")
    btn_close = types.InlineKeyboardButton("❌ إغلاق اللوحة", callback_data="admin_close")
    
    markup.add(btn_lessons, btn_stats)
    markup.add(btn_close)
    return markup

# ==============================================================================
# --- 5. أوامر البوت والتفاعل المباشر ---
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
        f"منصتك الذكية للتحليل المالي والتعلم وفق مفاهيم **الأموال الذكية (SMC & ICT)**.\n\n"
        f"🔹 **خدمات البوت المتاحة:**\n"
        f"• 📊 **تحليل الشارتات:** أرسل صورة الشارت لقراءتها فوراً بالذكاء الاصطناعي.\n"
        f"• 📚 **الدروس المبتكرة:** دروس مدعومة بمخططات وشارتات توضيحية.\n"
        f"• 🎓 **الشهادات:** إصدار شهادة تخرج رسمية فوراً.\n"
        f"• 💬 **الدعم الفني:** التواصل المباشر مع المحللين.\n\n"
        f"👇 **اختر الخيار المطلوب من القائمة أدناه:**"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(uid), parse_mode="Markdown")

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda msg: msg.text == "👑 لوحة تحكم الإدارة")
def admin_command(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.send_message(message.chat.id, "🛑 **عذراً، هذه اللوحة مخصصة لإدارة الأكاديمية فقط.**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return
        
    bot.send_message(
        message.chat.id,
        "⚙️ **لوحة التحكم والتطوير - FOREX AMT**\n─────────────────────────\nاختر من الخيارات التالية:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🔙 القائمة الرئيسية")
def back_to_main(message):
    uid = message.from_user.id
    user_states.pop(uid, None)
    bot.send_message(message.chat.id, "🔄 تم الانتقال إلى القائمة الرئيسية.", reply_markup=main_menu_markup(uid))

@bot.message_handler(func=lambda msg: msg.text == "📊 تحليل شارت تلقائي")
def prompt_chart_upload(message):
    bot.send_message(
        message.chat.id,
        "📸 **محلل الشارتات الذكي (SMC Vision)**\n─────────────────────────\n"
        "يرجى إرسال صورة الشارت الآن بدقة واضحة لتحديد الهيكلية والمناطق الاستثمارية.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "💬 الدعم والاستشارات")
def request_consultation(message):
    uid = message.from_user.id
    user_states[uid] = "WAITING_CONSULTATION"
    bot.send_message(
        message.chat.id,
        "💬 **قسم الدعم والاستشارات الفنية**\n─────────────────────────\n"
        "اكتب استفسارك أو تحليل الزوج المطلوب في رسالة واحدة وسيقوم المشرفون بالرد عليك.",
        reply_markup=back_menu_markup(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "📈 القناة الرسمية")
def channel_info(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("الانضمام للقناة الرسمية 🚀", url="https://t.me/wwwforexmta"))
    bot.send_message(
        message.chat.id,
        "📢 **القناة الرسمية للأكاديمية**\n─────────────────────────\nتابع التوصيات والدروس الشاملة يومياً:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ دليل البوت")
def about_bot(message):
    about_text = (
        "ℹ️ **دليل المنظومة - FOREX AMT**\n"
        "─────────────────────────\n"
        "• **الذكاء الاصطناعي:** توليد شارتات توضيحية وتحليل الصور تلقائياً.\n"
        "• **الدروس الآلية:** إنشاء دروس مكثفة مدعمة بأمثلة صور مصممة فورياً.\n"
        "• **نظام الشهادات:** إصدار شهادة إتمام الدورة تلقائياً."
    )
    bot.send_message(message.chat.id, about_text, parse_mode="Markdown")

# ==============================================================================
# --- 6. توليد الشهادات (PDF) ---
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
    c.drawCentredString(width / 2, height - 330, "For mastering Smart Money Concepts (SMC) & Market Structure.")
    
    c.save()
    buffer.seek(0)
    return buffer

@bot.message_handler(func=lambda msg: msg.text == "🎓 استخراج الشهادة")
def send_certificate(message):
    student_name = message.from_user.first_name or "Student"
    msg = bot.reply_to(message, "⏳ **جاري إصدار واعتماد الشهادة...**", parse_mode="Markdown")
    try:
        pdf_buffer = generate_pdf_certificate_memory(student_name)
        bot.send_document(
            message.chat.id,
            document=("FOREX_AMT_Certificate.pdf", pdf_buffer),
            caption=f"🎓 تهانينا يا **{student_name}**! تم استخراج شهادتك بنجاح.",
            parse_mode="Markdown"
        )
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        logging.error(f"Certificate error: {e}")
        bot.edit_message_text("❌ حدث خطأ أثناء إنشاء الشهادة.", message.chat.id, msg.message_id)

# ==============================================================================
# --- 7. عرض مكتبة الدروس مع الصور ---
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
        "📚 **فهرس الدروس الشاملة (SMC/ICT)**\n─────────────────────────\nاختر الدرس للبدء بالقراءة والشرح التوضيحي:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==============================================================================
# --- 8. معالجة نقرات الأزرار التفاعلية (Callbacks) ---
# ==============================================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data.startswith("view_lesson_"):
        lesson_id = data.replace("view_lesson_", "")
        with get_db_connection() as conn:
            lesson = conn.execute("SELECT title, content, image_url FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
            
        if lesson:
            bot.answer_callback_query(call.id)
            caption = f"📘 **{lesson['title']}**\n─────────────────────────\n\n{lesson['content']}"
            if lesson['image_url']:
                try:
                    bot.send_photo(call.message.chat.id, lesson['image_url'], caption=caption, parse_mode="Markdown")
                except Exception:
                    bot.send_message(call.message.chat.id, caption, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, caption, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "الدرس غير موجود!")
        return

    if uid not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "🛑 إجراء محظور: للمشرفين فقط.", show_alert=True)
        return

    if data == "admin_stats":
        with get_db_connection() as conn:
            users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            consult_count = conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
            lessons_count = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
            
        stats_msg = (
            f"📊 **تقارير وإحصائيات المنظومة**\n─────────────────────────\n"
            f"👥 **المشتركين:** `{users_count}`\n"
            f"💬 **الاستشارات:** `{consult_count}`\n"
            f"📚 **الدروس المضافة:** `{lessons_count}`"
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text(stats_msg, call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard(), parse_mode="Markdown")

    elif data == "admin_manage_lessons":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🤖 توليد درس + شارت توضيحي بالذكاء", callback_data="admin_ai_gen_lesson"),
            types.InlineKeyboardButton("🗑️ حذف درس", callback_data="admin_delete_lesson_list"),
            types.InlineKeyboardButton("🔙 العودة للوحة", callback_data="admin_main")
        )
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📚 **قسم إدارة وتوليد الدروس**\nاختر الخيار المطلوب:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif data == "admin_ai_gen_lesson":
        user_states[uid] = "WAITING_AI_LESSON_TOPIC"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🤖 **أدخل اسم عنوان الدرس لتوليد الشرح والشارت التوضيحي تلقائياً:**", reply_markup=back_menu_markup(), parse_mode="Markdown")

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
# --- 9. معالجة رد الأدمن مباشرة على الاستشارات (Reply System) ---
# ==============================================================================

@bot.message_handler(func=lambda msg: msg.reply_to_message is not None)
def handle_admin_reply(message):
    uid = message.from_user.id
    
    if uid in ADMIN_IDS:
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        
        match = re.search(r"معرف المستخدم:\s*`?(\d+)`?", replied_text)
        if match:
            target_user_id = int(match.group(1))
            user_reply_text = f"💬 **وصلك رد من فريق الدعم والإدارة:**\n\n{message.text}"
            
            try:
                bot.send_message(target_user_id, user_reply_text, parse_mode="Markdown")
                bot.reply_to(message, "✅ **تم إرسال ردك للمستخدم بنجاح.**")
            except Exception as e:
                logging.error(f"Failed to deliver admin reply to user {target_user_id}: {e}")
                bot.reply_to(message, f"❌ تعذر إرسال الرد للمستخدم (ربما قام بحظر البوت):\n`{e}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚠️ لم يتم العثور على معرف المستخدم في الرسالة الأصلية.")

# ==============================================================================
# --- 10. معالجة الرسائل النصية المباشرة والذكاء الاصطناعي ---
# ==============================================================================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    uid = message.from_user.id
    state = user_states.get(uid)

    if state == "WAITING_AI_LESSON_TOPIC" and uid in ADMIN_IDS:
        topic = message.text
        user_states.pop(uid, None)
        status_msg = bot.send_message(message.chat.id, f"⚡ **جاري كتابة الشرح وتصميم الشارت التوضيحي لموضوع: '{topic}'...**", parse_mode="Markdown")
        
        try:
            prompt = (
                f"اكتب درساً تعليمياً مقتضباً ومباشراً باللغة العربية حول: '{topic}' في التداول وفق مفاهيم SMC/ICT.\n"
                f"الشروط:\n"
                f"1. الدخول المباشر في الشرح بدون مقدمات.\n"
                f"2. التنسيق في نقاط محددة وإموجي واضحة.\n"
                f"3. شروط التداول والتطبيق العملي."
            )
            ai_content = poll_generate_text(prompt)
            chart_img_url = poll_generate_chart_image_url(topic)
            lesson_title = f"درس: {topic}"

            with get_db_connection() as conn:
                conn.execute("INSERT INTO lessons (title, content, image_url) VALUES (?, ?, ?)", (lesson_title, ai_content, chart_img_url))
                conn.commit()

            channel_text = f"🎓 **[درس تعليمي + مثال توضيحي]**\n\n📘 **{lesson_title}**\n\n{ai_content}\n\n---\n📲 تابع المزيد عبر بوت الأكاديمية الرسمية."

            try:
                bot.send_photo(OFFICIAL_CHANNEL_ID, chart_img_url, caption=channel_text, parse_mode="Markdown")
            except Exception as ch_err:
                logging.error(f"Failed publishing photo to channel: {ch_err}")

            bot.delete_message(message.chat.id, status_msg.message_id)
            
            try:
                bot.send_photo(message.chat.id, chart_img_url, caption=f"✅ **تم إنشاء ونشر الدرس بنجاح!**\n\n📘 **{lesson_title}**\n\n{ai_content}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
            except Exception:
                bot.send_message(message.chat.id, f"✅ **تم نشر الدرس بنجاح!**\n\n📖 **{lesson_title}**\n\n{ai_content}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")

        except Exception as e:
            logging.error(f"Lesson Gen Error: {e}")
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
            
        support_msg = (
            f"📥 استشارة جديدة\n"
            f"👤 الاسم: {name}\n"
            f"🔗 المعرف: {username}\n"
            f"🆔 معرف المستخدم: {uid}\n\n"
            f"💬 نص الرسالة:\n{consult_text}\n\n"
            f"💡 للرد على هذا الشخص، اعمل (Reply / رد) على هذه الرسالة واكتب ردك مباشرة."
        )
        
        sent_success = False
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, support_msg)
                sent_success = True
            except Exception as e:
                logging.error(f"Failed to send support msg to admin {admin_id}: {e}")
        
        if sent_success:
            bot.reply_to(message, "✅ **تم إرسال استفسارك إلى فريق الدعم بنجاح وسنتواصل معك قريباً.**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ **تعذر وصول الرسالة للإدارة. يرجى تأكد الأدمن من فتح البوت والضغط على /start.**", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    ai_reply = poll_generate_text(message.text)
    bot.reply_to(message, ai_reply, reply_markup=main_menu_markup(uid), parse_mode="Markdown")

# ==============================================================================
# --- 11. تحليل الشارتات عند إرسال صورة (تحويل الصورة لـ Base64) ---
# ==============================================================================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')
    status_msg = bot.reply_to(message, "⏳ **جاري تحليل الشارت وقراءة المستويات بالذكاء الاصطناعي...**", parse_mode="Markdown")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')
        analysis_result = poll_analyze_chart_vision(image_base64)

        if analysis_result:
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.reply_to(message, f"📊 **[نتيجة تحليل الشارت الذكي]**\n─────────────────────────\n\n{analysis_result}", reply_markup=main_menu_markup(uid), parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ تعذر تحليل الشارت حالياً، يرجى إعادة محاولة إرسال الصورة.", message.chat.id, status_msg.message_id)

    except Exception as e:
        logging.error(f"Vision Processing Error: {e}")
        bot.edit_message_text(f"❌ حدث خطأ أثناء معالجة الصورة:\n`{str(e)}`", message.chat.id, status_msg.message_id, parse_mode="Markdown")

# ==============================================================================
# --- 12. مسار الـ Webhook الخاص بـ Flask للعمل على Render ---
# ==============================================================================

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

@app.route('/')
def home():
    return "FOREX AMT Bot is Running Smoothly with Webhook! 🚀"

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    try:
        json_data = request.get_json(force=True)
        if json_data:
            update = telebot.types.Update.de_json(json_data)
            bot.process_new_updates([update])
    except Exception as e:
        logging.error(f"Error processing update: {e}")
    
    return "OK", 200

def set_render_webhook():
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        webhook_url = f"{render_url}{WEBHOOK_PATH}"
        try:
            bot.remove_webhook()
            bot.set_webhook(url=webhook_url)
            logging.info(f"Webhook set successfully to: {webhook_url}")
        except Exception as e:
            logging.error(f"Failed to set webhook automatically: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
else:
    set_render_webhook()
