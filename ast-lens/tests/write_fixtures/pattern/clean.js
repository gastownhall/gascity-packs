// Already-clean JS: no `console.*` statements and no `var` — every pattern
// intent must return None (nothing to change) on this file.
function add(a, b) {
  const sum = a + b;
  return sum;
}

export { add };
