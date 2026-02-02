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

# --- ၁။ Flask Keep-Alive (Render အတွက်) ---
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Hybrid AI Agent is Running!"

def run_flask():
    try:
        flask_app.run(host='0.0.0.0', port=10000)
    except: pass

threading.Thread(target=run_flask, daemon=True).start()

# --- ၂။ AI Processing Function ---
def process_research(pdf_path):
    # gemini-1.5-flash ကို အသုံးပြုပါ (2.5 မရှိသေးပါ)
    llm = LLM(model="gemini/gemini-2.5-flash")
    loader = PyPDFLoader(pdf_path)
    content = "\n".join([p.page_content for p in loader.load()])
    
    agent = Agent(
        role='သုတေသန ပညာရှင်',
        goal='PDF ကို မြန်မာလို အနှစ်ချုပ်ရန်',
        backstory='သင်သည် စာရွက်စာတမ်းများကို ကျွမ်းကျင်စွာ အနှစ်ချုပ်ပေးသူဖြစ်သည်။',
        llm=llm
    )
    task = Task(description=f"ဤစာသားများကို မြန်မာလို အနှစ်ချုပ်ပါ: {content}", expected_output="မြန်မာလို အနှစ်ချုပ်။", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

def get_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- ၃။ Telegram Bot Logic ---
async def tg_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.mime_type == 'application/pdf':
        await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ခဏစောင့်ပေးပါ...")
        f = await context.bot.get_file(update.message.document.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
            await f.download_to_drive(t.name)
            res = process_research(t.name)
            await update.message.reply_text(f"🔍 ရလဒ်:\n\n{res}")
            await update.message.reply_document(document=BytesIO(get_docx(res)), filename="Report.docx")
            os.remove(t.name)

def start_bot():
    token = os.getenv("TELEGRAM_TOKEN")
    if token:
        bot = ApplicationBuilder().token(token).build()
        bot.add_handler(MessageHandler(filters.Document.PDF, tg_handle))
        bot.run_polling()

# Background မှာ Bot ကို နှိုးထားခြင်း
if "bot_on" not in st.session_state:
    threading.Thread(target=start_bot, daemon=True).start()
    st.session_state.bot_on = True

# --- ၄။ Streamlit Interface ---
st.title("🔍 Web + Telegram AI Agent")
key = st.sidebar.text_input("Gemini API Key", type="password")
if key: os.environ["GOOGLE_API_KEY"] = key

up = st.file_uploader("PDF တင်ပါ", type=["pdf"])
if up and key:
    if st.button("သုတေသန စတင်ပါ"):
        with st.spinner("Processing..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                t.write(up.getvalue())
                res = process_research(t.name)
                st.success("ပြီးပါပြီ!")
                st.write(res)
                st.download_button("📥 Word File", data=get_docx(res), file_name="report.docx")
                os.remove(t.name)

