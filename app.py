import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from huggingface_hub import InferenceClient
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- API Clients Setup ---
# Hugging Face Client (စကားပြောရန်အတွက် Mistral သို့မဟုတ် Llama-3 model သုံးနိုင်သည်)
hf_client = InferenceClient(model="mistralai/Mistral-7B-Instruct-v0.3", token=os.environ.get("HF_TOKEN"))

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Gemini-HF Agent is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Logic Functions ---
def get_gemini_response(prompt_text, file_path=None):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    if file_path:
        uploaded_file = genai.upload_file(path=file_path)
        response = model.generate_content([prompt_text, uploaded_file])
    else:
        response = model.generate_content(prompt_text)
    return response.text

def get_hf_chat(user_text):
    # Hugging Face ကိုသုံးပြီး စာပြန်ခြင်း
    prompt = f"<s>[INST] Please reply in Myanmar language: {user_text} [/INST]</s>"
    response = ""
    for message in hf_client.chat_completion(
        messages=[{"role": "user", "content": user_text}],
        max_tokens=500,
        stream=True,
    ):
        response += message.choices[0].delta.content or ""
    return response

# --- Helper Functions (PPT, Excel) ---
def create_ppt(text):
    prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "AI Summary Report"; slide.placeholders[1].text = text[:1000]
    bio = BytesIO(); prs.save(bio); bio.seek(0); return bio

def get_excel(text):
    try:
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            df = pd.DataFrame(lines); bio = BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer: df.to_excel(writer, index=False, header=False)
            return bio.getvalue()
    except: return None

# --- ၁။ Text Message Handler (Hugging Face ကို သုံး၍ Chat လုပ်ခြင်း) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
    try:
        # စာရိုက်ခြင်းအတွက် Hugging Face ကို သုံးသည်
        res = get_hf_chat(user_text)
        await update.message.reply_text(res)
    except Exception as e:
        # Error တက်ပါက Gemini ဖြင့် Backup လုပ်သည်
        res = get_gemini_response(f"Reply in Myanmar: {user_text}")
        await update.message.reply_text(res)

# --- ၂။ Media Handler (Gemini ကို သုံး၍ File ဖတ်ခြင်း) ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = None; suffix = ""
    if update.message.document:
        file_obj = await update.message.document.get_file(); suffix = ".pdf"
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file(); suffix = ".jpg"
    
    if not file_obj: return

    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    
    keyboard = [
        [InlineKeyboardButton("🔍 OCR", callback_data='ocr'),
         InlineKeyboardButton("📝 အနှစ်ချုပ်/Audio", callback_data='summary')],
        [InlineKeyboardButton("📊 Excel", callback_data='excel'),
         InlineKeyboardButton("📽️ Slide (PPT)", callback_data='ppt')]
    ]
    await update.message.reply_text("📁 ဖိုင်ရရှိပါပြီ။ ဘာလုပ်ပေးရမလဲ?", reply_markup=InlineKeyboardMarkup(keyboard))

# --- ၃။ Callback Handler ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    file_path = context.user_data.get('current_file')
    
    if not file_path:
        await query.edit_message_text("❌ ဖိုင်သက်တမ်းကုန်သွားပါပြီ။")
        return

    await query.edit_message_text(f"⚙️ လုပ်ဆောင်နေပါသည်: {command.upper()}...")
    
    prompts = {
        "ocr": "Extract all text from this file.",
        "summary": "Summarize this file in Myanmar language.",
        "excel": "Extract tables to Markdown Table format.",
        "ppt": "Key points for a presentation slide."
    }
    
    # ဖိုင်ဖတ်ရန် Gemini ကို သုံးသည်
    res = get_gemini_response(prompts[command], file_path)
    chat_id = query.message.chat_id

    if command == "summary":
        await context.bot.send_message(chat_id=chat_id, text=res)
        tts = gTTS(text=res, lang='my'); bio = BytesIO(); tts.write_to_fp(bio); bio.seek(0)
        await context.bot.send_audio(chat_id=chat_id, audio=bio, title="AI Summary Voice")
    elif command == "excel":
        ex = get_excel(res)
        if ex: await context.bot.send_document(chat_id=chat_id, document=BytesIO(ex), filename="Data.xlsx")
    elif command == "ppt":
        ppt_file = create_ppt(res)
        await context.bot.send_document(chat_id=chat_id, document=ppt_file, filename="Presentation.pptx")
    else:
        await context.bot.send_message(chat_id=chat_id, text=res[:4000])

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        app.add_handler(CallbackQueryHandler(button_click))
        print("Bot started with Gemini & HF...")
        app.run_polling(drop_pending_updates=True)
