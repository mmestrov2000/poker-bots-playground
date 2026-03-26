# C++ Bot Example

This example shows the bundled-native-binary pattern.

Use it when:
- you want to write your bot in C++
- you can build a Linux executable before uploading

Files:
- `bot.json`
- `bot.cpp`
- `build-linux.sh`

Typical workflow:
1. Build `./bot` on Linux.
2. Mark it executable.
3. Zip `bot.json` and `bot`.

The upload should contain the compiled `bot` executable, not only the source file.
