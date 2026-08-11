import io
import zipfile
import tempfile
from pathlib import Path

import streamlit as st
from pypdf import PdfReader, PdfWriter

st.title("Dividir PDF em partes de até 5 MB")
st.caption("Faça upload de um PDF e ele será dividido em múltiplos arquivos, cada um com no máximo 5 MB.")

MAX_SIZE = 5 * 1024 * 1024  # 5 MB


def split_pdf(pdf_bytes: bytes, filename: str) -> list[tuple[str, bytes]]:
    """Divide um PDF em partes de até MAX_SIZE bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    if total_pages == 0:
        return []

    # Se o arquivo original já cabe em 5 MB, retorna ele mesmo
    if len(pdf_bytes) <= MAX_SIZE:
        return [(filename, pdf_bytes)]

    stem = Path(filename).stem
    parts: list[tuple[str, bytes]] = []
    current_pages: list[int] = []

    def flush(pages: list[int], part_num: int) -> bytes:
        writer = PdfWriter()
        for p in pages:
            writer.add_page(reader.pages[p])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    part_num = 1
    for i in range(total_pages):
        current_pages.append(i)

        # Gera o PDF parcial para verificar o tamanho
        candidate = flush(current_pages, part_num)

        if len(candidate) > MAX_SIZE:
            if len(current_pages) == 1:
                # Página individual já passa de 5 MB — inclui mesmo assim
                part_name = f"{stem}_parte{part_num}.pdf"
                parts.append((part_name, candidate))
                current_pages = []
                part_num += 1
            else:
                # Remove a última página e salva as anteriores
                current_pages.pop()
                part_data = flush(current_pages, part_num)
                part_name = f"{stem}_parte{part_num}.pdf"
                parts.append((part_name, part_data))
                current_pages = [i]
                part_num += 1

    # Salva páginas restantes
    if current_pages:
        part_data = flush(current_pages, part_num)
        part_name = f"{stem}_parte{part_num}.pdf"
        parts.append((part_name, part_data))

    return parts


upload = st.file_uploader("Envie um PDF", type=["pdf"])

if upload:
    pdf_bytes = upload.read()
    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    st.info(f"Arquivo: **{upload.name}** ({file_size_mb:.2f} MB)")

    if len(pdf_bytes) <= MAX_SIZE:
        st.success("O arquivo já tem 5 MB ou menos. Não precisa dividir!")
    else:
        if st.button("Dividir PDF", type="primary"):
            with st.spinner("Dividindo..."):
                parts = split_pdf(pdf_bytes, upload.name)

            st.success(f"PDF dividido em **{len(parts)} parte(s)**.")

            # Monta ZIP com todas as partes
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, data in parts:
                    zf.writestr(name, data)
            zip_buf.seek(0)

            st.download_button(
                "Baixar todas as partes (ZIP)",
                data=zip_buf.getvalue(),
                file_name=f"{Path(upload.name).stem}_dividido.zip",
                mime="application/zip",
                use_container_width=True,
            )

            st.divider()
            st.subheader("Partes geradas")
            for name, data in parts:
                size_mb = len(data) / (1024 * 1024)
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{name}** — {size_mb:.2f} MB")
                col2.download_button(
                    f"Baixar",
                    data=data,
                    file_name=name,
                    mime="application/pdf",
                    key=name,
                )
