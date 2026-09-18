import io
import base64
import logging
import sqlite3
import requests
import telebot
from telebot import types
from groq import Groq
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas

# ==============================================================================
# --- 1. الإعدادات والمفاتيح المباشرة (Direct Configuration) ---
# ==============================================================================

BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
GROQ_API_KEY = "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"

# ضع مفتاح OpenAI الخاص بك هنا لتحليل صور الشارتات
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"

# معرّفات القنوات والمشرفين
OFFICIAL_CHANNEL_ID = -1004363402118  # القناة العامة للتوصيات (FOREX AMT)
SUPPORT_CHAT_ID = -1004488517670      # قناة/مجموعة الدعم والاستشارات
ADMIN_IDS = [966607076]               # معرّف المشرف/المطور

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# تهيئة البوت وعميل Groq
bot = telebot.TeleBot(BOT_TOKEN)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# قاموس لتتبع حالات المستخدمين
user_states = {}

# ==============================================================================
# --- 2. قاعدة البيانات (SQLite DB) ---
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
        conn.commit()

init_db()

# ==============================================================================
# --- 3. إنشاء الشهادات في الذاكرة (RAM) ---
# ==============================================================================

def generate_pdf_certificate_memory(student_name):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = 792, 612
    
    # رسم الإطار الخارجية
    c.setStrokeColorRGB(0.1, 0.1, 0.3)
    c.setLineWidth(5)
    c.rect(30, 30, width - 60, height - 60)
    
    # النصوص والأنماط
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
# --- 4. الأزرار والمجموعات التفاعلية ---
# ==============================================================================

def main_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("📈 القناة الرسمية"),
        types.KeyboardButton("💬 طلب استشارة / دعم"),
        types.KeyboardButton("📊 تحليل شارت (ارسل صورة)"),
        types.KeyboardButton("🎓 شهادة الدورة (PDF)"),
        types.KeyboardButton("ℹ️ حول البوت")
    )
    return markup

def back_menu_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 العودة للقائمة الرئيسية"))
    return markup

# ==============================================================================
# --- 5. التعامل مع الأوامر والأزرار الأساسية ---
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
        "يمكنك الآن طرح أي سؤال حول الـ SMC، إرسال صورة الشارت لتحليلها بالذكاء الاصطناعي، أو طلب دعم واستشارة مباشرة."
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_markup(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🔙 العودة للقائمة الرئيسية")
def back_to_main(message):
    user_states.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "تمت العودة للقائمة الرئيسية.", reply_markup=main_menu_markup())

@bot.message_handler(func=lambda msg: msg.text == "📈 القناة الرسمية")
def channel_info(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("الانضمام للقناة 🚀", url="https://t.me/wwwforexmta"))
    bot.send_message(message.chat.id, "تابع قناتنا الرسمية FOREX AMT للتوصيات والتحليلات اليومية:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ حول البوت")
