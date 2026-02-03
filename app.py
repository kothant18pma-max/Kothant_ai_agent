import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from groq import Groq
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- API Keys Safety Loading ---
def get_env(key):
    val = os.environ.get(key)
    if not val:
        print(f"⚠️ Warning: {key} is missing in Dashboard Environment Variables!")
    return val

GROQ_KEY = get_env("GROQ_API_KEY")
GEMINI_KEY = get_env("GOOGLE_API_KEY")
TG_TOKEN = get_env("TELEGRAM_TOKEN")

# --- Flask Health Check ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Logics ---
def get_groq_chat(text):
    if not GROQ_KEY: return "Error: Groq API Key missing in Settings."
    client = Groq(api_key=GROQ_KEY)
    chat = client.chat.completions.create(
        messages=[{"role": "user", "content": f"Reply in Myanmar: {text}"}],
        model="llama3-8b-8192"
    )
    return chat.choices[0].message.content

# --- Handlers ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = get_groq_chat(update.message.text)
    await update.message.reply_text(res)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ဖိုင်ရရှိပါပြီ။ ခေတ္တစောင့်ပေးပါ။")

# --- Main Bot Launch ---
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    
    if TG_TOKEN:
        app = ApplicationBuilder().token(TG_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        print("--- Bot is Starting ---")
        app.run_polling(drop_pending_updates=True)
