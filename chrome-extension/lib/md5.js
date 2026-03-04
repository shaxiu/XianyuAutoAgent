// md5.js — Lightweight MD5 hash implementation used for message deduplication and signature verification.
// Self-contained RFC 1321 MD5 — no external dependencies.

// ---------------------------------------------------------------------------
// MD5 core (RFC 1321)
// ---------------------------------------------------------------------------

/**
 * Per-round shift amounts.
 */
const S = [
  7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,  7, 12, 17, 22,
  5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,  5,  9, 14, 20,
  4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,  4, 11, 16, 23,
  6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21,  6, 10, 15, 21
];

/**
 * Pre-computed T table: T[i] = floor(2^32 * abs(sin(i + 1))), i = 0..63
 */
const T = [
  0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
  0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
  0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
  0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
  0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
  0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
  0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
  0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
  0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
  0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
  0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
  0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
  0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
  0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
  0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
  0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391
];

/**
 * Safe 32-bit addition (handles overflow correctly in JS).
 */
function add32(a, b) {
  return (a + b) & 0xffffffff;
}

/**
 * Left-rotate a 32-bit value by n bits.
 */
function rotl(x, n) {
  return ((x << n) | (x >>> (32 - n))) & 0xffffffff;
}

/**
 * Convert a UTF-8 string to a byte array.
 */
function utf8Encode(str) {
  const encoder = new TextEncoder();
  return encoder.encode(str);
}

/**
 * MD5 padding: append 0x80, zero-pad, then append 64-bit little-endian bit length.
 * Returns a Uint8Array whose length is a multiple of 64.
 */
function md5Pad(bytes) {
  const bitLen = bytes.length * 8;
  // Need: original + 1 (0x80) + padding + 8 (length) to be multiple of 64
  let totalLen = bytes.length + 1;
  while (totalLen % 64 !== 56) {
    totalLen++;
  }
  totalLen += 8; // 64-bit length

  const padded = new Uint8Array(totalLen);
  padded.set(bytes);
  padded[bytes.length] = 0x80;

  // Append bit length as 64-bit little-endian
  const view = new DataView(padded.buffer);
  // For messages < 2^32 bytes the high 32 bits of the bit-length are 0
  view.setUint32(totalLen - 8, bitLen & 0xffffffff, true);
  view.setUint32(totalLen - 4, Math.floor(bitLen / 0x100000000) & 0xffffffff, true);

  return padded;
}

/**
 * Process a single 512-bit (64-byte) block.
 * @param {DataView} blockView  DataView over the 64-byte block
 * @param {number} offset       Byte offset into the DataView
 * @param {number[]} state      [a, b, c, d] – mutated in place
 */
function md5Block(blockView, offset, state) {
  let [a, b, c, d] = state;

  // Read 16 little-endian 32-bit words
  const M = new Array(16);
  for (let j = 0; j < 16; j++) {
    M[j] = blockView.getUint32(offset + j * 4, true);
  }

  for (let i = 0; i < 64; i++) {
    let f, g;
    if (i < 16) {
      f = (b & c) | (~b & d);
      g = i;
    } else if (i < 32) {
      f = (d & b) | (~d & c);
      g = (5 * i + 1) % 16;
    } else if (i < 48) {
      f = b ^ c ^ d;
      g = (3 * i + 5) % 16;
    } else {
      f = c ^ (b | ~d);
      g = (7 * i) % 16;
    }
    f = (f & 0xffffffff) >>> 0;

    const temp = d;
    d = c;
    c = b;
    b = add32(b, rotl(add32(add32(a, f), add32(T[i], M[g])), S[i]));
    a = temp;
  }

  state[0] = add32(state[0], a);
  state[1] = add32(state[1], b);
  state[2] = add32(state[2], c);
  state[3] = add32(state[3], d);
}

/**
 * Convert a 32-bit integer to a little-endian hex string (8 chars).
 */
function toLEHex(n) {
  // We need the bytes in little-endian order
  const b0 = (n & 0xff).toString(16).padStart(2, '0');
  const b1 = ((n >>> 8) & 0xff).toString(16).padStart(2, '0');
  const b2 = ((n >>> 16) & 0xff).toString(16).padStart(2, '0');
  const b3 = ((n >>> 24) & 0xff).toString(16).padStart(2, '0');
  return b0 + b1 + b2 + b3;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Compute the MD5 hex digest of a UTF-8 string.
 * @param {string} str
 * @returns {string} 32-character lowercase hex digest
 */
export function md5(str) {
  const bytes = utf8Encode(str);
  const padded = md5Pad(bytes);
  const view = new DataView(padded.buffer);

  // Initial hash state
  const state = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];

  // Process each 64-byte block
  for (let offset = 0; offset < padded.byteLength; offset += 64) {
    md5Block(view, offset, state);
  }

  return toLEHex(state[0]) + toLEHex(state[1]) + toLEHex(state[2]) + toLEHex(state[3]);
}

/**
 * Generate a message ID.
 * Mirrors Python: `f"{random_part}{timestamp} 0"`
 * @returns {string}
 */
export function generateMid() {
  const randomPart = Math.floor(1000 * Math.random());
  const timestamp = Date.now();
  return `${randomPart}${timestamp} 0`;
}

/**
 * Generate a UUID.
 * Mirrors Python: `f"-{timestamp}1"`
 * @returns {string}
 */
export function generateUuid() {
  const timestamp = Date.now();
  return `-${timestamp}1`;
}

/**
 * Generate an API signature.
 * Mirrors Python:
 *   app_key = "34839810"
 *   msg = f"{token}&{t}&{app_key}&{data}"
 *   return md5(msg)
 *
 * @param {string} t     - Timestamp string
 * @param {string} token - Access token
 * @param {string} data  - Request body / data string
 * @returns {string} 32-character lowercase hex MD5 digest
 */
export function generateSign(t, token, data) {
  const appKey = '34839810';
  const msg = `${token}&${t}&${appKey}&${data}`;
  return md5(msg);
}
