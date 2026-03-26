# Bot Examples

This folder contains readable example bots in the current `bot.json` + stdin/stdout format.

- `python_bot/`: the recommended starter bot
- `javascript_bot/`: Node.js example using `["node", "bot.js"]`
- `cpp_bot/`: C++ example that compiles to a bundled Linux executable
- `go_bot/`: Go example that compiles to a bundled Linux executable

What to expect:
- Python and JavaScript examples are source-first examples.
- C++ and Go examples include source plus a build script.
- Compiled examples use `bot.json` with `["./bot"]`, so you build the binary before zipping for upload.

There are no prebuilt upload archives in the repo anymore. Package your chosen example into a `.zip` before uploading.

For language details and runtime caveats, read [../../docs/multi-language-bots.md](../../docs/multi-language-bots.md).
