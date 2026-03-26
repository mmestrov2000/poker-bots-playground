# Go Bot Example

This example shows the bundled-native-binary pattern using Go.

Use it when:
- you want a compiled language with simple deployment
- you can build a Linux binary before uploading

Files:
- `bot.json`
- `bot.go`
- `build-linux.sh`

Typical workflow:
1. Build `./bot` for Linux.
2. Mark it executable.
3. Zip `bot.json` and `bot`.
