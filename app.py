import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from groq import Groq
from huggingface_hub import InferenceClient
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- API Clients Setup ---
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
hf_client = InferenceClient(token=os.environ.get("HF_TOKEN"))

# --- Flask Server (Render Health Check) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Multi-AI Agent is Online!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Logic Functions ---
def get_groq_chat(user_text):
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": f"Please reply in Myanmar: {user_text}"}],
            model="llama3-8b-8192"
        )
        return completion.choices[0].message.content
    except:
        # Groq အဆင်မပြေလျှင် Gemini ဖြင့် အစားထိုးသည်
        model = genai.GenerativeModel('gemini-2.5-flash')
        return model.generate_content(user_text).text

def get_gemini_file_analysis(file_path, prompt):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    uploaded_file = genai.upload_file(path=file_path)
    return model.generate_content([prompt, uploaded_file]).text

# --- Telegram Handlers ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
    res = get_groq_chat(update.message.text)
    await update.message.reply_text(res)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = await (update.message.document or update.message.photo[-1]).get_file()
    suffix = ".pdf" if update.message.document else ".jpg"
    
    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    
    keyboard = [
        [InlineKeyboardButton("🔍 OCR", callback_data='ocr'), InlineKeyboardButton("📝 Summary/Audio", callback_data='summary')],
        [InlineKeyboardButton("📊 Excel", callback_data='excel'), InlineKeyboardButton("📽️ PPT Slide", callback_data='ppt')]
    ]
    await update.message.reply_text("📁 ဖိုင်ရရှိပါပြီ။ ဘာလုပ်ပေးရမလဲ?", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_path = context.user_data.get('current_file')
    if not file_path: return
    
    cmd = query.data
    prompts = {
        "ocr": "Extract all text (OCR).",
        "summary": "Summarize in Myanmar and English.",
        "excel": "Extract tables to Markdown.",
        "ppt": "Key points for PPT slide."
    }
    
    await query.edit_message_text(f"⚙️ {cmd.upper()} လုပ်ဆောင်နေပါသည်...")
    res = get_gemini_file_analysis(file_path, prompts[cmd])
    
    # ရလဒ်ပေးပို့ခြင်း (Audio, PPT, Excel logic များ အရင်အတိုင်း ထည့်သွင်းနိုင်သည်)
    await context.bot.send_message(chat_id=query.message.chat_id, text=res[:4000])

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        app.add_handler(CallbackQueryHandler(button_click))
        app.run_polling(drop_pending_updates=True)
