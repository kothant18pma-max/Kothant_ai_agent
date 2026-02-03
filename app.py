# --- Smart AI Logic (OCR ပိုမိုကောင်းမွန်အောင် ပြင်ဆင်ထားသည်) ---
def process_smart_ai(file_path):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    uploaded_file = genai.upload_file(path=file_path)
    
    # Prompt ကို OCR ပုံစံသို့ ဦးတည်စေခြင်း
    prompt = """
    ဤဖိုင်ကို အသေးစိတ် ကြည့်ရှုပါ။
    ၁။ အကယ်၍ ဤဖိုင်သည် အချက်အလက် မရှိသော ပုံ (သို့မဟုတ်) ဖတ်မရသော ဖိုင်ဖြစ်ပါက 'DATA_INSUFFICIENT' ဟုသာ ရေးပါ။
    ၂။ အချက်အလက် ရှိပါက အောက်ပါအတိုင်း အဆင့်ဆင့် လုပ်ဆောင်ပါ -
       - [OCR Section]: ဖိုင်ထဲတွင် ပါဝင်သော စာသားအားလုံးကို မူရင်းအတိုင်း (Transcription) တစ်လုံးမကျန် အရင်ဆုံး ပြန်ထုတ်ပေးပါ။
       - [Summary Section]: ထိုစာသားများကို မြန်မာလို အနှစ်ချုပ်ပေးပါ။
       - [Translation Section]: အရေးကြီးသော အချက်များကို မြန်မာလို ဘာသာပြန်ပေးပါ။
       - [Table Section]: ဇယားများပါပါက Markdown Table format (| Col |) ဖြင့် သေချာစွာ ထုတ်ပေးပါ။
    """
    
    response = model.generate_content([prompt, uploaded_file])
    return response.text

# --- Telegram Handler (OCR Result ကို ကိုင်တွယ်ရန်) ---
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)
        
        file_obj = None
        suffix = ""
        # PDF ရော ပုံရော လက်ခံရန်
        if update.message.document:
            file_obj = await update.message.document.get_file()
            suffix = ".pdf"
        elif update.message.photo:
            file_obj = await update.message.photo[-1].get_file()
            suffix = ".jpg"
        
        if not file_obj: return

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as t:
            await file_obj.download_to_drive(t.name)
            res = process_smart_ai(t.name)
            
            if "DATA_INSUFFICIENT" in res:
                await update.message.reply_text("⚠️ ဤဖိုင်တွင် ဖတ်ရန်စာသား သို့မဟုတ် အချက်အလက် မရှိပါ။")
            else:
                # OCR ရလဒ်နှင့် အနှစ်ချုပ်ကို အပိုင်းလိုက်ခွဲပို့ခြင်း (Long Message Fix)
                for i in range(0, len(res), 4000):
                    await update.message.reply_text(res[i:i+4000])
                
                # Word File အဖြစ် သိမ်းဆည်းနိုင်ရန် ပြုလုပ်ပေးခြင်း
                doc_bio = BytesIO()
                doc = Document()
                doc.add_heading('OCR & AI Research Report', 0)
                doc.add_paragraph(res)
                doc.save(doc_bio)
                await update.message.reply_document(document=BytesIO(doc_bio.getvalue()), filename="Full_OCR_Report.docx")
                
                # ဇယားပါက Excel ထုတ်ပေးခြင်း
                ex = get_excel(res)
                if ex:
                    await update.message.reply_document(document=BytesIO(ex), filename="Extracted_Tables.xlsx")
            
            os.remove(t.name)
            
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")
