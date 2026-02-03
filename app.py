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

# --- ၁။ Flask Server (Render Health Check အတွက် အရင်ဆုံးထားပါ) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- ၂။ Smart AI & OCR Logic ---
def process_smart_ai(file_path):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    uploaded_file = genai.upload_file(path=file_path)
    
    prompt = """
    ဤဖိုင်ကို အသေးစိတ် စစ်ဆေးပြီး အောက်ပါအတိုင်း လုပ်ဆောင်ပါ -
    ၁။ အကယ်၍ ဖတ်ရန်စာသား မရှိပါက 'DATA_INSUFFICIENT' ဟုသာ ရေးပါ။
    ၂။ ဖတ်ရန်ရှိပါက -
       - [OCR]: စာသားအားလုံးကို တစ်လုံးမကျန် Transcription အရင်ထုတ်ပါ။
       - [Summary]: မြန်မာလို အနှစ်ချုပ်နှင့် ဘာသာပြန်ပေးပါ။
       - [Tables]: ဇယားများပါက Markdown Table format (| Col |) ဖြင့် ထုတ်ပေးပါ။
    """
    response = model.generate_content([prompt, uploaded_file])
    return response.text

# --- ၃။ Excel Conversion ---
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
    return None

# --- ၄။ Telegram Handler (NameError မဖြစ်အောင် ဤနေရာတွင် ထားပါ) ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        
        # File type စစ်ဆေးခြင်း
        file_obj = None
        suffix = ""
        if update.message.document:
            file_obj = await update.message.document.get_file()
            suffix = ".pdf"
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
            suffix = ".jpg"
        
        if not file_obj: return

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            await file_obj.download_to_drive(t.name)
            res = process_smart_ai(t.name)
            
            if "DATA_INSUFFICIENT" in res:
                await update.message.reply_text("⚠️ ဤဖိုင်တွင် ဖတ်ရန်စာသား မတွေ့ပါ။")
            else:
                for i in range(0, len(res), 4000):
                    await update.message.reply_text(res[i:i+4000])
                
                # Excel & Word Files
                ex = get_excel(res)
                if ex: await update.message.reply_document(document=BytesIO(ex), filename="Table_Data.xlsx")
                
                doc_bio = BytesIO(); doc = Document(); doc.add_paragraph(res); doc.save(doc_bio)
                await update.message.reply_document(document=BytesIO(doc_bio.getvalue()), filename="OCR_Report.docx")
            
            os.remove(t.name)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# --- ၅။ Main Bot Execution ---
if __name__ == '__main__':
    # Flask ကို Background မှာ run ခြင်း
    threading.Thread(target=run_flask, daemon=True).start()
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        # Handler ကို မှန်ကန်စွာ ချိတ်ဆက်ခြင်း
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        print("--- Smart OCR Bot is LIVE ---")
        app.run_polling(drop_pending_updates=True)
