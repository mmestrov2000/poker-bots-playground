#!/usr/bin/env sh
set -eu

CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o bot bot.go
chmod +x bot
