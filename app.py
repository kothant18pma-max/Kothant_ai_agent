import os
import threading
import tempfile
import pandas as pd
import google.generativeai as genai
from groq import Groq
from huggingface_hub import InferenceClient
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import telegram.constants
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from docx import Document
from pptx import Presentation
from pptx.util import Inches, Pt
from io import BytesIO
from gtts import gTTS
import base64

# --- Environment Variables ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
HF_API_KEY = os.environ.get("HF_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# --- Configure APIs ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
hf_client = InferenceClient(token=HF_API_KEY) if HF_API_KEY else None

# --- Default AI Provider ---
DEFAULT_PROVIDER = "gemini"  # Options: gemini, groq, huggingface

# --- Flask Server (Render Health Check) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Multi-AI Agent is Active!"

@flask_app.route('/health')
def health():
    return {
        "status": "healthy",
        "providers": {
            "gemini": bool(GOOGLE_API_KEY),
            "groq": bool(GROQ_API_KEY),
            "huggingface": bool(HF_API_KEY)
        }
    }

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# ============================================================
# 🧠 AI PROVIDER FUNCTIONS
# ============================================================

# --- 1️⃣ Google Gemini ---
def gemini_response(prompt_text, file_path=None):
    """Google Gemini API for text and multimodal"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        if file_path:
            uploaded_file = genai.upload_file(path=file_path)
            response = model.generate_content([prompt_text, uploaded_file])
        else:
            response = model.generate_content(prompt_text)
        
        return response.text
    except Exception as e:
        return f"❌ Gemini Error: {str(e)}"

# --- 2️⃣ Groq (Ultra Fast - Llama, Mixtral) ---
def groq_response(prompt_text, model_name="llama-3.3-70b-versatile"):
    """Groq API for ultra-fast inference"""
    try:
        if not groq_client:
            return "❌ Groq API Key မရှိပါ။"
        
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Respond in Myanmar language when the user writes in Myanmar."
                },
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            model=model_name,
            temperature=0.7,
            max_tokens=4096,
        )
        
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Groq Error: {str(e)}"

# --- 3️⃣ Hugging Face ---
def huggingface_response(prompt_text, model_name="meta-llama/Llama-3.2-11B-Vision-Instruct"):
    """Hugging Face Inference API"""
    try:
        if not hf_client:
            return "❌ Hugging Face API Key မရှိပါ။"
        
        response = hf_client.text_generation(
            prompt=prompt_text,
            model=model_name,
            max_new_tokens=2048,
            temperature=0.7,
        )
        
        return response
    except Exception as e:
        return f"❌ Hugging Face Error: {str(e)}"

# --- Hugging Face Image Analysis ---
def huggingface_image_analysis(image_path, prompt="Describe this image in detail"):
    """Hugging Face Vision Model"""
    try:
        if not hf_client:
            return "❌ Hugging Face API Key မရှိပါ။"
        
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Using Llama Vision model
        response = hf_client.image_to_text(
            image=image_data,
            model="Salesforce/blip-image-captioning-large"
        )
        
        return response
    except Exception as e:
        return f"❌ HF Image Error: {str(e)}"

# --- Hugging Face Audio Transcription ---
def huggingface_audio_transcribe(audio_path):
    """Hugging Face Whisper for audio transcription"""
    try:
        if not hf_client:
            return "❌ Hugging Face API Key မရှိပါ။"
        
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        
        response = hf_client.automatic_speech_recognition(
            audio=audio_data,
            model="openai/whisper-large-v3"
        )
        
        return response["text"]
    except Exception as e:
        return f"❌ HF Audio Error: {str(e)}"

# ============================================================
# 🔄 UNIFIED AI FUNCTION (Auto-Select Provider)
# ============================================================

def get_ai_response(prompt_text, file_path=None, provider=None):
    """
    Unified AI response function with provider selection
    Supports: gemini, groq, huggingface
    """
    # Use user's preference or default
    selected_provider = provider or DEFAULT_PROVIDER
    
    # For file processing, Gemini is preferred (multimodal support)
    if file_path:
        return gemini_response(prompt_text, file_path)
    
    # Text-only responses
    if selected_provider == "gemini":
        return gemini_response(prompt_text)
    elif selected_provider == "groq":
        return groq_response(prompt_text)
    elif selected_provider == "huggingface":
        return huggingface_response(prompt_text)
    else:
        # Fallback chain: Groq → Gemini → HuggingFace
        if GROQ_API_KEY:
            result = groq_response(prompt_text)
            if not result.startswith("❌"):
                return result
        if GOOGLE_API_KEY:
            result = gemini_response(prompt_text)
            if not result.startswith("❌"):
                return result
        if HF_API_KEY:
            return huggingface_response(prompt_text)
        
        return "❌ No AI provider available. Please set API keys."

# ============================================================
# 📁 HELPER FUNCTIONS
# ============================================================

def create_ppt(text):
    """Create PowerPoint presentation"""
    prs = Presentation()
    
    # Title slide
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = "AI Summary Report"
    title_slide.placeholders[1].text = "Generated by AI Agent"
    
    # Content slides (split by paragraphs)
    paragraphs = text.split('\n\n')
    for i, para in enumerate(paragraphs[:10]):  # Max 10 slides
        if para.strip():
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = f"Section {i+1}"
            slide.placeholders[1].text = para[:500]
    
    bio = BytesIO()
    prs.save(bio)
    bio.seek(0)
    return bio

def get_excel(text):
    """Extract tables from text and create Excel"""
    try:
        lines = [line.strip().strip('|').split('|') for line in text.split('\n') if '|' in line]
        if len(lines) > 1:
            # Clean data
            cleaned = [[cell.strip() for cell in line if cell.strip()] for line in lines]
            cleaned = [line for line in cleaned if line and not all('-' in c for c in line)]
            
            if len(cleaned) > 1:
                df = pd.DataFrame(cleaned[1:], columns=cleaned[0])
                bio = BytesIO()
                with pd.ExcelWriter(bio, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                bio.seek(0)
                return bio.getvalue()
    except Exception as e:
        print(f"Excel Error: {e}")
    return None

def create_word_doc(text, title="AI Report"):
    """Create Word document"""
    try:
        doc = Document()
        doc.add_heading(title, 0)
        
        for para in text.split('\n'):
            if para.strip():
                doc.add_paragraph(para)
        
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except:
        return None

# ============================================================
# 🤖 TELEGRAM HANDLERS
# ============================================================

# --- /start Command ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Set default provider
    context.user_data['provider'] = DEFAULT_PROVIDER
    
    welcome = """
🤖 *Multi-AI Document Assistant*

🌟 *Available AI Providers:*
• 🔵 Gemini (Google) - Multimodal
• 🟢 Groq (Llama 3.3) - Ultra Fast
• 🟡 Hugging Face - Open Source

📋 *Commands:*
/start - ပြန်စတင်ရန်
/provider - AI Provider ရွေးရန်
/models - Available Models ကြည့်ရန်

📁 *Supported Files:*
PDF, Images, Audio, Documents

💬 စာသား ပို့ပြီး တိုက်ရိုက် စကားပြောနိုင်ပါတယ်!
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

# --- /provider Command ---
async def provider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔵 Gemini (Multimodal)", callback_data='set_gemini')],
        [InlineKeyboardButton("🟢 Groq (Ultra Fast)", callback_data='set_groq')],
        [InlineKeyboardButton("🟡 Hugging Face (Open Source)", callback_data='set_huggingface')],
        [InlineKeyboardButton("🔄 Auto (Fallback Chain)", callback_data='set_auto')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current = context.user_data.get('provider', DEFAULT_PROVIDER)
    await update.message.reply_text(
        f"🎛️ *AI Provider ရွေးချယ်ပါ*\n\nလက်ရှိ: `{current.upper()}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- /models Command ---
async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models_info = """
🧠 *Available Models:*

🔵 *Gemini:*
• gemini-2.0-flash (Default)
• gemini-1.5-pro
• gemini-1.5-flash

🟢 *Groq:*
• llama-3.3-70b-versatile (Default)
• llama-3.1-8b-instant
• mixtral-8x7b-32768
• gemma2-9b-it

🟡 *Hugging Face:*
• meta-llama/Llama-3.2-11B-Vision-Instruct
• mistralai/Mixtral-8x7B-Instruct-v0.1
• openai/whisper-large-v3 (Audio)
• Salesforce/blip-image-captioning-large (Image)
    """
    await update.message.reply_text(models_info, parse_mode='Markdown')

# --- Text Message Handler ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    provider = context.user_data.get('provider', DEFAULT_PROVIDER)
    
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action=telegram.constants.ChatAction.TYPING
    )
    
    prompt = f"""အသုံးပြုသူမှ မေးမြန်းချက်: {user_text}
    
(မြန်မာလို ယဉ်ကျေးစွာ ပြန်လည်ဖြေကြားပေးပါ။ အကယ်၍ English ဖြင့် မေးပါက English ဖြင့် ဖြေပါ။)"""
    
    res = get_ai_response(prompt, provider=provider)
    
    # Send in chunks if too long
    for i in range(0, len(res), 4000):
        await update.message.reply_text(res[i:i+4000])

# --- Media Handler (Files & Photos) ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_obj = None
    suffix = ""
    file_type = "document"
    
    if update.message.document:
        doc = update.message.document
        file_obj = await doc.get_file()
        
        # Determine file type
        if doc.mime_type == 'application/pdf':
            suffix = ".pdf"
            file_type = "pdf"
        elif doc.mime_type in ['audio/mpeg', 'audio/wav', 'audio/ogg']:
            suffix = ".mp3"
            file_type = "audio"
        elif doc.mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            suffix = ".docx"
            file_type = "word"
        else:
            suffix = ".bin"
    
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        suffix = ".jpg"
        file_type = "image"
    
    elif update.message.voice:
        file_obj = await update.message.voice.get_file()
        suffix = ".ogg"
        file_type = "audio"
    
    elif update.message.audio:
        file_obj = await update.message.audio.get_file()
        suffix = ".mp3"
        file_type = "audio"
    
    if not file_obj:
        await update.message.reply_text("❌ ဖိုင်အမျိုးအစား မသိရပါ။")
        return

    # Download and save file
    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file_obj.download_to_drive(t.name)
    context.user_data['current_file'] = t.name
    context.user_data['file_type'] = file_type
    
    # Show service options based on file type
    if file_type == "audio":
        keyboard = [
            [InlineKeyboardButton("🎤 Transcribe (စာသားပြောင်း)", callback_data='transcribe')],
            [InlineKeyboardButton("📝 Summarize", callback_data='summary_audio')]
        ]
    elif file_type == "image":
        keyboard = [
            [InlineKeyboardButton("🔍 OCR (စာကူးမယ်)", callback_data='ocr')],
            [InlineKeyboardButton("🖼️ Image Analysis", callback_data='analyze_image')],
            [InlineKeyboardButton("📊 Extract Table", callback_data='excel')]
        ]
    else:  # PDF, documents
        keyboard = [
            [InlineKeyboardButton("🔍 OCR (စာကူးမယ်)", callback_data='ocr'),
             InlineKeyboardButton("📝 အနှစ်ချုပ်", callback_data='summary')],
            [InlineKeyboardButton("📊 Excel ထုတ်မယ်", callback_data='excel'),
             InlineKeyboardButton("📽️ PPT လုပ်မယ်", callback_data='ppt')],
            [InlineKeyboardButton("📄 Word Doc ထုတ်မယ်", callback_data='word'),
             InlineKeyboardButton("🔊 Audio Summary", callback_data='audio')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"📁 *{file_type.upper()}* ဖိုင်ကို လက်ခံရရှိပါပြီ။\n\nဘယ် Service ကို သုံးချင်ပါသလဲ?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# --- Callback Handler (Button Clicks) ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    command = query.data
    chat_id = query.message.chat_id
    
    # --- Provider Selection ---
    if command.startswith('set_'):
        provider = command.replace('set_', '')
        context.user_data['provider'] = provider
        
        provider_names = {
            'gemini': '🔵 Google Gemini',
            'groq': '🟢 Groq (Llama 3.3)',
            'huggingface': '🟡 Hugging Face',
            'auto': '🔄 Auto Fallback'
        }
        
        await query.edit_message_text(f"✅ AI Provider ကို *{provider_names.get(provider, provider)}* သို့ ပြောင်းလိုက်ပါပြီ!", parse_mode='Markdown')
        return
    
    # --- File Processing ---
    file_path = context.user_data.get('current_file')
    file_type = context.user_data.get('file_type', 'document')
    provider = context.user_data.get('provider', DEFAULT_PROVIDER)
    
    if not file_path or not os.path.exists(file_path):
        await query.edit_message_text("❌ ဖိုင်သက်တမ်းကုန်သွားပါပြီ။ ကျေးဇူးပြု၍ ပြန်ပို့ပေးပါ။")
        return

    await query.edit_message_text(f"⚙️ *{command.upper()}* လုပ်ဆောင်နေပါသည်... ⏳", parse_mode='Markdown')
    
    try:
        # --- Audio Transcription (Hugging Face Whisper) ---
        if command == 'transcribe':
            if HF_API_KEY:
                res = huggingface_audio_transcribe(file_path)
            else:
                res = get_ai_response("Transcribe this audio file.", file_path)
            await context.bot.send_message(chat_id=chat_id, text=f"🎤 *Transcription:*\n\n{res}", parse_mode='Markdown')
        
        # --- Image Analysis ---
        elif command == 'analyze_image':
            res = get_ai_response("Describe this image in detail. Include any text visible.", file_path)
            await context.bot.send_message(chat_id=chat_id, text=f"🖼️ *Image Analysis:*\n\n{res}", parse_mode='Markdown')
        
        # --- OCR ---
        elif command == 'ocr':
            res = get_ai_response("Extract ALL text from this file. Provide complete transcription.", file_path)
            
            # Send text
            for i in range(0, len(res), 4000):
                await context.bot.send_message(chat_id=chat_id, text=res[i:i+4000])
            
            # Also send as text file
            text_bio = BytesIO(res.encode('utf-8'))
            text_bio.seek(0)
            await context.bot.send_document(chat_id=chat_id, document=text_bio, filename="OCR_Result.txt")
        
        # --- Summary ---
        elif command in ['summary', 'summary_audio']:
            res = get_ai_response("ဤဖိုင်ကို မြန်မာလို အသေးစိတ် အနှစ်ချုပ်ပေးပါ။ Key points များကို ထုတ်ပေးပါ။", file_path)
            
            for i in range(0, len(res), 4000):
                await context.bot.send_message(chat_id=chat_id, text=res[i:i+4000])
        
        # --- Audio Output ---
        elif command == 'audio':
            res = get_ai_response("ဤဖိုင်ကို မြန်မာလို အတိုချုပ်ပေးပါ (Audio အတွက် အတိုရှင်းရှင်း)။", file_path)
            
            try:
                tts = gTTS(text=res[:3000], lang='my')
                audio_bio = BytesIO()
                tts.write_to_fp(audio_bio)
                audio_bio.seek(0)
                await context.bot.send_audio(chat_id=chat_id, audio=audio_bio, title="AI Summary Audio", filename="summary.mp3")
            except:
                await 
