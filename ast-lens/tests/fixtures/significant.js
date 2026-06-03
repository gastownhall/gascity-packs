/**
 * Module exercising JS significance kinds (App B): arrow functions bound to
 * identifiers (>= 5 lines so they surface) and try/catch with a catch body.
 *
 * Over the 200-LoC threshold so the emitter runs.
 */
import EventEmitter from "events";

export function alpha() {
  const transform = (a, b) => {
    const x = a + b;
    const y = x * 2;
    const z = y - 1;
    return z + extra();
  };
  try {
    risky();
  } catch (err) {
    recover(err);
  }
  return transform;
}

export function bravo() {
  const transform = (a, b) => {
    const x = a + b;
    const y = x * 2;
    const z = y - 1;
    return z + extra();
  };
  try {
    risky();
  } catch (err) {
    recover(err);
  }
  return transform;
}

export function charlie() {
  const transform = (a, b) => {
    const x = a + b;
    const y = x * 2;
    const z = y - 1;
    return z + extra();
  };
  try {
    risky();
  } catch (err) {
    recover(err);
  }
  return transform;
}

export function delta() {
  const transform = (a, b) => {
    const x = a + b;
    const y = x * 2;
    const z = y - 1;
    return z + extra();
  };
  try {
    risky();
  } catch (err) {
    recover(err);
  }
  return transform;
}

export class Bus extends EventEmitter {
  constructor() {
    super();
    this.count = 0;
  }

  tick() {
    this.count += 1;
    return this.count;
  }
}

function extra() {
  return 0;
}

function risky() {
  throw new Error("boom");
}

function recover(_err) {
  return null;
}

export const FILLER_00 = 0;
export const FILLER_01 = 1;
export const FILLER_02 = 2;
export const FILLER_03 = 3;
export const FILLER_04 = 4;
export const FILLER_05 = 5;
export const FILLER_06 = 6;
export const FILLER_07 = 7;
export const FILLER_08 = 8;
export const FILLER_09 = 9;
export const FILLER_10 = 10;
export const FILLER_11 = 11;
export const FILLER_12 = 12;
export const FILLER_13 = 13;
export const FILLER_14 = 14;
export const FILLER_15 = 15;
export const FILLER_16 = 16;
export const FILLER_17 = 17;
export const FILLER_18 = 18;
export const FILLER_19 = 19;
export const FILLER_20 = 20;
export const FILLER_21 = 21;
export const FILLER_22 = 22;
export const FILLER_23 = 23;
export const FILLER_24 = 24;
export const FILLER_25 = 25;
export const FILLER_26 = 26;
export const FILLER_27 = 27;
export const FILLER_28 = 28;
export const FILLER_29 = 29;
export const PAD_000 = 0;
export const PAD_001 = 1;
export const PAD_002 = 2;
export const PAD_003 = 3;
export const PAD_004 = 4;
export const PAD_005 = 5;
export const PAD_006 = 6;
export const PAD_007 = 7;
export const PAD_008 = 8;
export const PAD_009 = 9;
export const PAD_010 = 10;
export const PAD_011 = 11;
export const PAD_012 = 12;
export const PAD_013 = 13;
export const PAD_014 = 14;
export const PAD_015 = 15;
export const PAD_016 = 16;
export const PAD_017 = 17;
export const PAD_018 = 18;
export const PAD_019 = 19;
export const PAD_020 = 20;
export const PAD_021 = 21;
export const PAD_022 = 22;
export const PAD_023 = 23;
export const PAD_024 = 24;
export const PAD_025 = 25;
export const PAD_026 = 26;
export const PAD_027 = 27;
export const PAD_028 = 28;
export const PAD_029 = 29;
export const PAD_030 = 30;
export const PAD_031 = 31;
export const PAD_032 = 32;
export const PAD_033 = 33;
export const PAD_034 = 34;
export const PAD_035 = 35;
export const PAD_036 = 36;
export const PAD_037 = 37;
export const PAD_038 = 38;
export const PAD_039 = 39;
export const PAD_040 = 40;
export const PAD_041 = 41;
export const PAD_042 = 42;
export const PAD_043 = 43;
export const PAD_044 = 44;
export const PAD_045 = 45;
export const PAD_046 = 46;
export const PAD_047 = 47;
export const PAD_048 = 48;
export const PAD_049 = 49;
export const PAD_050 = 50;
export const PAD_051 = 51;
export const PAD_052 = 52;
export const PAD_053 = 53;
export const PAD_054 = 54;
export const PAD_055 = 55;
export const PAD_056 = 56;
export const PAD_057 = 57;
export const PAD_058 = 58;
export const PAD_059 = 59;
export const PAD_060 = 60;
export const PAD_061 = 61;
export const PAD_062 = 62;
export const PAD_063 = 63;
export const PAD_064 = 64;
export const PAD_065 = 65;
export const PAD_066 = 66;
export const PAD_067 = 67;
export const PAD_068 = 68;
export const PAD_069 = 69;
export const PAD_070 = 70;
export const PAD_071 = 71;
export const PAD_072 = 72;
export const PAD_073 = 73;
export const PAD_074 = 74;
export const PAD_075 = 75;
export const PAD_076 = 76;
export const PAD_077 = 77;
export const PAD_078 = 78;
export const PAD_079 = 79;
export const PAD_080 = 80;
export const PAD_081 = 81;
export const PAD_082 = 82;
export const PAD_083 = 83;
export const PAD_084 = 84;
export const PAD_085 = 85;
export const PAD_086 = 86;
export const PAD_087 = 87;
export const PAD_088 = 88;
export const PAD_089 = 89;
export const PAD_090 = 90;
export const PAD_091 = 91;
