#!/bin/sh
set -eu

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl not found"
  echo "Install openssl so github-intake can sign GitHub App JWTs."
  exit 2
fi

openssl version | awk 'NR==1 { print $0 " available" }'
