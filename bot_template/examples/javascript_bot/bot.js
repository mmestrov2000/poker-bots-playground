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
