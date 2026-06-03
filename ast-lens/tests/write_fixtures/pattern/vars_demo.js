// Fixture for the no-var intent. Mixes `var` (rewritten to `let`), an existing
// `let`/`const` (left alone), a multi-declarator `var` and a `for (var …)` —
// all of which must keep their semicolons, extra declarators and structure.
var total = 0;
const FACTOR = 2;
var a = 1, b = 2;
for (var i = 0; i < 3; i++) {
  total += i * FACTOR;
}
let result = total + a + b;
export { result };
