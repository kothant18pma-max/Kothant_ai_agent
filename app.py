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
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- API Clients Setup ---
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
hf_client = InferenceClient(token=os.environ.get("HF_TOKEN")) # Optional Hugging Face use

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Multi-Model AI Agent is Live!"

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

def get_groq_chat(user_text):
    # Groq ကို သုံးပြီး Chat တုံ့ပြန်မှုကို အလွန်မြန်အောင် လုပ်ခြင်း
    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": f"Please reply in Myanmar language: {user_text}"}],
        model="llama3-8b-8192",
    )
    return chat_completion.choices[0].message.content

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

# --- ၁။ Text Message Handler (Groq ကို သုံး၍ Chatting လုပ်ခြင်း) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
    try:
        # Chat အတွက် Groq က ပိုမြန်လို့ Groq ကို သုံးထားပါတယ်
        res = get_groq_chat(user_text)
        await update.message.reply_text(res)
    except Exception as e:
        await update.message.reply_text(f"Groq Error: {str(e)}. Switching to Gemini...")
        res = get_gemini_response(user_text)
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
        [InlineKeyboardButton("🔍 OCR (စာကူးမယ်)", callback_data='ocr'),
         InlineKeyboardButton("📝 အနှစ်ချုပ်/Audio", callback_data='summary')],
        [InlineKeyboardButton("📊 Excel ထုတ်မယ်", callback_data='excel'),
         InlineKeyboardButton("📽️ Slide (PPT) လုပ်မယ်", callback_data='ppt')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📁 ဖိုင်ရရှိပါပြီ။ ဘယ် AI Service သုံးမလဲ?", reply_markup=reply_markup)

# --- ၃။ Callback Handler ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    file_path = context.user_data.get('current_file')
    
    if not file_path:
        await query.edit_message_text("❌ ဖိုင်သက်တမ်းကုန်သွားပါပြီ။")
        return

    await query.edit_message_text(f"⚙️ Gemini Vision ဖြင့် {command.upper()} လုပ်ဆောင်နေပါသည်...")
    
    prompts = {
        "ocr": "ဤဖိုင်ထဲမှ စာသားအားလုံးကို Transcription ထုတ်ပေးပါ။",
        "summary": "ဤဖိုင်ကို မြန်မာလို အနှစ်ချုပ်ပေးပါ။",
        "excel": "ဤဖိုင်ထဲမှ ဇယားများကို Markdown Table format ဖြင့်သာ ထုတ်ပေးပါ။",
        "ppt": "Presentation Slide လုပ်ရန် အဓိကအချက်များကို Bullet points ဖြင့် ထုတ်ပေးပါ။"
    }
    
    # File analysis အတွက် Gemini က Vision ပိုကောင်းပါတယ်
    res = get_gemini_response(prompts[command], file_path)

    chat_id = query.message.chat_id
    if command == "ocr":
        await context.bot.send_message(chat_id=chat_id, text=f"🔍 OCR Result:\n\n{res}")
    elif command == "summary":
        await context.bot.send_message(chat_id=chat_id, text=f"📝 Summary:\n\n{res}")
        tts = gTTS(text=res, lang='my'); bio = BytesIO(); tts.write_to_fp(bio); bio.seek(0)
        await context.bot.send_audio(chat_id=chat_id, audio=bio, title="AI Voice Summary")
    elif command == "excel":
        ex = get_excel(res)
        if ex: await context.bot.send_document(chat_id=chat_id, document=BytesIO(ex), filename="Data.xlsx")
    elif command == "ppt":
        ppt_file = create_ppt(res)
        await context.bot.send_document(chat_id=chat_id, document=ppt_file, filename="Presentation.pptx")

# --- Bot Start ---
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
        app.add_handler(CallbackQueryHandler(button_click))
        print("Bot is ready with Groq & Gemini...")
        app.run_polling(drop_pending_updates=True)
