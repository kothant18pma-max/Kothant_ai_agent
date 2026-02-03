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
from pptx import Presentation
from io import BytesIO
from gtts import gTTS

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Smart AI Agent with PPT Feature is Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- PowerPoint Creation Function ---
def create_ppt(text):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    title = slide.shapes.title
    body = slide.placeholders[1]
    
    title.text = "AI Data Summary"
    body.text = text[:1000] # အကျဉ်းချုပ်ကို Slide ထဲထည့်ခြင်း
    
    ppt_bio = BytesIO()
    prs.save(ppt_bio)
    ppt_bio.seek(0)
    return ppt_bio

# --- Smart AI Logic (Headers ဖြင့် ခိုင်းစေခြင်း) ---
def process_smart_ai(file_path):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    uploaded_file = genai.upload_file(path=file_path)
    
    prompt = """
    ဤဖိုင်ကို အောက်ပါ ခေါင်းစဉ်များအတိုင်း တိကျစွာ ခွဲခြားထုတ်ပေးပါ -
    [OCR]: ဖိုင်ထဲက စာသားအားလုံးကို တစ်လုံးမကျန် Transcription ထုတ်ပါ။
    [Myanmar_Summary]: အကြောင်းအရာအားလုံးကို မြန်မာလို အနှစ်ချုပ်ပါ။
    [English_Summary]: အကြောင်းအရာအားလုံးကို အင်္ဂလိပ်လို အနှစ်ချုပ်ပါ။
    [Presentation_Points]: Presentation Slide လုပ်ရန်အတွက် အဓိကအချက်များကို Bullet points များဖြင့် ရေးပေးပါ။
    [Tables]: ဇယားများပါက Markdown Table format ဖြင့် ထုတ်ပေးပါ။
    ဖတ်ရန်စာသား မရှိပါက 'DATA_INSUFFICIENT' ဟုသာ ရေးပါ။
    """
    response = model.generate_content([prompt, uploaded_file])
    return response.text

# --- (generate_audio နှင့် get_excel function များသည် မူလအတိုင်းဖြစ်သည်) ---
def generate_audio(text, lang='my'):
    try:
        tts = gTTS(text=text, lang=lang)
        bio = BytesIO(); tts.write_to_fp(bio); bio.seek(0)
        return bio
    except: return None

def get_excel(text):
    try:
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            df = pd.DataFrame(lines); bio = BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer: df.to_excel(writer, index=False, header=False)
            return bio.getvalue()
    except: return None

# --- Telegram Handler ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        file_obj = None; suffix = ""
        if update.message.document:
            file_obj = await update.message.document.get_file(); suffix = ".pdf"
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file(); suffix = ".jpg"
        
        if not file_obj: return

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            await file_obj.download_to_drive(t.name)
            res = process_smart_ai(t.name)
            
            if "DATA_INSUFFICIENT" in res:
                await update.message.reply_text("⚠️ ဖတ်ရန်စာသား မတွေ့ပါ။")
            else:
                for i in range(0, len(res), 4000): await update.message.reply_text(res[i:i+4000])
                
                # ၁။ Audio ပို့ခြင်း
                if "[Myanmar_Summary]:" in res:
                    my_v = generate_audio(res.split("[Myanmar_Summary]:")[1].split("[")[0].strip(), 'my')
                    if my_v: await update.message.reply_audio(audio=my_v, title="Myanmar Audio")
                
                # ၂။ Presentation ပို့ခြင်း
                if "[Presentation_Points]:" in res:
                    ppt_txt = res.split("[Presentation_Points]:")[1].split("[")[0].strip()
                    ppt_file = create_ppt(ppt_txt)
                    await update.message.reply_document(document=ppt_file, filename="Presentation.pptx", caption="Presentation Slide ထုတ်ပေးထားပါသည်။")
                
                # ၃။ Excel & Word ပို့ခြင်း
                ex = get_excel(res)
                if ex: await update.message.reply_document(document=BytesIO(ex), filename="Data.xlsx")
                doc_b = BytesIO(); doc = Document(); doc.add_paragraph(res); doc.save(doc_b)
                await update.message.reply_document(document=BytesIO(doc_b.getvalue()), filename="Report.docx")
            os.remove(t.name)
    except Exception as e: await update.message.reply_text(f"Error: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media))
        app.run_polling(drop_pending_updates=True)
