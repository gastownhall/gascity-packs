// Fixture for the remove-console intent. Has standalone console.log/debug
// statements (which should be dropped) AND a braceless `if` body and a logged
// value used in an assignment (which must be PRESERVED).
function process(items) {
  console.log("starting");
  const out = [];
  for (const it of items) {
    console.debug("item", it);
    out.push(it * 2);
  }
  const n = console.count ? console.count("x") : 0;
  if (out.length === 0) console.log("empty");
  return out;
}

export { process };
