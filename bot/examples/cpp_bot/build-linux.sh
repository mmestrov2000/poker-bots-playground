#!/usr/bin/env sh
set -eu

g++ -O2 -std=c++17 -o bot bot.cpp
chmod +x bot
