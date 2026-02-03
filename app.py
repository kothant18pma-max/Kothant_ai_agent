import os
import threading
import tempfile
import pandas as pd
from flask import Flask
from telegram import Update
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from crewai import Agent, Task, Crew, LLM
from langchain_community.document_loaders import PyPDFLoader
from docx import Document
from io import BytesIO

# --- Flask Server (Render Health Check) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is Healthy!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

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

# --- AI Function (Updated for Image) ---
def process_ai(file_path, is_image=False):
    llm = LLM(model="gemini/gemini-2.5-flash")
    
    if is_image:
        # Gemini က ပုံကို တိုက်ရိုက်ဖတ်နိုင်ရန် input format ပြင်ဆင်ခြင်း
        input_data = f"ဓာတ်ပုံဖိုင်လမ်းကြောင်း: {file_path}"
        task_desc = "ဓာတ်ပုံထဲက စာသားများကို ဖတ်ပြီး မြန်မာလို အနှစ်ချုပ်ပါ။ ဇယားပါလျှင် Markdown Table ဖြင့် ထုတ်ပေးပါ။"
    else:
        loader = PyPDFLoader(file_path)
        input_data = "\n".join([p.page_content for p in loader.load()])
        task_desc = "PDF အချက်အလက်များကို မြန်မာလို အနှစ်ချုပ်ပါ။ ဇယားများကို Markdown Table format ဖြင့် သေချာစွာ ထုတ်ပေးပါ။"
    
    agent = Agent(role='Researcher', goal='Data Extraction', backstory='Expert Analyst', llm=llm)
    task = Task(description=f"{task_desc}\n\nData Content: {input_data}", expected_output="Summary and Tables", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

# --- Telegram PDF Handler ---
async def tg_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        await update.message.reply_text("PDF ဖတ်နေပါသည်... 📄")
        f = await context.bot.get_file(update.message.document.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            await f.download_to_drive(t.name)
            res = process_ai(t.name, is_image=False)
            for i in range(0, len(res), 4000): await update.message.reply_text(res[i:i+4000])
            ex = get_excel(res)
            if ex: await update.message.reply_document(document=BytesIO(ex), filename="Data.xlsx")
            os.remove(t.name)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

# --- Telegram Image Handler (JPEG/PNG အတွက် အသစ်) ---
async def tg_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        await update.message.reply_text("ပုံထဲက စာသားများကို ဖတ်နေပါသည်... 📷")
        # Telegram က ပုံကို အကြီးဆုံး size ဖြင့် ယူခြင်း
        photo_file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t:
            await photo_file.download_to_drive(t.name)
            res = process_ai(t.name, is_image=True)
            for i in range(0, len(res), 4000): await update.message.reply_text(res[i:i+4000])
            ex = get_excel(res)
            if ex: await update.message.reply_document(document=BytesIO(ex), filename="Image_Data.xlsx")
            os.remove(t.name)
    except Exception as e: await update.message.reply_text(f"Error: {e}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        application = ApplicationBuilder().token(token).build()
        # Handler နှစ်ခုစလုံးကို ထည့်သွင်းခြင်း
        application.add_handler(MessageHandler(filters.Document.PDF, tg_pdf))
        application.add_handler(MessageHandler(filters.PHOTO, tg_img))
        print("Bot started with Image and PDF support...")
        application.run_polling(drop_pending_updates=True)
