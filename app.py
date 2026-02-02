
import streamlit as st
import os
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool
from langchain_community.document_loaders import PyPDFLoader
import tempfile
from docx import Document
from io import BytesIO

# --- Word File ထုတ်ပေးသည့် Function ---
def create_word_file(content):
    doc = Document()
    doc.add_heading('AI Research Report', 0)
    doc.add_paragraph(content)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

st.set_page_config(page_title="AI Researcher", layout="wide")
st.title("🔍 Advanced AI Researcher (PDF + Web)")

# Sidebar for API Keys
with st.sidebar:
    st.header("API Configuration")
    google_key = st.text_input("Google API Key", type="password")
    serper_key = st.text_input("Serper API Key", type="password")
    
    if google_key: os.environ["GOOGLE_API_KEY"] = google_key
    if serper_key: os.environ["SERPER_API_KEY"] = serper_key

uploaded_file = st.file_uploader("သုတေသနပြုမည့် PDF တင်ပါ", type=["pdf"])

if uploaded_file and google_key:
    if st.button("သုတေသန စတင်ပါ"):
        with st.spinner("Agent များ အလုပ်လုပ်နေပါပြီ..."):
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            loader = PyPDFLoader(tmp_path)
            pages = loader.load_and_split()
            pdf_content = "\n".join([page.page_content for page in pages])

            search_tool = SerperDevTool()
            gemini_llm = LLM(model="gemini/gemini-2.5-flash")

            researcher = Agent(
                role='ဝါရင့် သုတေသီ',
                goal='PDF နှင့် အင်တာနက် သတင်းများကို နှိုင်းယှဉ်လေ့လာရန်',
                backstory='သင်သည် တိကျသော သုတေသန အစီရင်ခံစာများ ရေးသားသူဖြစ်သည်။',
                tools=[search_tool],
                llm=gemini_llm
            )

            task = Task(
                description=f"ပေးထားသော PDF ကိုဖတ်ပါ: {pdf_content}။ ၎င်းနှင့်ပတ်သက်သော နောက်ဆုံးရသတင်းများကို ရှာဖွေပြီး မြန်မာလို အနှစ်ချုပ်ပေးပါ။",
                expected_output="ပြည့်စုံသော မြန်မာလို သုတေသန မှတ်တမ်း။",
                agent=researcher
            )

            crew = Crew(agents=[researcher], tasks=[task])
            result = crew.kickoff()

            # --- ရလဒ်ပြသခြင်းနှင့် Download ခလုတ် ---
            st.success("သုတေသန ပြီးစီးပါပြီ!")
            st.markdown(result.raw)
            
            # Word file ဖန်တီးပြီး Download Button ပြခြင်း
            docx_data = create_word_file(str(result.raw))
            st.download_button(
                label="📥 Word File (DOCX) အဖြစ် ဒေါင်းလုဒ်ဆွဲပါ",
                data=docx_data,
                file_name="research_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
            os.remove(tmp_path)


