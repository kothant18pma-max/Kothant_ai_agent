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
from gtts import gTTS

# --- ၁။ Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "AI Agent is Live with Audio Feature!"

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
       - [OCR]: စာသားအားလုံးကို တစ်လုံးမကျန် Transcription ထုတ်ပါ။
       - [Myanmar_Summary]: မြန်မာလို အနှစ်ချုပ်ပေးပါ။
       - [English_Summary]: အင်္ဂလိပ်လို အနှစ်ချုပ်ပေးပါ။
       - [Tables]: ဇယားများပါက Markdown Table format (| Col |) ဖြင့် ထုတ်ပေးပါ။
    """
    response = model.generate_content([prompt, uploaded_file])
    return response.text

# --- ၃။ Audio Generation Function ---
def generate_audio(text, lang='my'):
    try:
        tts = gTTS(text=text, lang=lang)
        audio_bio = BytesIO()
        tts.write_to_fp(audio_bio)
        audio_bio.seek(0)
        return audio_bio
    except: return None

# --- ၄။ Excel Conversion ---
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

# --- ၅။ Telegram Handler ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        
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
                # စာသားရလဒ် ပို့ခြင်း
                for i in range(0, len(res), 4000):
                    await update.message.reply_text(res[i:i+4000])
                
                # --- Audio Feature Section ---
                # မြန်မာ အနှစ်ချုပ်ကို ရှာပြီး အသံထုတ်ခြင်း
                if "[Myanmar_Summary]:" in res:
                    my_text = res.split("[Myanmar_Summary]:")[1].split("[")[0].strip()
                    my_voice = generate_audio(my_text, lang='my')
                    if my_voice:
                        await update.message.reply_audio(audio=my_voice, filename="Myanmar.mp3", title="Myanmar Audio")
                
                # အင်္ဂလိပ် အနှစ်ချုပ်ကို ရှာပြီး အသံထုတ်ခြင်း
                if "[English_Summary]:" in res:
                    en_text = res.split("[English_Summary]:")[1].split("[")[0].strip()
                    en_voice = generate_audio(en_text, lang='en')
                    if en_voice:
                        await update.message.reply_audio(audio=en_voice, filename="English.mp3", title="English Audio")

                # Excel & Word Files
                ex = get_excel(res)
                if ex: await update.message.reply_document(document=BytesIO(ex), filename="Table_Data.xlsx")
                
                doc_bio = BytesIO(); doc = Document(); doc.add_paragraph(res); doc.save(doc_bio)
                await update.message.reply_document(document=BytesIO(doc_bio.getvalue()), filename="OCR_Report.docx")
            
            os.remove(t.name)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# --- ၆။ Main Bot Execution ---
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        print("--- Smart OCR Bot with Audio is LIVE ---")
        app.run_polling(drop_pending_updates=True)

