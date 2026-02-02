import os
import threading
import tempfile
import streamlit as st
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from crewai import Agent, Task, Crew, LLM
from langchain_community.document_loaders import PyPDFLoader
from docx import Document
from io import BytesIO

# --- Flask Server for Render Keep-Alive ---
flask_app = Flask('')
@flask_app.route('/')
def home(): return "AI Agent is Running!"

def run_flask():
    try:
        # Render အတွက် Port 10000 က မပါမဖြစ်ပါ
        flask_app.run(host='0.0.0.0', port=10000)
    except: pass

threading.Thread(target=run_flask, daemon=True).start()

# --- Shared AI Function ---
def process_ai(pdf_path):
    llm = LLM(model="gemini/gemini-2.5-flash")
    loader = PyPDFLoader(pdf_path)
    content = "\n".join([p.page_content for p in loader.load()])
    
    agent = Agent(
        role='သုတေသန ပညာရှင်',
        goal='PDF ကို မြန်မာလို အနှစ်ချုပ်ရန်',
        backstory='သင်သည် စာရွက်စာတမ်းများကို ကျွမ်းကျင်စွာ အနှစ်ချုပ်ပေးသူဖြစ်သည်။',
        llm=llm
    )
    task = Task(description=f"အနှစ်ချုပ်ပါ: {content}", expected_output="မြန်မာလို အနှစ်ချုပ်။", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

def get_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- Telegram Bot Logic ---
async def tg_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.mime_type == 'application/pdf':
        await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ခဏစောင့်ပေးပါ...")
        f = await context.bot.get_file(update.message.document.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            await f.download_to_drive(t.name)
            res = process_ai(t.name)
            await update.message.reply_text(f"🔍 ရလဒ်:\n\n{res}")
            await update.message.reply_document(document=BytesIO(get_docx(res)), filename="Report.docx")
            os.remove(t.name)

if __name__ == '__main__':
    # ၁။ Token ကို သေချာစစ်ဆေးပါ
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        print("CRITICAL ERROR: TELEGRAM_TOKEN is missing in Environment Variables!")
    else:
        # ၂။ Application ကို တည်ဆောက်ပါ
        application = ApplicationBuilder().token(token).build()
        
        # စာသားများကို အပိုင်းလိုက်ခွဲပို့ရန် function
async def send_long_message(update, text):
    if len(text) <= 4000:
        await update.message.reply_text(text)
    else:
        # စာလုံးရေ ၄၀၀၀ စီ ခွဲထုတ်ပြီး ပို့ပေးခြင်း
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])

# သင့်ရဲ့ မူလ handler ကို ဒီလို ပြင်လိုက်ပါ
async def tg_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document and update.message.document.mime_type == 'application/pdf':
            await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ခဏစောင့်ပေးပါ...")
            
            f = await context.bot.get_file(update.message.document.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                await f.download_to_drive(t.name)
                res = process_ai(t.name) # AI processing လုပ်တဲ့နေရာ
                
                # အနှစ်ချုပ်စာသားကို ခွဲပို့မည်
                await update.message.reply_text("🔍 သုတေသန အနှစ်ချုပ် ရလဒ် -")
                await send_long_message(update, res)
                
                # Word file ပြန်ပို့ခြင်း (Word file ကတော့ Message long ဖြစ်လည်း ပြဿနာမရှိပါ)
                docx_data = get_docx(res)
                await update.message.reply_document(
                    document=BytesIO(docx_data), 
                    filename="AI_Research_Report.docx"
                )
                os.remove(t.name)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
        
        # ၄။ ပိုမိုမြန်ဆန်စွာ အလုပ်လုပ်စေရန် polling ကို run ပါ
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    # Environment variable ကို ဖတ်ပါ
    token = os.environ.get("TELEGRAM_TOKEN")
    
    if token is None or token == "":
        print("CRITICAL ERROR: TELEGRAM_TOKEN is missing in Environment Variables!")
        # Flask server သာ Run ထားပြီး Bot ကို မနှိုးပါနဲ့
    else:
        print(f"Token found: {token[:5]}***") # Token ရှိကြောင်း အတည်ပြုရန် (လုံခြုံရေးအရ အရှေ့ ၅ လုံးပဲပြပါမည်)
        application = ApplicationBuilder().token(token).build()
        application.add_handler(MessageHandler(filters.Document.PDF, tg_msg))
        
        print("--- Bot is now LIVE and Polling ---")
        application.run_polling(drop_pending_updates=True)

# --- Streamlit UI ---
st.title("🔍 Web + Telegram AI Agent")
key = st.sidebar.text_input("Gemini API Key", type="password")
if key: os.environ["GOOGLE_API_KEY"] = key

up = st.file_uploader("PDF တင်ပါ", type=["pdf"])
if up and key:
    if st.button("သုတေသန စတင်ပါ"):
        with st.spinner("Processing..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                t.write(up.getvalue())
                res = process_ai(t.name)
                st.success("ပြီးပါပြီ!")
                st.write(res)
                st.download_button("📥 Word File", data=get_docx(res), file_name="report.docx")
                os.remove(t.name)



