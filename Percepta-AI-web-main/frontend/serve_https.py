"""
Simple HTTPS server for serving the frontend on LAN.
Mobile browsers require HTTPS for camera access (getUserMedia).
This script auto-generates a self-signed certificate and starts an HTTPS server.

Usage:
    python serve_https.py
    Then open https://<your-pc-ip>:8443 on your phone
    (Accept the browser security warning since it's a self-signed cert)
"""

import http.server
import ssl
import os
import subprocess
import sys

PORT = 8443
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"

def generate_self_signed_cert():
    """Generate a self-signed certificate using Python's ssl module or openssl."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"[✓] Using existing certificate: {CERT_FILE}")
        return

    print("[*] Generating self-signed SSL certificate...")
    
    try:
        # Try using openssl command
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", KEY_FILE, "-out", CERT_FILE,
            "-days", "365", "-nodes",
            "-subj", "/CN=BlindHelper/O=Dev/C=IN"
        ], check=True, capture_output=True)
        print(f"[✓] Certificate generated: {CERT_FILE}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If openssl is not available, use Python to generate the cert
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "BlindHelper"),
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
                .sign(key, hashes.SHA256())
            )
            with open(KEY_FILE, "wb") as f:
                f.write(key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                ))
            with open(CERT_FILE, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            print(f"[✓] Certificate generated using cryptography library")
        except ImportError:
            print("[!] Neither 'openssl' command nor 'cryptography' package available.")
            print("[!] Install cryptography: pip install cryptography")
            print("[!] Or install OpenSSL and add it to PATH")
            sys.exit(1)


def get_local_ip():
    """Try to get the LAN IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    generate_self_signed_cert()

    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("0.0.0.0", PORT), handler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT_FILE, KEY_FILE)
    server.socket = context.wrap_socket(server.socket, server_side=True)

    local_ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  HTTPS Server running!")
    print(f"  Local:   https://localhost:{PORT}")
    print(f"  Network: https://{local_ip}:{PORT}")
    print(f"{'='*50}")
    print(f"\n  On your phone:")
    print(f"  1. Open Chrome/Safari")
    print(f"  2. Go to: https://{local_ip}:{PORT}")
    print(f"  3. Accept the security warning")
    print(f"     (it's safe — self-signed cert)")
    print(f"\n  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        server.server_close()
