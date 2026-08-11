from __future__ import annotations

from pathlib import Path

import pkcs11
from pkcs11 import Attribute, ObjectClass
from pyhanko.sign.pkcs11 import PKCS11Signer
from pyhanko.sign.signers import PdfSigner, PdfSignatureMetadata
from pyhanko.sign.fields import SigFieldSpec
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter


def sign_pdf_pades(
    pdf_in: Path,
    pdf_out: Path,
    pkcs11_lib_path: str,
    pin: str,
    cert_label: str,
):
    lib = pkcs11.lib(pkcs11_lib_path)
    slots = lib.get_slots(token_present=True)
    if not slots:
        raise RuntimeError("Nenhum token presente.")
    token = slots[0].get_token()

    try:
        session = token.open(user_pin=pin)
    except pkcs11.exceptions.UserAlreadyLoggedIn:
        session = token.open(rw=False)

    with session:
        signer = PKCS11Signer(
            pkcs11_session=session,
            cert_label=cert_label,
            key_label=cert_label,
        )

        meta = PdfSignatureMetadata(
            field_name="Assinatura1",
            reason="Assinatura digital",
            location="Brasil",
        )

        pdf_signer = PdfSigner(
            signature_meta=meta,
            signer=signer,
            new_field_spec=SigFieldSpec(sig_field_name="Assinatura1"),
        )

        with open(pdf_in, "rb") as inf:
            w = IncrementalPdfFileWriter(inf)
            with open(pdf_out, "wb") as outf:
                pdf_signer.sign_pdf(w, output=outf)
