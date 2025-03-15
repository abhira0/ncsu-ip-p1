import os
import asyncio
import datetime
import subprocess
from hypercorn.config import Config
from hypercorn.asyncio import serve
from quart import Quart, send_file, make_response

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa

app = Quart(__name__)

@app.route('/<filename>')
async def serve_file(filename):
    files_dir = os.path.abspath("./files")
    file_path = os.path.join(files_dir, filename)

    if not os.path.exists(file_path):
        return {"error": f"File {filename} not found"}, 404

    response = await send_file(file_path)
    # Add Cache-Control headers to prevent caching
    response = await make_response(response)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response

def create_self_signed_cert(cert_file, key_file):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    
    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    print(f"Generated self-signed certificate at {cert_file} and key at {key_file}")

def ensure_certs():
    cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")
    cert_file = os.path.join(cert_dir, "cert.pem")
    key_file = os.path.join(cert_dir, "key.pem")
    
    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        print("Certificates not found. Generating new self-signed certificates using Python...")
        os.makedirs(cert_dir, exist_ok=True)
        create_self_signed_cert(cert_file, key_file)

def main():
    ensure_certs()
    
    config = Config()
    config.bind = ["0.0.0.0:8443"]
    config.h2_protocol = True
    config.use_reloader = True
    config.certfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs/cert.pem")
    config.keyfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs/key.pem")
    
    print(f"Starting HTTPS (HTTP/2) server on https://0.0.0.0:8443")
    print(f"Using certificate: {config.certfile}")
    print(f"Using key: {config.keyfile}\n")
    
    asyncio.run(serve(app, config))

main()
