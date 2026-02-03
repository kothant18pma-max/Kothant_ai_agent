import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from docx import Document
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Interactive AI Agent is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- AI Logic ---
def get_ai_response(file_path, command_type):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    uploaded_file = genai.upload_file(path=file_path)
    
    prompts = {
        "ocr": "ဤဖိုင်ထဲမှ စာသားအားလုံးကို တစ်လုံးမကျန် Transcription ထုတ်ပေးပါ။",
        "summary": "ဤဖိုင်ကို မြန်မာလို အနှစ်ချုပ်နှင့် ဘာသာပြန်ပေးပါ။ (Audio အတွက် သီးသန့်ပေးပါ)",
        "excel": "ဤဖိုင်ထဲမှ ဇယားများကို Markdown Table format ဖြင့်သာ ထုတ်ပေးပါ။",
        "ppt": "Presentation Slide လုပ်ရန်အတွက် အဓိကအချက်များကို Bullet points များဖြင့် ထုတ်ပေးပါ။"
    }
    
    response = model.generate_content([prompts[command_type], uploaded_file])
    return response.text

# --- Helper Functions (PPT, Excel, Audio) ---
def create_ppt(text):
    prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "AI Data Summary"
    slide.placeholders[1].text = text[:1000]
    bio = BytesIO(); prs.save(bio); bio.seek(0); return bio

def get_excel(text):
    try:
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            df = pd.DataFrame(lines); bio = BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer: df.to_excel(writer, index=False, header=False)
            return bio.getvalue()
    except: return None

# --- Telegram Media Handler ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = None; suffix = ""
    if update.message.document:
        file_obj = await update.message.document.get_file(); suffix = ".pdf"
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file(); suffix = ".jpg"
    
    if not file_obj: return

    # ဖိုင်ကို ခေတ္တသိမ်းပြီး Path ကို Context ထဲမှာ မှတ်ထားခြင်း
    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    
    # ခလုတ်များ ပြသခြင်း
    keyboard = [
        [InlineKeyboardButton("🔍 OCR ဖတ်မယ်", callback_data='ocr'),
         InlineKeyboardButton("📝 အနှစ်ချုပ်/Audio", callback_data='summary')],
        [InlineKeyboardButton("📊 Excel ထုတ်မယ်", callback_data='excel'),
         InlineKeyboardButton("📽️ Slide (PPT) လုပ်မယ်", callback_data='ppt')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("ဖိုင်ကို လက်ခံရရှိပါပြီ။ ဘာလုပ်ပေးရမလဲ ရွေးချယ်ပါ -", reply_markup=reply_markup)

# --- Button Callback Handler ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    command = query.data
    file_path = context.user_data.get('current_file')
    
    if not file_path:
        await query.edit_message_text("ဖိုင်သက်တမ်း ကုန်ဆုံးသွားပါပြီ။ ပြန်ပို့ပေးပါ။")
        return

    await query.edit_message_text(f"လုပ်ဆောင်နေပါသည်... ⏳ ({command.upper()})")
    res = get_ai_response(file_path, command)

    # ခိုင်းစေသည့် အလုပ်အလိုက် ရလဒ်ထုတ်ပေးခြင်း
    if command == "ocr":
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"🔍 OCR Result:\n\n{res}")
        doc_bio = BytesIO(); doc = Document(); doc.add_paragraph(res); doc.save(doc_bio)
        await context.bot.send_document(chat_id=query.message.chat_id, document=BytesIO(doc_bio.getvalue()), filename="OCR.docx")
    
    elif command == "summary":
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"📝 Summary:\n\n{res}")
        tts = gTTS(text=res, lang='my'); audio_bio = BytesIO(); tts.write_to_fp(audio_bio); audio_bio.seek(0)
        await context.bot.send_audio(chat_id=query.message.chat_id, audio=audio_bio, title="Summary Voice")

    elif command == "excel":
        ex = get_excel(res)
        if ex: await context.bot.send_document(chat_id=query.message.chat_id, document=BytesIO(ex), filename="Data.xlsx")
        else: await context.bot.send_message(chat_id=query.message.chat_id, text="ဇယားကွက် မတွေ့ရှိပါ။")

    elif command == "ppt":
        ppt_file = create_ppt(res)
        await context.bot.send_document(chat_id=query.message.chat_id, document=ppt_file, filename="Presentation.pptx")

# --- Bot Execution ---
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        app.add_handler(CallbackQueryHandler(button_click)) # ခလုတ်နှိပ်ခြင်းကို စစ်ဆေးရန်
        app.run_polling(drop_pending_updates=True)
