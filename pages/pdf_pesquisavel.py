import io
import os
import time
import zipfile
from pathlib import Path

import streamlit as st

from ocr_engine import (
    available_engine,
    default_language,
    find_tesseract,
    make_searchable_pdf,
    tesseract_languages,
)

st.config.set_option("server.maxUploadSize", 400)

st.title("PDF Pesquisável (OCR em lote)")
st.caption(
    "Selecione vários PDFs digitalizados e gere versões pesquisáveis. "
    "O documento continua idêntico na tela: o texto é gravado numa camada invisível por cima da imagem."
)

ENGINE = available_engine()
LANGS = tesseract_languages()
MAX_WORKERS = min(8, os.cpu_count() or 4)

if ENGINE == "tesseract":
    st.success(f"Motor rápido ativo: Tesseract ({find_tesseract()}).", icon=":material/bolt:")
else:
    st.warning(
        "Tesseract não encontrado — usando EasyOCR, que é bem mais lento e não roda em paralelo. "
        "No Windows, instale o **Tesseract-OCR** (com o pacote de idioma Português) e reinicie o app "
        "para o processamento ficar várias vezes mais rápido.",
        icon=":material/slow_motion_video:",
    )

uploads = st.file_uploader(
    "Envie os PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

RESULT_KEYS = (
    "pesquisavel_outputs",
    "pesquisavel_summary",
    "pesquisavel_failures",
    "pesquisavel_elapsed",
    "pesquisavel_zip",
)

# Trocar a seleção de arquivos descarta o resultado anterior, senão a tela
# continuaria mostrando downloads que não correspondem mais ao que está listado.
selection = tuple((upload.name, upload.size) for upload in uploads or ())
if st.session_state.get("pesquisavel_selecao") != selection:
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)
    st.session_state["pesquisavel_selecao"] = selection

with st.expander("Opções de processamento"):
    col_a, col_b = st.columns(2)

    with col_a:
        quality = st.select_slider(
            "Qualidade da leitura",
            options=["Rápida (150 DPI)", "Equilibrada (200 DPI)", "Máxima (300 DPI)"],
            value="Equilibrada (200 DPI)",
            help="Menos DPI é mais rápido. 300 DPI só compensa em documentos com letra miúda ou de má qualidade.",
        )
        dpi = {"Rápida (150 DPI)": 150, "Equilibrada (200 DPI)": 200, "Máxima (300 DPI)": 300}[quality]

        skip_text_pages = st.checkbox(
            "Pular páginas que já têm texto",
            value=True,
            help="Peticionamentos e documentos gerados por sistema já são pesquisáveis. "
            "Pular essas páginas costuma ser o maior ganho de velocidade.",
        )

    with col_b:
        if ENGINE == "tesseract":
            workers = st.slider(
                "Páginas em paralelo",
                min_value=1,
                max_value=MAX_WORKERS,
                value=MAX_WORKERS,
                help="Quantas páginas são reconhecidas ao mesmo tempo.",
            )
            lang = st.selectbox(
                "Idioma",
                options=[default_language(LANGS)] + [item for item in LANGS if item != default_language(LANGS)],
                help="Idiomas instalados no Tesseract desta máquina.",
            )
        else:
            workers = 1
            lang = "por+eng"
            st.info("Paralelismo e escolha de idioma ficam disponíveis com o Tesseract instalado.")

start = st.button(
    "Gerar PDFs pesquisáveis",
    type="primary",
    disabled=not uploads,
    use_container_width=True,
)


def build_zip(files: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return buffer.getvalue()


if start and uploads:
    overall = st.progress(0.0, text="Preparando...")
    status = st.empty()

    outputs: list[tuple[str, bytes]] = []
    failures: list[tuple[str, str]] = []
    summary: list[dict] = []

    began = time.perf_counter()

    for index, upload in enumerate(uploads):
        label = upload.name
        status.write(f"Processando **{label}** ({index + 1} de {len(uploads)})...")

        def report(done: int, total: int, index=index, label=label) -> None:
            inner = done / total if total else 1.0
            overall.progress(
                (index + inner) / len(uploads),
                text=f"{label} — página {done} de {total}" if total else f"{label} — sem páginas para OCR",
            )

        file_began = time.perf_counter()
        try:
            result = make_searchable_pdf(
                upload.getvalue(),
                engine=ENGINE,
                lang=lang,
                dpi=dpi,
                skip_text_pages=skip_text_pages,
                workers=workers,
                progress_cb=report,
            )
        except Exception as error:  # noqa: BLE001 — um arquivo ruim não pode parar o lote
            failures.append((label, str(error)))
            continue

        outputs.append((f"{Path(label).stem}_pesquisavel.pdf", result.data))
        summary.append(
            {
                "Arquivo": label,
                "Páginas": result.pages_total,
                "Com OCR": result.pages_ocr,
                "Já tinham texto": result.pages_skipped,
                "Palavras": result.words,
                "Tempo (s)": round(time.perf_counter() - file_began, 1),
            }
        )

    overall.progress(1.0, text="Concluído")
    status.empty()

    st.session_state["pesquisavel_outputs"] = outputs
    st.session_state["pesquisavel_summary"] = summary
    st.session_state["pesquisavel_failures"] = failures
    st.session_state["pesquisavel_elapsed"] = time.perf_counter() - began
    # Monta o ZIP uma vez só: cada clique em download dispara um rerun da página.
    st.session_state["pesquisavel_zip"] = build_zip(outputs) if len(outputs) > 1 else None

outputs = st.session_state.get("pesquisavel_outputs") or []
summary = st.session_state.get("pesquisavel_summary") or []
failures = st.session_state.get("pesquisavel_failures") or []
elapsed = st.session_state.get("pesquisavel_elapsed")

if failures:
    for name, message in failures:
        st.error(f"**{name}**: {message}")

if outputs:
    st.divider()

    pages_ocr = sum(item["Com OCR"] for item in summary)
    pages_skipped = sum(item["Já tinham texto"] for item in summary)

    col_1, col_2, col_3, col_4 = st.columns(4)
    col_1.metric("PDFs gerados", len(outputs))
    col_2.metric("Páginas com OCR", pages_ocr)
    col_3.metric("Páginas puladas", pages_skipped)
    col_4.metric("Tempo total", f"{elapsed:.1f}s" if elapsed else "—")

    bundle = st.session_state.get("pesquisavel_zip")
    if bundle:
        st.download_button(
            f"Baixar todos ({len(outputs)} PDFs) em ZIP",
            data=bundle,
            file_name="pdfs_pesquisaveis.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

    st.dataframe(summary, hide_index=True, use_container_width=True)

    for position, (name, data) in enumerate(outputs):
        st.download_button(
            f"Baixar {name}",
            data=data,
            file_name=name,
            mime="application/pdf",
            # A posição entra na chave porque dois envios podem ter o mesmo nome.
            key=f"dl_{position}_{name}",
            use_container_width=True,
        )
