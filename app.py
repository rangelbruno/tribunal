import streamlit as st

st.set_page_config(page_title="Tribunal 2.0", layout="wide")

assinador = st.Page("pages/assinador.py", title="Tribunal 2.0", icon=":material/draw:", default=True)
dividir_pdf = st.Page("pages/dividir_pdf.py", title="Dividir PDF (5 MB)", icon=":material/content_cut:")
extrair_zip = st.Page("pages/extrair_zip.py", title="Extrair ZIPs", icon=":material/folder_zip:")
ocr = st.Page("pages/ocr.py", title="OCR (Extrair Texto)", icon=":material/document_scanner:")

nav = st.navigation([assinador, dividir_pdf, extrair_zip, ocr])
nav.run()
