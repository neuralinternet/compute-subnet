#!/bin/bash

#############################################################
# for generating root CA, server, client private key and cert
#############################################################

ca_key_bits="4096"
ca_cert_expire_days="365"
pem_password="bittensor"

echo "1.1. generate root CA"
openssl req -newkey rsa:"$ca_key_bits" -keyform PEM -keyout ca.key -x509 --days "$ca_cert_expire_days" -outform PEM -passout pass:"$pem_password" -out ca.cer -subj "/C=US/ST=NY/CN=NI/O=NI"

#for register_api server
echo "2.1 Generate a server private key."
openssl genrsa -out server.key "$ca_key_bits"

echo "2.2 Use the server private key to generate a certificate generation request."
openssl req -new -key server.key -out server.req -sha256 -subj "/C=US/ST=NY/CN=NI/O=NI"

echo "2.3 Use the certificate generation request and the CA cert to generate the server cert."
openssl x509 -req -in server.req -CA ca.cer -CAkey ca.key -set_serial 100 -days "$ca_cert_expire_days" -outform PEM -passin pass:"$pem_password" -out server.cer -sha256

echo "2.4 Convert the cer to PEM CRT format"
openssl x509 -inform PEM -in server.cer -out server.crt

echo "2.5 Clean up – now that the cert has been created, we no longer need the request"
rm server.req

#for frontend server
echo "3.1 Generate a client private key."
openssl genrsa -out client.key "$ca_key_bits"

echo "3.2 Use the client private key to generate a certificate generation request."
openssl req -new -key client.key -out client.req -subj "/C=US/ST=NY/CN=NI/O=NI"

echo "3.3 Use the certificate generation request and the CA cert to generate the client cert."
openssl x509 -req -in client.req -CA ca.cer -CAkey ca.key -set_serial 101 -days "$ca_cert_expire_days" -outform PEM -out client.cer -passin pass:"$pem_password" -extensions v3_req -extfile <(
cat << EOF
[ v3_req ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = 127.0.0.1
DNS.2 = 0.0.0.0
DNS.3 = localhost
EOF
)

echo "3.4 Convert the client certificate and private key to pkcs#12 format for use by browsers."
openssl pkcs12 -export -inkey client.key -in client.cer -out client.p12 -passout pass:"$pem_password"

echo "3.5. Convert the cer to PEM CRT format"
openssl x509 -inform PEM -in client.cer -out client.crt

echo "3.6. Clean up – now that the cert has been created, we no longer need the request."
rm client.req