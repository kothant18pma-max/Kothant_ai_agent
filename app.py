import os
import threading
import tempfile
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from crewai import Agent, Task, Crew, LLM
from langchain_community.document_loaders import PyPDFLoader
from docx import Document
from io import BytesIO

# --- ၁။ Flask Keep-Alive (Render အတွက်) ---
app = Flask('')

@app.route('/')
def home():
    return "AI Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask, daemon=True).start()

# --- ၂။ Word File Function ---
def create_word_file(content):
    doc = Document()
    doc.add_heading('AI Research Report', 0)
    doc.add_paragraph(content)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- ၃။ Telegram Bot Logic ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.mime_type == 'application/pdf':
        await update.message.reply_text("PDF ဖိုင် ရပါပြီ။ သုတေသန လုပ်နေပါပြီ...")
        
        file = await context.bot.get_file(update.message.document.file_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            await file.download_to_drive(tmp.name)
            
            # AI Processing
            loader = PyPDFLoader(tmp.name)
            pdf_content = "\n".join([p.page_content for p in loader.load()])
            
            # Gemini LLM Setup (gemini-1.5-flash ကို သုံးပါ)
            gemini_llm = LLM(model="gemini/gemini-2.5-flash")
            
            researcher = Agent(
                role='ဝါရင့် သုတေသီ',
                goal='PDF အချက်အလက်များကို မြန်မာလို အနှစ်ချုပ်ရန်',
                backstory='သင်သည် တိကျသော အစီရင်ခံစာများ ရေးသားသူဖြစ်သည်။',
                llm=gemini_llm
            )
            
            task = Task(
                description=f"အောက်ပါစာသားများကို မြန်မာလို အနှစ်ချုပ်ပါ: {pdf_content}",
                expected_output="ပြည့်စုံသော မြန်မာလို သုတေသန အစီရင်ခံစာ။",
                agent=researcher
            )
            
            crew = Crew(agents=[researcher], tasks=[task])
            result = crew.kickoff()
            
            # စာသားပြန်ပို့ခြင်း
            summary_text = str(result.raw)
            await update.message.reply_text(f"🔍 ရလဒ်:\n\n{summary_text}")
            
            # Word File ပြန်ပို့ခြင်း
            docx_data = create_word_file(summary_text)
            await update.message.reply_document(
                document=BytesIO(docx_data),
                filename="Research_Report.docx"
            )
            
            os.remove(tmp.name)
    else:
        await update.message.reply_text("PDF ဖိုင်ကိုသာ ပို့ပေးပါ။")

# --- ၄။ Main Execution ---
if __name__ == '__main__':
    # Render Environment Variables ထဲက Key တွေကို ယူပါ
    token = os.getenv("TELEGRAM_TOKEN")
    
    if not token:
        print("Error: TELEGRAM_TOKEN not found!")
    else:
        app_bot = ApplicationBuilder().token(token).build()
        app_bot.add_handler(MessageHandler(filters.Document.PDF, handle_document))
        
        print("Bot is starting...")
        app_bot.run_polling()

