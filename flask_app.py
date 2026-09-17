import os
from flask import Flask, request
import telebot

BOT_TOKEN = "8616578192:AAGu7PJPpqpCxGSHvd1pq5hIE9w1K42YS0E"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

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

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "مرحباً بك في أكاديمية النيزك! 🚀\nالسيرفر يعمل الآن بنجاح وبشكل مستقر.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"تم استلام رسالتك: {message.text}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
