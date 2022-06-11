#!/bin/bash
set -e

if [[ -z "${BIND_PORT}" ]] && [[ -n "$BIND_IP" ]]; then
  echo "Defaulting to port 8080"
  BIND_PORT=8080
fi

if [[ -n "${PROXY}" ]]; then
  echo "Using proxy: '$PROXY'"
  PROXYARG="--proxy $PROXY"
fi

if [[ -n "${BASE_FOLDER}" ]]; then
  echo "Using base folder: '$BASE_FOLDER'"
  BASEFOLDERARG="--base-folder $BASE_FOLDER"
fi

if [[ -n "${ADV_DL}" ]]; then
  ADVDLARG="--advanced-download"
fi

cd /matterport-dl
/usr/local/bin/python3 matterport-dl.py $M_ID $BIND_IP $BIND_PORT $ADVDLARG $PROXYARG $BASEFOLDERARG
