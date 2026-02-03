import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from groq import Groq
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- API Keys Loading (Dashboard ထဲမှာ ထည့်ဖို့ မမေ့ပါနဲ့) ---
GROQ_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")

# --- Flask Health Check ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Running!"

def run_flask():
    # Render Port ကို အတိအကျ ယူသုံးခြင်း
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Logic (Error-Safe) ---
def get_groq_response(text):
    if not GROQ_KEY: return "Error: Groq API Key is missing in Dashboard."
    client = Groq(api_key=GROQ_KEY)
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": f"Reply in Myanmar: {text}"}],
        model="llama3-8b-8192"
    )
    return chat.choices[0].message.content

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
    res = get_groq_response(update.message.text)
    await update.message.reply_text(res)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Media handling logic here...
    file_obj = await (update.message.document or update.message.photo[-1]).get_file()
    t = tempfile.NamedTemporaryFile(delete=False, suffix=".file")
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    
    keyboard = [[InlineKeyboardButton("🔍 OCR", callback_data='ocr'), InlineKeyboardButton("📝 Summary", callback_data='summary')]]
    await update.message.reply_text("ဖိုင်ရပါပြီ။ ဘာလုပ်ပေးရမလဲ?", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Main Initialization ---
if __name__ == '__main__':
    # Start Flask first
    threading.Thread(target=run_flask, daemon=True).start()
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        print("Bot Started Successfully!")
        app.run_polling(drop_pending_updates=True)
    else:
        print("Error: TELEGRAM_TOKEN missing!")