def about_bot(message):
    about_text = (
        "🤖 **بوت FOREX AMT الذكي**\n\n"
        "• يحلل الشارتات الفنية باستخدام OpenAI Vision.\n"
        "• يجيب على كافة الاستفسارات التعليمية واستراتيجيات SMC فورياً عبر Groq AI.\n"
        "• يربطك مباشرة بفريق الدعم الفني والاستشارات."
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

@bot.message_handler(func=lambda msg: msg.text == "💬 طلب استشارة / دعم")
def request_consultation(message):
    user_states[message.from_user.id] = "WAITING_CONSULTATION"
    bot.send_message(
        message.chat.id,
        "اكتب استفسارك أو رسالتك الآن بالتفصيل، وسأقوم بتحويلها مباشرة إلى فريق الدعم:",
        reply_markup=back_menu_markup()
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 تحليل شارت (ارسل صورة)")
def request_chart_analysis(message):
    user_states[message.from_user.id] = "WAITING_CHART_IMAGE"
    bot.send_message(
        message.chat.id,
        "قم بإرسال صورة الشارت الآن لتقييمها واستخراج مناطق الـ SMC منها بالذكاء الاصطناعي.",
        reply_markup=back_menu_markup()
    )

# ==============================================================================
# --- 6. معالجة النصوص المحادثة والأسئلة (Groq AI) ---
# ==============================================================================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    uid = message.from_user.id
    state = user_states.get(uid)
    
    # 1. توجيه استفسارات الدعم والاستشارات
    if state == "WAITING_CONSULTATION":
        user_states.pop(uid, None)
        consult_text = message.text
        name = message.from_user.first_name or "المستخدم"
        username = f"@{message.from_user.username}" if message.from_user.username else "بدون معرف"
        
        with get_db_connection() as conn:
            conn.execute("INSERT INTO consultations (user_id, full_name, message) VALUES (?, ?, ?)", (uid, name, consult_text))
            conn.commit()
            
        bot.reply_to(message, "✅ تم إرسال رسالتك إلى فريق الدعم بنجاح!", reply_markup=main_menu_markup())
        
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

    # 2. الرد الآلي الذكي على الأسئلة عبر Groq LLM
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
            bot.reply_to(message, response.choices[0].message.content, reply_markup=main_menu_markup())
            return
        except Exception as e:
            logging.error(f"Groq API Error: {e}")

    bot.send_message(message.chat.id, "الرجاء اختيار أحد الخيارات من القائمة أدناه:", reply_markup=main_menu_markup())

# ==============================================================================
# --- 7. تحليل الصور والشارتات (OpenAI Vision) ---
# ==============================================================================

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id
    bot.send_chat_action(message.chat.id, 'typing')
    status_msg = bot.reply_to(message, "⏳ **جاري تحليل الشارت وقراءة مستويات الـ SMC بالذكاء الاصطناعي...**", parse_mode="Markdown")
    
    try:
        # تحميل صورة الشارت وتحويلها لـ Base64
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

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_instruction},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            "max_tokens": 800
        }
        
        res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        res_json = res.json()
        
        if 'choices' in res_json:
            analysis_result = res_json['choices'][0]['message']['content']
        else:
            analysis_result = "⚠️ تعذر تحليل الشارت آلياً. تم توجيهه لفريق الدعم والمحللين."

        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.reply_to(message, f"🎯 **[نتيجة تحليل الشارت الذكي]**\n\n{analysis_result}", reply_markup=main_menu_markup(), parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Vision Processing Error: {e}")
        bot.edit_message_text("❌ حدث خطأ أثناء معالجة صورة الشارت.", message.chat.id, status_msg.message_id)

    # إعادة توجيه نسخة من الصورة إلى قناة الدعم والمحللين
    try:
        caption = f"📸 **شارت جديد للتحليل** من: {message.from_user.first_name} (`{uid}`)"
        bot.send_photo(SUPPORT_CHAT_ID, message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed forwarding chart to support: {e}")

# ==============================================================================
# --- 8. أوامر المشرفين للنشر (Admin Command) ---
# ==============================================================================

@bot.message_handler(commands=['post'])
def post_to_official_channel(message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    text_to_post = message.text.replace("/post", "").strip()
    if not text_to_post:
        bot.reply_to(message, "يرجى كتابة النص المراد نشره بعد الأمر. مثال:\n`/post توصية جديدة...`", parse_mode="Markdown")
        return
        
    try:
        bot.send_message(OFFICIAL_CHANNEL_ID, text_to_post, parse_mode="Markdown")
        bot.reply_to(message, "✅ تم نشر الرسالة بنجاح في القناة الرسمية!")
    except Exception as e:
        bot.reply_to(message, f"❌ فشل النشر في القناة: {e}")

# ==============================================================================
# --- 9. تشغيل البوت الرئيسي ---
# ==============================================================================

if __name__ == "__main__":
    logging.info("Starting FOREX AMT Bot...")
    bot.infinity_polling(skip_pending=True)
