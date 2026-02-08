import os
import threading
import tempfile
import google.generativeai as genai
from huggingface_hub import InferenceClient
from openai import OpenAI
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# --- API Clients Setup ---
# 1. Grok (xAI) Setup
grok_key = os.environ.get("XAI_API_KEY") # Grok အတွက် key
grok_client = OpenAI(api_key=grok_key, base_url="https://api.x.ai/v1") if grok_key else None

# 2. DeepSeek Setup
deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
ds_client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com") if deepseek_key else None

# 3. Gemini Setup
genai_key = os.environ.get("GOOGLE_API_KEY")
if genai_key: genai.configure(api_key=genai_key)

# --- AI Core Functions ---

# Grok Chat Function
def get_grok_res(text):
    if not grok_client: return None
    try:
        response = grok_client.chat.completions.create(
            model="grok-beta", # သို့မဟုတ် grok-2
            messages=[{"role": "user", "content": text}]
        )
        return response.choices[0].message.content
    except: return None

# DeepSeek Chat Function
def get_deepseek_res(text):
    if not ds_client: return None
    try:
        response = ds_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": text}]
        )
        return response.choices[0].message.content
    except: return None

# Gemini Vision/Chat Fallback
def get_gemini_res(prompt, file_path=None):
    if not genai_key: return "Error: Gemini Key missing."
    model = genai.GenerativeModel('gemini-2.5-flash')
    if file_path:
        up_file = genai.upload_file(path=file_path)
        return model.generate_content([prompt, up_file]).text
    return model.generate_content(prompt).text

# --- Combined Logic (ဘယ်သူ့ကို အရင်သုံးမလဲ ရွေးချယ်မှု) ---
def get_ai_chat(text):
    # ၁။ DeepSeek ကို အရင်စမ်း
    res = get_deepseek_res(text)
    if res: return res
    
    # ၂။ DeepSeek မရရင် Grok ကို သုံး
    res = get_grok_res(text)
    if res: return res
    
    # ၃။ အားလုံးမရမှ Gemini နဲ့ ဖြေ
    return get_gemini_res(f"Reply in Myanmar: {text}")

# --- Telegram Handlers ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = get_ai_chat(update.message.text)
    await update.message.reply_text(res)

# (ကျန်တဲ့ handle_media, button_click နဲ့ Flask အပိုင်းတွေက အရင်အတိုင်းပဲ သုံးနိုင်ပါတယ်)
