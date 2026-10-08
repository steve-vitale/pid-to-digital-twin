"""OPC UA client for reading the gateway the way any outside system would: Ignition's own OPC UA server, encrypted
(Basic256Sha256, SignAndEncrypt), with a client certificate the gateway administrator must approve once.

Private material lives in IGNITION_SECRETS_DIR: the client certificate/key and opcua-verifier.json (written by
build_gateway.py). Nothing here is committed.
"""
import datetime
import json
import os
import socket
from pathlib import Path

from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

GATEWAY_UA = os.environ.get("IGNITION_UA_URL", "opc.tcp://localhost:62541")
APP_URI = "urn:pid-digital-twin:verifier"
TAG_NS = "urn:inductiveautomation:ignition:opcua:tags"


def secrets_dir():
    d = os.environ.get("IGNITION_SECRETS_DIR")
    if not d:
        raise SystemExit("set IGNITION_SECRETS_DIR (private folder outside the repo)")
    return Path(d)


async def ensure_cert():
    """Self-signed OPC UA application certificate (Part 6 profile for Basic256Sha256: RSA 2048, SHA-256, the
    application URI in subjectAltName). The gateway rejects it until an administrator trusts it, after checking
    its SHA-1 fingerprint (printed by `python scripts/ignition/ua_client.py`)."""
    d = secrets_dir()
    d.mkdir(parents=True, exist_ok=True)
    cert, key = d / "verifier-cert.der", d / "verifier-key.pem"
    if not cert.exists():
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pid-digital-twin verifier"),
                          x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pid-digital-twin")])
        now = datetime.datetime.now(datetime.timezone.utc)
        c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
             .not_valid_after(now + datetime.timedelta(days=365))
             .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(APP_URI),
                                                         x509.DNSName(socket.gethostname())]), critical=False)
             # Self-signed, so it is its own issuer: OPC UA stacks (Ignition's included) require keyCertSign and
             # cA=true here, and reject the certificate with BadCertificateUseNotAllowed without them.
             .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
             .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=True,
                                          data_encipherment=True, key_agreement=False, key_cert_sign=True,
                                          crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
             .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH,
                                                   ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False)
             .sign(k, hashes.SHA256()))
        key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                        serialization.NoEncryption()))
        cert.write_bytes(c.public_bytes(serialization.Encoding.DER))
    return cert, key


async def connect():
    cert, key = await ensure_cert()
    cred = json.loads((secrets_dir() / "opcua-verifier.json").read_text(encoding="utf-8"))
    c = Client(GATEWAY_UA, timeout=15)
    c.application_uri = APP_URI
    c.set_user(cred["username"])
    c.set_password(cred["password"])
    await c.set_security(SecurityPolicyBasic256Sha256, str(cert), str(key), mode=ua.MessageSecurityMode.SignAndEncrypt)
    await c.connect()
    return c


async def tag_ns(c):
    return await c.get_namespace_index(TAG_NS)


if __name__ == "__main__":
    import asyncio
    import hashlib
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gw
    gw._load_env()
    cert_path, _ = asyncio.run(ensure_cert())
    print("verifier certificate SHA-1:", hashlib.sha1(cert_path.read_bytes()).hexdigest())
    print("Trust it in the gateway (Connections > OPC > Security > Server) only if this fingerprint matches.")
