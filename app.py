import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from flask import Flask
from telegram import Update
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from docx import Document
from io import BytesIO

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is Healthy!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Gemini Multimodal Logic ---
def process_with_gemini(file_path, is_image=True):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # ဖိုင်ကို Gemini ဆီသို့ တိုက်ရိုက် Upload တင်ခြင်း
    sample_file = genai.upload_file(path=file_path)
    
    prompt = """
    ဤဖိုင်ထဲတွင်ပါဝင်သော အချက်အလက်များကို အသေးစိတ်ဖတ်ပါ။ 
    ၁။ စာသားအားလုံးကို မြန်မာလို အနှစ်ချုပ်ပေးပါ။
    ၂။ ဇယားများ (Tables) ပါဝင်ပါက Markdown Table format (| Column |) ဖြင့် တိကျစွာ ထုတ်ပေးပါ။
    ၃။ ကိန်းဂဏန်းအချက်အလက်များကို မလွဲမချော်အောင် အထူးဂရုစိုက်ပါ။
    """
    
    response = model.generate_content([prompt, sample_file])
    return response.text

# --- Excel Logic ---
def get_excel(text):
    try:
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            df = pd.DataFrame(lines)
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, header=False)
            return bio.getvalue()
    except: return None

# --- Telegram Handlers ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        
        # PDF သို့မဟုတ် ပုံ ဖြစ်မဖြစ် စစ်ဆေးခြင်း
        if update.message.document and update.message.document.mime_type == 'application/pdf':
            file_obj = await update.message.document.get_file()
            suffix = ".pdf"
            msg = "PDF ဖတ်နေပါသည်..."
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
            suffix = ".jpg"
            msg = "ပုံထဲက Data များကို ဖတ်နေပါသည်..."
        else: return

        await update.message.reply_text(f"{msg} 🔍")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            await file_obj.download_to_drive(t.name)
            # Gemini ဖြင့် တိုက်ရိုက်ဖတ်ခြင်း
            res = process_with_gemini(t.name)
            
            for i in range(0, len(res), 4000): 
                await update.message.reply_text(res[i:i+4000])
            
            ex = get_excel(res)
            if ex: await update.message.reply_document(document=BytesIO(ex), filename="Extracted_Data.xlsx")
            os.remove(t.name)
            
    except Exception as e: await update.message.reply_text(f"Error: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        # PDF နှင့် ပုံ နှစ်ခုလုံးကို Handler တစ်ခုတည်းဖြင့် ကိုင်တွယ်ခြင်း
        app.add_handler(MessageHandler(filters.Document.PDF | filters.PHOTO, handle_media))
        app.run_polling(drop_pending_updates=True)
