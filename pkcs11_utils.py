from __future__ import annotations

import binascii
from datetime import datetime

import pkcs11
from pkcs11 import Attribute, ObjectClass

from cryptography import x509
from cryptography.hazmat.backends import default_backend


def _dt(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def list_certificates(pkcs11_lib_path: str, pin: str) -> list[dict]:
    lib = pkcs11.lib(pkcs11_lib_path)

    slots = lib.get_slots(token_present=True)
    if not slots:
        raise RuntimeError(
            "Nenhum token detectado.\n\n"
            "Verifique se o token GD StarSign está conectado ao computador "
            "e se o driver (DLL PKCS#11) está instalado corretamente.\n\n"
            "Dicas:\n"
            "• Confira se o dispositivo aparece no Gerenciador de Dispositivos do Windows.\n"
            "• Certifique-se de que o caminho da DLL informado na sidebar está correto.\n"
            "• Tente desconectar e reconectar o token, depois clique em 'Recarregar certificados'."
        )

    # usa o primeiro slot com token
    token = slots[0].get_token()

    results: list[dict] = []

    try:
        session = token.open(user_pin=pin)
    except pkcs11.exceptions.UserAlreadyLoggedIn:
        session = token.open(rw=False)

    with session:
        certs = session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE})
        for c in certs:
            raw_label = c[Attribute.LABEL]
            label = raw_label.decode(errors="ignore") if isinstance(raw_label, (bytes, bytearray)) else str(raw_label)
            der = c[Attribute.VALUE]
            cert = x509.load_der_x509_certificate(der, default_backend())

            serial_hex = format(cert.serial_number, "x").upper()
            subject = cert.subject.rfc4514_string()

            results.append(
                {
                    "label": label,
                    "subject": subject,
                    "serial_hex": serial_hex,
                    "not_before": _dt(cert.not_valid_before_utc),
                    "not_after": _dt(cert.not_valid_after_utc),
                }
            )

    if not results:
        raise RuntimeError("Nenhum certificado encontrado no token.")

    return results