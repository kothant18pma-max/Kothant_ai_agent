import os
import threading
import tempfile
import streamlit as st
import telegram.constants
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
        flask_app.run(host='0.0.0.0', port=10000)
    except: pass

threading.Thread(target=run_flask, daemon=True).start()

# --- Shared AI Function ---
def process_ai(file_path, is_image=False):
    # Gemini 1.5 Flash သို့မဟုတ် 2.0 Flash ကို သုံးပါ (2.5 မရှိသေးပါ)
    llm = LLM(model="gemini/gemini-2.5-flash")
    
    if is_image:
        content_desc = "ဓာတ်ပုံထဲက စာသားများကို ဖတ်ပြီး မြန်မာလို အနှစ်ချုပ်ပေးပါ"
        # Gemini Multimodal ဖြစ်၍ ပုံကို တိုက်ရိုက်ယူနိုင်ရန် CrewAI Tool လိုအပ်နိုင်သော်လည်း 
        # ဤနေရာတွင် ရိုးရှင်းအောင် စာသားဖြင့်သာ ဖော်ပြထားသည်
        input_data = f"ဓာတ်ပုံဖိုင်လမ်းကြောင်း: {file_path}" 
    else:
        loader = PyPDFLoader(file_path)
        input_data = "\n".join([p.page_content for p in loader.load()])
    
    agent = Agent(
        role='ကျွမ်းကျင်သုတေသနပညာရှင်',
        goal='စာရွက်စာတမ်းနှင့် ပုံများကို မြန်မာလို အနှစ်ချုပ်ရန်',
        backstory='သင်သည် PDF နှင့် ဓာတ်ပုံများထဲက အချက်အလက်များကို မြန်မာလို ကျွမ်းကျင်စွာ ဘာသာပြန်ဆို အနှစ်ချုပ်ပေးသူဖြစ်သည်။',
        llm=llm
    )
    task = Task(description=f"အောက်ပါအချက်အလက်များကို မြန်မာလို အနှစ်ချုပ်ပါ: {input_data}", expected_output="မြန်မာလို စနစ်တကျ အနှစ်ချုပ်။", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

def get_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- Telegram Long Message Fix ---
async def send_long_message(update, text):
    if len(text) <= 4000:
        await update.message.reply_text(text)
    else:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])

# --- Telegram PDF Handler ---
async def tg_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document and update.message.document.mime_type == 'application/pdf':
            # Typing Action ပြခြင်း
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
            await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ခဏစောင့်ပေးပါ... 📄")
            
            f = await context.bot.get_file(update.message.document.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                await f.download_to_drive(t.name)
                res = process_ai(t.name, is_image=False)
                
                await update.message.reply_text("🔍 PDF အနှစ်ချုပ် ရလဒ် -")
                await send_long_message(update, res)
                await update.message.reply_document(document=BytesIO(get_docx(res)), filename="Research_Report.docx")
                os.remove(t.name)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# --- Telegram Image Handler ---
async def tg_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Typing Action ပြခြင်း
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        await update.message.reply_text("ပုံကို လက်ခံရရှိပါပြီ။ စာသားများကို ဖတ်နေပါသည်... 📷")
        
        photo_file = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t:
            await photo_file.download_to_drive(t.name)
            res = process_ai(t.name, is_image=True)
            
            await update.message.reply_text("🔍 ပုံထဲက တွေ့ရှိချက် -")
            await send_long_message(update, res)
            os.remove(t.name)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# --- Main Bot Execution ---
if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_TOKEN")
    
    if token:
        application = ApplicationBuilder().token(token).build()
        
        # Handler များ ထည့်သွင်းခြင်း
        application.add_handler(MessageHandler(filters.Document.PDF, tg_pdf))
        application.add_handler(MessageHandler(filters.PHOTO, tg_image))
        
        # Bot ကို Background မှာ Run ရန် Thread သုံးခြင်း (Streamlit နှင့် တွဲသုံးရန်)
        def start_polling():
            application.run_polling(drop_pending_updates=True)
        
        threading.Thread(target=start_polling, daemon=True).start()
        print("--- Bot is now LIVE with Image & PDF Support ---")

# --- Streamlit UI ---
st.set_page_config(page_title="AI Research Agent", page_icon="🔍")
st.title("🔍 Web + Telegram AI Agent")
st.info("Telegram Bot တွင်လည်း PDF နှင့် ပုံများ ပို့နိုင်ပါသည်။")

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
