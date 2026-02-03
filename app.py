import os
import threading
import tempfile
from groq import Groq
import google.generativeai as genai
from huggingface_hub import InferenceClient
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from io import BytesIO
from gtts import gTTS

# --- API Clients Setup ---
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
hf_client = InferenceClient(token=os.environ.get("HF_TOKEN"))

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Multi-AI Agent is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- ၁။ Text Chat Logic (Groq ကို သုံး၍ အလွန်မြန်စွာ ဖြေကြားခြင်း) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
    
    try:
        # Groq Llama-3 Model ကို သုံး၍ စာပြန်ခြင်း
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": f"Please reply in Myanmar language: {user_text}"}],
            model="llama3-8b-8192",
        )
        res = chat_completion.choices[0].message.content
        await update.message.reply_text(res)
    except Exception as e:
        # Groq အဆင်မပြေလျှင် Hugging Face သို့မဟုတ် Gemini ဖြင့် Backup လုပ်နိုင်သည်
        await update.message.reply_text("ခဏတာ အဆင်မပြေဖြစ်နေပါသည်။ နောက်မှ ပြန်ကြိုးစားကြည့်ပါ။")

# --- ၂။ Image/PDF Logic (Gemini ဖြင့် Vision Task လုပ်ခြင်း) ---
# (အရင်ပေးထားသည့် handle_media နှင့် button_click logic များကို ဆက်သုံးပါ)
# Gemini က ပုံဖတ်ရာတွင် အတော်ဆုံးဖြစ်သောကြောင့် File အတွက် Gemini ကို ထားခဲ့ခြင်းဖြစ်ပါသည်။

# --- ၃။ Hugging Face ကို သီးသန့် Task များအတွက် သုံးရန် (ဥပမာ - Sentiment Analysis) ---
def analyze_with_hf(text):
    # Hugging Face Model တစ်ခုခုကို လှမ်းသုံးခြင်း
    res = hf_client.text_classification(text, model="distilbert-base-uncased-finetuned-sst-2-english")
    return res
