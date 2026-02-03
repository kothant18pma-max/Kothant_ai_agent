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

# --- ၁။ Flask Server (Render Health Check အတွက် အရေးကြီးဆုံး) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "AI Agent is Live and Healthy!"

def run_flask():
    # Render က ပေးတဲ့ Port ကို သုံးပါ (မရှိလျှင် 10000)
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- ၂။ AI Processing Functions (PDF, Image, Word, Excel) ---
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

def process_ai(file_path, is_image=False):
    llm = LLM(model="gemini/gemini-2.5-flash")
    if is_image:
        input_data = f"ဓာတ်ပုံဖိုင်: {file_path}"
        task_desc = "ဓာတ်ပုံထဲက စာသားများကိုဖတ်ပြီး အနှစ်ချုပ်ပါ။ ဇယားပါက Markdown Table ဖြင့်ထုတ်ပေးပါ။"
    else:
        loader = PyPDFLoader(file_path)
        input_data = "\n".join([p.page_content for p in loader.load()])
        task_desc = "PDF အချက်အလက်များကို အနှစ်ချုပ်ပါ။ ဇယားများကို Markdown Table format ဖြင့်ထုတ်ပေးပါ။"
    
    agent = Agent(role='Researcher', goal='Data Extraction', backstory='Expert Analyst', llm=llm)
    task = Task(description=f"{task_desc}\n\nData: {input_data}", expected_output="Summary and Tables", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

# --- ၃။ Telegram Handler Logic ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.mime_type == 'application/pdf':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ခဏစောင့်ပေးပါ... 📄")
        
        f = await context.bot.get_file(update.message.document.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            await f.download_to_drive(t.name)
            res = process_ai(t.name)
            
            # စာသားအပိုင်းလိုက်ပို့ခြင်း
            for i in range(0, len(res), 4000):
                await update.message.reply_text(res[i:i+4000])
            
            # File များပြန်ပို့ခြင်း
            doc_bio = BytesIO(); doc = Document(); doc.add_paragraph(res); doc.save(doc_bio)
            await update.message.reply_document(document=BytesIO(doc_bio.getvalue()), filename="Report.docx")
            
            ex = get_excel(res)
            if ex: await update.message.reply_document(document=BytesIO(ex), filename="Tables.xlsx")
            os.remove(t.name)

# --- ၄။ Main Execution Block ---
if __name__ == '__main__':
    # Flask ကို Background မှာ အရင်ဆုံးနှိုးပါ (Render Health Check အောင်မြင်ရန်)
    threading.Thread(target=run_flask, daemon=True).start()
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        # Bot ကို Polling စနစ်ဖြင့် Run ပါ
        application = ApplicationBuilder().token(token).build()
        application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        application.run_polling(drop_pending_updates=True)
