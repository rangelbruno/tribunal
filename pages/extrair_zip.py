import io
import zipfile
import tempfile
from pathlib import Path

import streamlit as st

st.title("Extrair ZIPs")
st.caption("Envie vários arquivos .zip e baixe todos extraídos em pastas separadas (uma pasta por ZIP).")

uploads = st.file_uploader("Envie 1 ou mais arquivos ZIP", type=["zip"], accept_multiple_files=True)

run = st.button("Extrair todos", type="primary", disabled=not uploads)

if run:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        logs = []
        ok_count = 0
        fail_count = 0

        progress = st.progress(0)
        total = len(uploads)

        for i, uf in enumerate(uploads, start=1):
            zip_name = Path(uf.name).stem  # nome sem .zip
            out_folder = base / zip_name
            out_folder.mkdir(parents=True, exist_ok=True)

            try:
                with zipfile.ZipFile(io.BytesIO(uf.getbuffer()), "r") as zf:
                    zf.extractall(out_folder)
                file_count = sum(1 for f in out_folder.rglob("*") if f.is_file())
                logs.append(f"[OK] {uf.name} -> pasta '{zip_name}/' ({file_count} arquivo(s))")
                ok_count += 1
            except Exception as e:
                logs.append(f"[ERRO] {uf.name}: {type(e).__name__}: {e}")
                fail_count += 1

            progress.progress(i / total)

        # Gera um ZIP final com todas as pastas extraídas
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for f in base.rglob("*"):
                if f.is_file():
                    zout.write(f, arcname=f.relative_to(base))
        buf.seek(0)

        log_col, out_col = st.columns([1, 1])

        with out_col:
            st.success(f"Concluído. OK: {ok_count} | Falhas: {fail_count}")
            st.download_button(
                "Baixar tudo extraído (ZIP)",
                data=buf.getvalue(),
                file_name="extraidos.zip",
                mime="application/zip",
                use_container_width=True,
            )

        with log_col:
            st.subheader("Logs")
            st.code("\n".join(logs))
