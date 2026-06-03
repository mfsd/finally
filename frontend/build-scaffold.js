
const fs = require("fs");
const path = require("path");
function mkdirp(p) { fs.mkdirSync(p, { recursive: true }); }
function write(p, c) { mkdirp(path.dirname(p)); fs.writeFileSync(p, c); console.log("Created:", p); }
console.log("helper ready");