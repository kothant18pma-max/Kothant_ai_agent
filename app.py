import os
import threading
import tempfile
import google.generativeai as genai
from huggingface_hub import InferenceClient
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from io import BytesIO
from gtts import gTTS

# --- API Clients Setup ---
# Hugging Face: စကားပြောရန် (Chat)
hf_token = os.environ.get("HF_TOKEN")
hf_client = InferenceClient(model="mistralai/Mistral-7B-Instruct-v0.3", token=hf_token) if hf_token else None

# --- Flask Server (Render Health Check အတွက်) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Core Functions ---
def get_gemini_res(prompt, file_path=None):
    # Gemini: ဖိုင်ဖတ်ရန် (Vision)
    key = os.environ.get("GOOGLE_API_KEY")
    if not key: return "Error: Gemini API Key missing."
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    if file_path:
        up_file = genai.upload_file(path=file_path)
        return model.generate_content([prompt, up_file]).text
    return model.generate_content(prompt).text

def get_hf_chat(text):
    if not hf_client: return get_gemini_res(f"Reply in Myanmar: {text}")
    try:
        # Hugging Face စာပြန်ခြင်း
        res = ""
        for msg in hf_client.chat_completion(messages=[{"role": "user", "content": text}], max_tokens=500, stream=True):
            res += msg.choices[0].delta.content or ""
        return res
    except: return get_gemini_res(f"Reply in Myanmar: {text}")

# --- Handlers ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # စာရိုက်လျှင် Hugging Face က ဖြေမည်
    res = get_hf_chat(update.message.text)
    await update.message.reply_text(res)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ဖိုင်ပို့လျှင် Gemini က ကိုင်တွယ်မည်
    file_obj = await (update.message.document or update.message.photo[-1]).get_file()
    suffix = ".pdf" if update.message.document else ".jpg"
    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    
    kb = [[InlineKeyboardButton("🔍 OCR", callback_data='ocr'), InlineKeyboardButton("📝 Summary", callback_data='sum')]]
    await update.message.reply_text("📁 ဖိုင်ရပါပြီ။ ဘာလုပ်ရမလဲ?", reply_markup=InlineKeyboardMarkup(kb))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_path = context.user_data.get('current_file')
    if not file_path: return

    cmd = query.data
    prompt = "Extract text." if cmd == 'ocr' else "Summarize this in Myanmar."
    await query.edit_message_text(f"⚙️ {cmd.upper()} လုပ်ဆောင်နေပါသည်...")
    res = get_gemini_res(prompt, file_path)
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
