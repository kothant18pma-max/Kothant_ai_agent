import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM
from crewai_tools import PDFSearchTool, SerperDevTool
from langchain_community.document_loaders import PyPDFLoader
import tempfile

st.set_page_config(page_title="AI Researcher", layout="wide")
st.title("🔍 Advanced AI Researcher (PDF + Web)")

# Sidebar for API Keys
with st.sidebar:
    st.header("API Configuration")
    google_key = st.text_input("Google API Key", type="password")
    serper_key = st.text_input("Serper API Key (for Web Search)", type="password")
    
    if google_key:
        os.environ["GOOGLE_API_KEY"] = google_key
    if serper_key:
        os.environ["SERPER_API_KEY"] = serper_key

# PDF Upload
uploaded_file = st.file_uploader("သုတေသနပြုမည့် PDF တင်ပါ", type=["pdf"])

if uploaded_file and google_key:
    if st.button("သုတေသန စတင်ပါ"):
        with st.spinner("Agent များ အလုပ်လုပ်နေပါပြီ..."):
            # ၁။ PDF ဖတ်ခြင်း
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            loader = PyPDFLoader(tmp_path)
            pages = loader.load_and_split()
            pdf_content = "\n".join([page.page_content for page in pages])

            # ၂။ Tools & LLM
            search_tool = SerperDevTool()
            gemini_llm = LLM(model="gemini/gemini-2.5-flash")

            # ၃။ Agents
            researcher = Agent(
                role='ဝါရင့် သုတေသီ',
                goal='PDF ထဲမှ အချက်အလက်များကို အခြေခံပြီး အင်တာနက်ပေါ်ရှိ နောက်ဆုံးရသတင်းများနှင့် တိုက်ဆိုင်စစ်ဆေးရန်',
                backstory='သင်သည် အချက်အလက်များကို နှိုင်းယှဉ်လေ့လာရာတွင် ကျွမ်းကျင်သူဖြစ်ပြီး တိကျမှန်ကန်မှုကို ဦးစားပေးသူဖြစ်သည်။',
                tools=[search_tool],
                llm=gemini_llm
            )

            # ၄။ Tasks
            task = Task(
                description=f"""
                ၁။ ပေးထားသော PDF အချက်အလက်များကို ဖတ်ပါ: {pdf_content}
                ၂။ ထိုအကြောင်းအရာနှင့် ပတ်သက်၍ အင်တာနက်တွင် နောက်ဆုံးရသတင်းများကို ရှာဖွေပါ။
                ၃။ PDF ပါ အချက်အလက်နှင့် အပြင်လောက သတင်းများကို နှိုင်းယှဉ်ပြီး မြန်မာလို အစီရင်ခံစာ ရေးပေးပါ။
                """,
                expected_output="PDF နှင့် အင်တာနက်သတင်းများကို နှိုင်းယှဉ်ထားသော ပြည့်စုံသည့် မြန်မာလို သုတေသန မှတ်တမ်း။",
                agent=researcher
            )

            crew = Crew(agents=[researcher], tasks=[task])
            result = crew.kickoff()

            st.success("သုတေသန ပြီးစီးပါပြီ!")
            st.markdown(result.raw)
            
            os.remove(tmp_path)
