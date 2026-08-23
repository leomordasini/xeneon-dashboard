"""
generate_cert.py — Run ONCE as Administrator
Generates a self-signed SSL cert for 192.168.1.148 and installs it
to the Windows Trusted Root store so the Xeneon browser trusts it.

Usage:
    pip install cryptography
    python generate_cert.py
"""

import datetime, ipaddress, subprocess, sys, os

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("Installing cryptography library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(HERE, "cert.pem")
KEY  = os.path.join(HERE, "key.pem")
IP   = "192.168.1.148"

print(f"Generating SSL certificate for {IP}...")

# Generate private key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Build certificate
subject = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME,         "Xeneon Dashboard"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME,   "Local"),
])
cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(subject)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
    .add_extension(
        x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.IPv4Address(IP)),
            x509.DNSName("localhost"),
        ]),
        critical=False,
    )
    .add_extension(
        x509.BasicConstraints(ca=True, path_length=None),
        critical=True,
    )
    .add_extension(
        x509.KeyUsage(
            digital_signature=True, key_cert_sign=True, key_encipherment=True,
            content_commitment=False, data_encipherment=False, key_agreement=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ),
        critical=True,
    )
    .sign(key, hashes.SHA256())
)

# Write cert.pem and key.pem
with open(KEY, "wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))

with open(CERT, "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print(f"  cert.pem → {CERT}")
print(f"  key.pem  → {KEY}")

# Install to Windows Trusted Root
print("\nInstalling certificate to Windows Trusted Root store...")
result = subprocess.run(
    ["certutil", "-addstore", "-f", "Root", CERT],
    capture_output=True, text=True
)

if result.returncode == 0:
    print("  [OK] Certificate trusted by Windows!")
    print("  The Xeneon browser will now accept HTTPS from this server.")
else:
    print("  [WARN] Could not auto-install. Run as Administrator.")
    print("  Or run manually in PowerShell (as Admin):")
    print(f'  certutil -addstore Root "{CERT}"')
    print()
    print(result.stderr)

print(f"""
Done! Next steps:
  1. Run server: python server.py (or double-click start_server.bat)
  2. In iCUE → Web URL widget → Size XL
     URL: https://{IP}:8080/lights.html
""")
