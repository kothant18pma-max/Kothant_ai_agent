import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM
from langchain_community.document_loaders import PyPDFLoader
import tempfile

# UI အပြင်အဆင်
st.set_page_config(page_title="AI PDF Analyst", layout="centered")
st.title("📄 AI PDF Analyst (Myanmar)")
st.write("PDF ဖိုင်တင်ပြီး အနှစ်ချုပ်ခိုင်းကြည့်ပါ။")

# API Key ထည့်ရန် (Sidebar တွင် ထည့်ခိုင်းခြင်းက ပိုလုံခြုံသည်)
with st.sidebar:
    google_api_key = st.text_input("Google API Key", type="password")
    os.environ["GOOGLE_API_KEY"] = google_api_key

# PDF Upload လုပ်ရန်
uploaded_file = st.file_uploader("PDF ဖိုင်ရွေးပါ", type=["pdf"])

if uploaded_file and google_api_key:
    if st.button("စတင်လေ့လာပါ"):
        with st.spinner("Agent များ အလုပ်လုပ်နေပါပြီ... ခဏစောင့်ပါ"):
            try:
                # ၁။ PDF ကို ယာယီသိမ်းပြီး ဖတ်ခြင်း
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_path = tmp_file.name

                loader = PyPDFLoader(tmp_path)
                pages = loader.load_and_split()
                pdf_content = "\n".join([page.page_content for page in pages])

                # ၂။ CrewAI Setup
                gemini_llm = LLM(model="gemini/gemini-1.5-flash")

                analyst = Agent(
                    role='စာရွက်စာတမ်း ကျွမ်းကျင်သူ',
                    goal='PDF အချက်အလက်များကို မြန်မာလို အနှစ်ချုပ်ရန်',
                    backstory='သင်သည် စာရွက်စာတမ်းများကို စေ့စေ့စပ်စပ် ဖတ်ရှုနိုင်သူဖြစ်သည်။',
                    llm=gemini_llm
                )

                task = Task(
                    description=f"အောက်ပါ စာသားများကို ဖတ်ပြီး အချက် ၅ ချက်ဖြင့် မြန်မာလို အနှစ်ချုပ်ပါ: \n\n {pdf_content}",
                    expected_output="သပ်ရပ်သော မြန်မာလို အနှစ်ချုပ် အစီရင်ခံစာ။",
                    agent=analyst
                )

                crew = Crew(agents=[analyst], tasks=[task])
                result = crew.kickoff()

                # ၃။ အဖြေထုတ်ပြခြင်း
                st.success("ပြီးစီးပါပြီ!")
                st.markdown("### 📋 အနှစ်ချုပ် ရလဒ်")
                st.write(str(result))
                
                # File အဖြစ် ပြန်ဒေါင်းရန်
                st.download_button("Report ကို ဒေါင်းလုဒ်ဆွဲရန်", str(result), file_name="summary.txt")

                os.remove(tmp_path) # ယာယီဖိုင်ကို ပြန်ဖျက်ခြင်း

            except Exception as e:
                st.error(f"Error တက်သွားပါသည်: {e}")
else:
    st.info("အပေါ်က အကွက်မှာ PDF တင်ပြီး ဘေးက Sidebar မှာ API Key ထည့်ပေးပါ။")