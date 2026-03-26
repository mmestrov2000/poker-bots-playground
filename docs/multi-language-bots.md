# Multi-Language Bots

The bot contract is language-agnostic.

Your bot can be written in any language if it can:
- read one JSON object from `stdin`
- write one JSON object to `stdout`
- run from the command declared in `bot.json`

## The Most Important Rule

The command in `bot.json` must be executable in the platform runtime.

Today that means:
- Python `3.12` is guaranteed
- other interpreted languages need their interpreter installed in the runtime
- compiled languages need you to bundle a Linux executable in the zip

If you are playing in the current event, Python is still the safest choice unless the organizers explicitly say that extra runtimes are available.

## Two Common Patterns

### Pattern 1: Interpreter is available

Examples:
- Python: `["python", "bot.py"]`
- JavaScript: `["node", "bot.js"]`
- Ruby: `["ruby", "bot.rb"]`

Use this pattern when the runtime already contains the interpreter.

Your zip usually contains:
- `bot.json`
- your source file
- any extra data files

### Pattern 2: Bundle a native executable

Examples:
- C++
- Go
- Rust

Use this pattern when you compile your bot into a Linux executable and ship that executable inside the zip.

Your zip usually contains:
- `bot.json`
- the compiled executable, usually named `bot`
- optional source files

Example `bot.json`:

```json
{
  "command": ["./bot"],
  "protocol_version": "2.0"
}
```

The platform preserves executable permissions from the uploaded archive, so bundled binaries and executable scripts can run correctly after extraction.

## JavaScript Example

Folder: [`bot/examples/javascript_bot/`](../bot/examples/javascript_bot/)

`bot.json`:

```json
{
  "command": ["node", "bot.js"],
  "protocol_version": "2.0"
}
```

`bot.js`:

```javascript
const fs = require("fs");

const state = JSON.parse(fs.readFileSync(0, "utf8"));
const legal = new Set(state.legal_actions.map((entry) => entry.action));

let response;
if (legal.has("check")) {
  response = { action: "check" };
} else if (legal.has("call")) {
  response = { action: "call" };
} else {
  response = { action: "fold" };
}

process.stdout.write(JSON.stringify(response) + "\n");
```

Use JavaScript when:
- Node.js is available in the platform runtime
- you prefer quick scripting over compiled binaries

Packaging:

```bash
zip -r js-bot.zip bot.json bot.js
```

Important:
- This will not run on the current platform image unless Node.js is installed there.

## C++ Example

Folder: [`bot/examples/cpp_bot/`](../bot/examples/cpp_bot/)

`bot.json`:

```json
{
  "command": ["./bot"],
  "protocol_version": "2.0"
}
```

Build the binary on Linux:

```bash
g++ -O2 -std=c++17 -o bot bot.cpp
chmod +x bot
zip -r cpp-bot.zip bot.json bot
```

Use C++ when:
- you want a fast native executable
- you can build for Linux before uploading

Important:
- Build for the same environment style the server uses: Linux, 64-bit.
- If you are on Windows, build inside WSL, Docker, or a Linux machine.
- Upload the compiled `bot` binary, not only `bot.cpp`.

## Go Example

Folder: [`bot/examples/go_bot/`](../bot/examples/go_bot/)

`bot.json`:

```json
{
  "command": ["./bot"],
  "protocol_version": "2.0"
}
```

Build the binary on Linux:

```bash
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o bot bot.go
chmod +x bot
zip -r go-bot.zip bot.json bot
```

Use Go when:
- you want easy static binaries
- you want simpler native deployment than C++

## What About Other Languages?

The same ideas apply:

- Ruby: `["ruby", "bot.rb"]`
- PHP: `["php", "bot.php"]`
- Java: `["java", "-jar", "bot.jar"]`
- Rust: compile a Linux binary and use `["./bot"]`

If the runtime can execute your command, the platform does not care which language you used.

## Local Testing Rule

No matter the language, the local test is the same idea:

```bash
<your command> < bot/fixtures/sample_v2_state.json
```

Examples:

```bash
python bot.py < ../fixtures/sample_v2_state.json
node bot.js < ../fixtures/sample_v2_state.json
./bot < ../fixtures/sample_v2_state.json
```

## Recommendation

For the current event:
- choose Python if you want the smoothest path
- choose JavaScript only if Node.js is confirmed in the runtime
- choose C++ or Go only if you are comfortable building a Linux executable before upload
