import os
import threading
import tempfile
import streamlit as st
import telegram.constants
import pandas as pd
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

# --- Excel Conversion Function ---
def get_excel(text):
    try:
        # AI ထုတ်ပေးတဲ့ Markdown Table (| Col1 | Col2 |) ကို ရှာဖွေပြီး Excel ပြောင်းခြင်း
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            df = pd.DataFrame(lines)
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, header=False)
            return bio.getvalue()
    except: return None
    return None

# --- Shared AI Function (PDF & Image) ---
def process_ai(file_path, is_image=False):
    llm = LLM(model="gemini/gemini-2.5-flash")
    
    if is_image:
        input_data = f"ဓာတ်ပုံဖိုင်: {file_path}"
        task_desc = "ဓာတ်ပုံထဲက စာသားများကို ဖတ်ပြီး အနှစ်ချုပ်ပါ။ ဇယားများပါလျှင် Markdown Table ဖြင့် ထုတ်ပေးပါ။"
    else:
        loader = PyPDFLoader(file_path)
        input_data = "\n".join([p.page_content for p in loader.load()])
        task_desc = "PDF ထဲက အချက်အလက်များကို အနှစ်ချုပ်ပါ။ ဇယားများပါလျှင် Markdown Table format (| Column |) ဖြင့် သေချာစွာ ထုတ်ပေးပါ။"
    
    agent = Agent(
        role='Data & Research Expert',
        goal='စာရွက်စာတမ်းများနှင့် ပုံများထဲက အချက်အလက်နှင့် ဇယားများကို တိကျစွာ ထုတ်ယူရန်',
        backstory='သင်သည် PDF နှင့် ဓာတ်ပုံများမှ Data များကို Excel ပုံစံအတိုင်း ပြန်လည်ထုတ်ယူပေးနိုင်သော ပညာရှင်ဖြစ်သည်။',
        llm=llm
    )
    task = Task(description=f"{task_desc}\n\nအချက်အလက်များ: {input_data}", expected_output="မြန်မာလို အနှစ်ချုပ်နှင့် ဇယားကွက်များ။", agent=agent)
    return str(Crew(agents=[agent], tasks=[task]).kickoff().raw)

def get_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

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
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
            await update.message.reply_text("PDF လက်ခံရရှိပါပြီ။ ဇယားကွက်များနှင့် အချက်အလက်များကို ရှာဖွေနေပါသည်... 📄")
            
            f = await context.bot.get_file(update.message.document.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                await f.download_to_drive(t.name)
                res = process_ai(t.name, is_image=False)
                
                await send_long_message(update, f"🔍 ရလဒ်:\n\n{res}")
                
                # Word File ပို့ခြင်း
                await update.message.reply_document(document=BytesIO(get_docx(res)), filename="Summary.docx")
                
                # Excel File ပို့ခြင်း (ဇယားပါလျှင်)
                excel_data = get_excel(res)
                if excel_data:
                    await update.message.reply_document(document=BytesIO(excel_data), filename="Tables.xlsx", caption="ဇယားကွက်များကို Excel အဖြစ် ထုတ်ပေးထားပါသည်။")
                
                os.remove(t.name)
    except Exception as e: await update.message.reply_text(f"Error: {str(e)}")

# --- Telegram Image Handler ---
async def tg_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        await update.message.reply_text("ပုံကို လက်ခံရရှိပါပြီ။ စာသားများနှင့် ဇယားများကို ဖတ်နေပါသည်... 📷")
        
        photo = await update.message.photo[-1].get_file()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t:
            await photo.download_to_drive(t.name)
            res = process_ai(t.name, is_image=True)
            await send_long_message(update, f"📷 ပုံထဲက တွေ့ရှိချက်:\n\n{res}")
            
            excel_data = get_excel(res)
            if excel_data:
                await update.message.reply_document(document=BytesIO(excel_data), filename="Image_Table.xlsx")
            os.remove(t.name)
    except Exception as e: await update.message.reply_text(f"Error: {str(e)}")

# --- Run Bot ---
if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_TOKEN")
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.Document.PDF, tg_pdf))
        app.add_handler(MessageHandler(filters.PHOTO, tg_img))
        threading.Thread(target=app.run_polling, kwargs={"drop_pending_updates": True}, daemon=True).start()

# --- Streamlit UI ---
st.title("🔍 Web + Telegram AI Data Agent")
st.markdown("PDF နှင့် ပုံများမှ **မြန်မာလိုအနှစ်ချုပ်၊ Word နှင့် Excel** တို့ကို တစ်ခါတည်း ထုတ်ပေးပါသည်။")

key = st.sidebar.text_input("Gemini API Key", type="password")
if key:
    os.environ["GOOGLE_API_KEY"] = key
    up = st.file_uploader("PDF တင်ပါ", type=["pdf"])
    if up and st.button("သုတေသန စတင်ပါ"):
        with st.spinner("ဇယားများနှင့် အချက်အလက်များကို ထုတ်ယူနေသည်..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as t:
                t.write(up.getvalue())
                res = process_ai(t.name)
                st.success("ပြီးပါပြီ!")
                st.write(res)
                st.download_button("📥 Word Report", data=get_docx(res), file_name="report.docx")
                excel = get_excel(res)
                if excel: st.download_button("📊 Excel Tables", data=excel, file_name="tables.xlsx")
                os.remove(t.name)
