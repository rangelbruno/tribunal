from __future__ import annotations

from pathlib import Path
import hashlib

import pkcs11
from pkcs11 import Attribute, ObjectClass, Mechanism

from asn1crypto import cms, algos, core, x509 as asn1_x509


def _find_cert_and_key(session, cert_label: str):
    # Certificado
    cert_obj = None
    for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
        try:
            label = obj[Attribute.LABEL]
        except Exception:
            continue
        if isinstance(label, (bytes, bytearray)):
            label = label.decode(errors="ignore")
        if str(label) == cert_label:
            cert_obj = obj
            break

    if not cert_obj:
        raise RuntimeError(f"Certificado com label '{cert_label}' não encontrado no token.")

    cert_der = cert_obj[Attribute.VALUE]
    cert_asn1 = asn1_x509.Certificate.load(cert_der)

    # Chave privada – tenta casar pelo ID (quando disponível)
    key_obj = None
    try:
        cert_id = cert_obj[Attribute.ID]
    except Exception:
        cert_id = None

    if cert_id is not None:
        keys = session.get_objects(
            {
                Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                Attribute.ID: cert_id,
            }
        )
        key_obj = next(iter(keys), None)

    if key_obj is None:
        # fallback: pega a primeira chave privada
        keys = session.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY})
        key_obj = next(iter(keys), None)

    if not key_obj:
        raise RuntimeError("Chave privada não encontrada no token (PRIVATE_KEY).")

    return cert_asn1, key_obj


def sign_file_to_p7s_detached(
    file_path: Path,
    out_path: Path,
    pkcs11_lib_path: str,
    pin: str,
    cert_label: str,
):
    """
    Gera CMS SignedData (PKCS#7) DETACHED:
    - assinatura inclui messageDigest do conteúdo
    - não embute o conteúdo (detached), então o .p7s valida com o arquivo original
    """
    data = Path(file_path).read_bytes()
    digest = hashlib.sha256(data).digest()

    lib = pkcs11.lib(pkcs11_lib_path)
    slots = lib.get_slots(token_present=True)
    if not slots:
        raise RuntimeError("Nenhum token presente. Plugue o GD StarSign e tente novamente.")
    token = slots[0].get_token()

    try:
        session = token.open(user_pin=pin)
    except pkcs11.exceptions.UserAlreadyLoggedIn:
        session = token.open(rw=False)

    with session:
        cert_asn1, key_obj = _find_cert_and_key(session, cert_label)

        # SignedAttributes (RFC 5652)
        signed_attrs = cms.CMSAttributes(
            [
                cms.CMSAttribute({"type": "content_type", "values": [cms.ContentType("data")]}),
                cms.CMSAttribute({"type": "message_digest", "values": [digest]}),
            ]
        )

        # Assinatura é feita sobre a DER dos signed_attrs (com tag SET OF)
        to_sign = signed_attrs.dump()

        signature = key_obj.sign(
            to_sign,
            mechanism=Mechanism.SHA256_RSA_PKCS,
        )

        signer_info = cms.SignerInfo(
            {
                "version": 1,
                "sid": cms.SignerIdentifier(
                    name="issuer_and_serial_number",
                    value=cms.IssuerAndSerialNumber(
                        {
                            "issuer": cert_asn1.issuer,
                            "serial_number": cert_asn1.serial_number,
                        }
                    ),
                ),
                "digest_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
                "signed_attrs": signed_attrs,
                "signature_algorithm": algos.SignedDigestAlgorithm({"algorithm": "rsassa_pkcs1v15"}),
                "signature": signature,
            }
        )

        signed_data = cms.SignedData(
            {
                "version": 1,
                "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
                "encap_content_info": cms.ContentInfo(
                    {
                        "content_type": "data",
                    }
                ),
                "certificates": [cert_asn1],
                "signer_infos": [signer_info],
            }
        )

        content_info = cms.ContentInfo({"content_type": "signed_data", "content": signed_data})
        out_path.write_bytes(content_info.dump())