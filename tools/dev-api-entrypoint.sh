#!/bin/sh
set -eu

bundle=/tmp/izo-dev-ca.pem
cp /etc/ssl/certs/ca-certificates.crt "$bundle"
if [ -d /run/izo-dev-ca ]; then
  for certificate in /run/izo-dev-ca/*.crt; do
    [ -f "$certificate" ] || continue
    cat "$certificate" >> "$bundle"
    printf "\n" >> "$bundle"
  done
fi
export SSL_CERT_FILE="$bundle"
exec "$@"
