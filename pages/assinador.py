import io
import zipfile
import tempfile
from pathlib import Path

import streamlit as st

from pkcs11_utils import list_certificates
from p7s_signer import sign_file_to_p7s_detached
from pdf_signer import sign_pdf_pades

# Aumenta limite de upload para 400MB
st.config.set_option("server.maxUploadSize", 400)
st.title("Tribunal 2.0")
st.caption("Assina PDFs em lote: gera .p7s (CAdES/PKCS#7) e/ou PDF embutido (PAdES). Rode localmente no PC com o token.")


def zip_dir(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, arcname=f.relative_to(folder))
    buf.seek(0)
    return buf.read()


with st.sidebar:
    st.header("Configuração PKCS#11 (Token GD)")

    pkcs11_lib = st.text_input(
        "Caminho da DLL PKCS#11",
        value=r"C:\Windows\System32\aetpkss1.dll",
        help="DLL PKCS#11 do GD StarSign CUT (aetpkss1.dll). Altere se usar outro driver.",
    )
    pin = st.text_input("PIN do token", value="1234", type="password")

    st.divider()
    st.subheader("Assinatura")
    gerar_p7s = st.checkbox("Gerar P7S (.p7s) - CAdES/PKCS#7 (detached)", value=True)
    gerar_pdf = st.checkbox("Gerar PDF assinado - PAdES (embutido)", value=True)

certs = []
cert_choice = None

# Carrega certificados automaticamente quando DLL e PIN estão preenchidos
if pkcs11_lib.strip() and pin.strip():
    if "certs" not in st.session_state:
        try:
            st.session_state["certs"] = list_certificates(pkcs11_lib.strip(), pin.strip())
        except Exception as e:
            st.warning(str(e))

    # Botão para recarregar manualmente se necessário
    with st.sidebar:
        st.divider()
        if st.button("Recarregar certificados", use_container_width=True):
            try:
                st.session_state["certs"] = list_certificates(pkcs11_lib.strip(), pin.strip())
                st.rerun()
            except Exception as e:
                st.warning(str(e))

certs = st.session_state.get("certs", [])

if certs:
    st.subheader("Certificados encontrados no token")
    for idx, c in enumerate(certs):
        st.write(
            f"**[{idx}]**  Label: `{c['label']}` | Subject: `{c['subject']}` | "
            f"Serial: `{c['serial_hex']}` | Validade: {c['not_before']} → {c['not_after']}"
        )

    cert_idx = st.number_input("Escolha o índice do certificado", min_value=0, max_value=len(certs) - 1, value=0, step=1)
    cert_choice = certs[int(cert_idx)]
else:
    st.info("Nenhum certificado listado ainda. Preencha DLL + PIN na sidebar.")

st.subheader("Arquivos")

modo = st.radio("Modo de entrada", ["Pasta local", "Upload de arquivos"], horizontal=True)

folder_path_str = ""
uploads = []
folder_name = "assinados"

if modo == "Pasta local":
    folder_path_str = st.text_input(
        "Caminho da pasta com PDFs",
        placeholder=r"C:\Users\...\meus_pdfs",
        help="Informe o caminho completo de uma pasta. Todos os PDFs dentro dela serão assinados.",
    )
    if folder_path_str.strip():
        folder_path = Path(folder_path_str.strip())
        if folder_path.is_dir():
            pdf_files = sorted(folder_path.glob("*.pdf"))
            if pdf_files:
                folder_name = folder_path.name
                st.info(f"Pasta: **{folder_name}** — {len(pdf_files)} PDF(s) encontrado(s)")
            else:
                st.warning("Nenhum arquivo PDF encontrado nesta pasta.")
        else:
            st.warning("Caminho informado não é uma pasta válida.")
else:
    uploads = st.file_uploader("Envie 1 ou mais PDFs", type=["pdf"], accept_multiple_files=True)

has_files = (modo == "Pasta local" and folder_path_str.strip() and Path(folder_path_str.strip()).is_dir() and any(Path(folder_path_str.strip()).glob("*.pdf"))) or (modo == "Upload de arquivos" and uploads)
run = st.button("Assinar em lote", type="primary", disabled=not has_files)

log_col, out_col = st.columns([1, 1])

if run:
    if not pkcs11_lib.strip():
        st.error("Informe o caminho da DLL PKCS#11.")
        st.stop()
    if not pin.strip():
        st.error("Informe o PIN do token.")
        st.stop()
    if not cert_choice:
        st.error("Liste e selecione um certificado do token.")
        st.stop()
    if not gerar_p7s and not gerar_pdf:
        st.error("Selecione pelo menos um modo de assinatura.")
        st.stop()

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        in_dir = base / "in"
        out_dir = base / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Monta lista de arquivos de entrada
        if modo == "Pasta local":
            src_folder = Path(folder_path_str.strip())
            pdf_files = sorted(src_folder.glob("*.pdf"))
            for pf in pdf_files:
                (in_dir / pf.name).write_bytes(pf.read_bytes())
            file_names = [pf.name for pf in pdf_files]
            zip_name = f"{src_folder.name}.zip"
        else:
            for uf in uploads:
                (in_dir / uf.name).write_bytes(uf.getbuffer())
            file_names = [uf.name for uf in uploads]
            zip_name = "assinados.zip"

        logs = []
        ok_count = 0
        fail_count = 0

        progress = st.progress(0)
        total = len(file_names)

        for i, fname in enumerate(file_names, start=1):
            src = in_dir / fname
            file_ok = True

            if gerar_p7s:
                try:
                    out_p7s = out_dir / (fname + ".p7s")
                    sign_file_to_p7s_detached(
                        file_path=src,
                        out_path=out_p7s,
                        pkcs11_lib_path=pkcs11_lib.strip(),
                        pin=pin.strip(),
                        cert_label=cert_choice["label"],
                    )
                    logs.append(f"[OK] P7S: {fname} -> {out_p7s.name}")
                except Exception as e:
                    file_ok = False
                    logs.append(f"[ERRO] P7S {fname}: {type(e).__name__}: {e}")

            if gerar_pdf:
                try:
                    out_pdf = out_dir / fname
                    sign_pdf_pades(
                        pdf_in=src,
                        pdf_out=out_pdf,
                        pkcs11_lib_path=pkcs11_lib.strip(),
                        pin=pin.strip(),
                        cert_label=cert_choice["label"],
                    )
                    logs.append(f"[OK] PDF: {fname} -> {out_pdf.name}")
                except Exception as e:
                    file_ok = False
                    logs.append(f"[ERRO] PDF {fname}: {type(e).__name__}: {e}")

            if file_ok:
                ok_count += 1
            else:
                fail_count += 1

            progress.progress(i / total)

        zip_bytes = zip_dir(out_dir)

        with out_col:
            st.success(f"Concluído. OK: {ok_count} | Falhas: {fail_count}")
            st.download_button(
                "Baixar ZIP",
                data=zip_bytes,
                file_name=zip_name,
                mime="application/zip",
                use_container_width=True,
            )

        with log_col:
            st.subheader("Logs")
            st.code("\n".join(logs))
