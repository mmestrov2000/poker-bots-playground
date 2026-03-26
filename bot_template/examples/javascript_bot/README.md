# JavaScript Bot Example

This example shows the same stdin/stdout contract using Node.js.

Use it when:
- Node.js is installed in the platform runtime
- you want an interpreted alternative to Python

Package layout:
- `bot.json`
- `bot.js`

Manifest command:

```json
["node", "bot.js"]
```

If the current event runtime does not include Node.js, this example is still useful as a reference but it will not run until Node.js is added to the platform image.
