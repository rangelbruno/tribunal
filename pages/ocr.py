import io
import os
import sys
from pathlib import Path

# Corrige encoding do console Windows para evitar erro com caracteres Unicode do EasyOCR
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"

import streamlit as st

st.title("OCR — Extrair texto de PDF / Imagens")
st.caption(
    "Faça upload de PDFs ou imagens (PNG, JPG, TIFF) e extraia o texto via OCR. "
    "Usa EasyOCR com suporte a Português e Inglês."
)

SUPPORTED_IMG = ["png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp"]
SUPPORTED = ["pdf"] + SUPPORTED_IMG


@st.cache_resource(show_spinner="Carregando modelo OCR (primeira vez pode demorar)...")
def load_reader():
    import easyocr
    return easyocr.Reader(["pt", "en"], gpu=False, verbose=False)


def ocr_image(reader, image_bytes: bytes) -> str:
    results = reader.readtext(image_bytes, detail=0, paragraph=True)
    return "\n".join(results)


def ocr_pdf(reader, pdf_bytes: bytes) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = []
    progress = st.progress(0, text="Processando páginas...")
    total = len(doc)
    for i, page in enumerate(doc):
        # Renderiza página como imagem PNG em 300 DPI
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        text = ocr_image(reader, img_bytes)
        all_text.append(f"--- Página {i + 1} ---\n{text}")
        progress.progress((i + 1) / total, text=f"Página {i + 1} de {total}")
    progress.empty()
    doc.close()
    return "\n\n".join(all_text)


uploads = st.file_uploader(
    "Envie PDFs ou imagens",
    type=SUPPORTED,
    accept_multiple_files=True,
)

if uploads:
    reader = load_reader()

    for upload in uploads:
        st.divider()
        ext = Path(upload.name).suffix.lower().lstrip(".")
        file_bytes = upload.read()

        st.subheader(f"{upload.name}")

        with st.spinner(f"Executando OCR em {upload.name}..."):
            if ext == "pdf":
                text = ocr_pdf(reader, file_bytes)
            else:
                text = ocr_image(reader, file_bytes)

        if text.strip():
            st.text_area("Texto extraído", text, height=400, key=f"txt_{upload.name}")

            st.download_button(
                "Baixar como TXT",
                data=text.encode("utf-8"),
                file_name=f"{Path(upload.name).stem}_ocr.txt",
                mime="text/plain",
                key=f"dl_{upload.name}",
                use_container_width=True,
            )
        else:
            st.warning("Nenhum texto detectado neste arquivo.")
