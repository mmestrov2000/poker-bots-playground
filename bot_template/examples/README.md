# Bot Examples

This folder contains readable example bots in the current `bot.json` + stdin/stdout format.

- Python examples:
  - `random_bot/`: chooses randomly from legal actions
  - `aggressive_bot/`: prefers betting and raising
  - `conservative_bot/`: prefers checking and cheap calls
- Additional language examples:
  - `javascript_bot/`: Node.js example using `["node", "bot.js"]`
  - `cpp_bot/`: C++ example that compiles to a bundled Linux executable
  - `go_bot/`: Go example that compiles to a bundled Linux executable

What to expect:
- Python and JavaScript examples are source-first examples.
- C++ and Go examples include source plus a build script.
- Compiled examples use `bot.json` with `["./bot"]`, so you build the binary before zipping for upload.

If you want something upload-ready right now, use the Python ZIP files in [`../bots/`](../bots/).
For language details and runtime caveats, read [../../docs/multi-language-bots.md](../../docs/multi-language-bots.md).
