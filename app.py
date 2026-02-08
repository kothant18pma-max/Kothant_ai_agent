import os
import threading
import tempfile
import google.generativeai as genai
from huggingface_hub import InferenceClient
from openai import OpenAI
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# --- API Clients Setup ---

# 1. Grok (xAI) Setup
grok_key = os.environ.get("XAI_API_KEY")
grok_client = OpenAI(api_key=grok_key, base_url="https://api.x.ai/v1") if grok_key else None

# 2. DeepSeek Setup
ds_key = os.environ.get("DEEPSEEK_API_KEY")
ds_client = OpenAI(api_key=ds_key, base_url="https://api.deepseek.com") if ds_key else None

# 3. Hugging Face Setup
hf_token = os.environ.get("HF_TOKEN")
hf_client = InferenceClient(model="mistralai/Mistral-7B-Instruct-v0.3", token=hf_token) if hf_token else None

# --- Flask Server (Render အတွက်) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Core Functions ---

def get_grok_res(text):
    if not grok_client: return None
    try:
        response = grok_client.chat.completions.create(
            model="grok-beta", # သို့မဟုတ် grok-2
            messages=[{"role": "user", "content": text}]
        )
        return response.choices[0].message.content
    except Exception: return None

def get_deepseek_res(text):
    if not ds_client: return None
    try:
        response = ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "Reply in Myanmar."}, {"role": "user", "content": text}]
        )
        return response.choices[0].message.content
    except Exception: return None

def get_gemini_res(prompt, file_path=None):
    key = os.environ.get("GOOGLE_API_KEY")
    if not key: return "Error: Gemini Key missing."
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    if file_path:
        up_file = genai.upload_file(path=file_path)
        return model.generate_content([prompt, up_file]).text
    return model.generate_content(prompt).text

# Chat Logic (Priority: DeepSeek -> Grok -> HF -> Gemini Fallback)
def get_ai_chat(text):
    # ၁။ DeepSeek ကို အရင်စမ်းမည်
    res = get_deepseek_res(text)
    if res: return res

    # ၂။ DeepSeek မရလျှင် Grok ကို သုံးမည်
    res = get_grok_res(text)
    if res: return res

    # ၃။ Grok မရလျှင် Hugging Face ကို သုံးမည်
    if hf_client:
        try:
            res_hf = ""
            for msg in hf_client.chat_completion(messages=[{"role": "user", "content": text}], max_tokens=500, stream=True):
                res_hf += msg.choices[0].delta.content or ""
            if res_hf: return res_hf
        except: pass

    # ၄။ အကုန်လုံး မရမှ Gemini ဖြင့် ဖြေမည်
    return get_gemini_res(f"Reply in Myanmar: {text}")

# --- Handlers ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = get_ai_chat(update.message.text)
    await update.message.reply_text(res)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = await (update.message.document or update.message.photo[-1]).get_file()
    suffix = ".pdf" if update.message.document else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
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
    prompt = "Extract all text from this file." if cmd == 'ocr' else "Summarize this clearly in Myanmar."
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
