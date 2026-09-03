import { test } from "node:test";
import assert from "node:assert/strict";
import { mormToBaseUnits, formatBaseUnits } from "../src/units.js";

test("base=1: integer MORM maps 1:1, fractions rejected", () => {
  assert.equal(mormToBaseUnits("5", 1), 5n);
  assert.equal(mormToBaseUnits("1000000", 1), 1000000n);
  assert.throws(() => mormToBaseUnits("1.5", 1)); // no sub-MORM when base=1
});

test("base=1e6: 6 decimals exact, 7th rejected", () => {
  assert.equal(mormToBaseUnits("1", 1_000_000), 1_000_000n);
  assert.equal(mormToBaseUnits("0.5", 1_000_000), 500_000n);
  assert.equal(mormToBaseUnits("12.345678", 1_000_000), 12_345_678n);
  assert.throws(() => mormToBaseUnits("0.0000001", 1_000_000));
});

test("huge amounts stay exact (BigInt)", () => {
  assert.equal(mormToBaseUnits("99999999999999999999", 1), 99999999999999999999n);
});

test("rejects non-positive / bad format", () => {
  assert.throws(() => mormToBaseUnits("0", 1));
  assert.throws(() => mormToBaseUnits("-3", 1));
  assert.throws(() => mormToBaseUnits("abc", 1));
});

test("formatBaseUnits round-trips and trims zeros", () => {
  assert.equal(formatBaseUnits(5n, 1), "5");
  assert.equal(formatBaseUnits(500000n, 1_000_000), "0.5");
  assert.equal(formatBaseUnits(12_345_678n, 1_000_000), "12.345678");
  assert.equal(formatBaseUnits(1_000_000n, 1_000_000), "1");
  assert.equal(formatBaseUnits(99999999999999999999n, 1), "99999999999999999999");
});
