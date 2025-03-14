#!/bin/bash
# Generate a self-signed certificate for HTTP/2 testing
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"