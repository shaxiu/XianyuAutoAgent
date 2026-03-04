// msgpack-decoder.js — Decodes MessagePack binary payloads from Goofish WebSocket frames into JavaScript objects.

/**
 * Pure JavaScript MessagePack decoder.
 * Ported from Python MessagePackDecoder in utils/xianyu_utils.py.
 *
 * Operates on Uint8Array input and uses DataView for big-endian multi-byte reads.
 * Strings are decoded with TextDecoder (UTF-8).
 * Binary (bin) types are returned as Uint8Array slices.
 * 64-bit integers use BigInt (DataView.getBigUint64 / getBigInt64).
 */

const _textDecoder = new TextDecoder('utf-8');

class MessagePackDecoder {
  /**
   * @param {Uint8Array} data
   */
  constructor(data) {
    this.data = data;
    this.view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    this.pos = 0;
    this.length = data.byteLength;
  }

  // ---------------------------------------------------------------------------
  // Low-level readers
  // ---------------------------------------------------------------------------

  readByte() {
    if (this.pos >= this.length) {
      throw new Error('Unexpected end of data');
    }
    return this.data[this.pos++];
  }

  readBytes(count) {
    if (this.pos + count > this.length) {
      throw new Error('Unexpected end of data');
    }
    const slice = this.data.subarray(this.pos, this.pos + count);
    this.pos += count;
    return slice;
  }

  readUint8() {
    return this.readByte();
  }

  readUint16() {
    const val = this.view.getUint16(this.pos, false); // big-endian
    this.pos += 2;
    return val;
  }

  readUint32() {
    const val = this.view.getUint32(this.pos, false);
    this.pos += 4;
    return val;
  }

  readUint64() {
    const val = this.view.getBigUint64(this.pos, false);
    this.pos += 8;
    return val;
  }

  readInt8() {
    const val = this.view.getInt8(this.pos);
    this.pos += 1;
    return val;
  }

  readInt16() {
    const val = this.view.getInt16(this.pos, false);
    this.pos += 2;
    return val;
  }

  readInt32() {
    const val = this.view.getInt32(this.pos, false);
    this.pos += 4;
    return val;
  }

  readInt64() {
    const val = this.view.getBigInt64(this.pos, false);
    this.pos += 8;
    return val;
  }

  readFloat32() {
    const val = this.view.getFloat32(this.pos, false);
    this.pos += 4;
    return val;
  }

  readFloat64() {
    const val = this.view.getFloat64(this.pos, false);
    this.pos += 8;
    return val;
  }

  readString(length) {
    const bytes = this.readBytes(length);
    return _textDecoder.decode(bytes);
  }

  // ---------------------------------------------------------------------------
  // Composite decoders
  // ---------------------------------------------------------------------------

  decodeArray(size) {
    const arr = [];
    for (let i = 0; i < size; i++) {
      arr.push(this.decodeValue());
    }
    return arr;
  }

  decodeMap(size) {
    const map = {};
    for (let i = 0; i < size; i++) {
      const key = this.decodeValue();
      const value = this.decodeValue();
      map[key] = value;
    }
    return map;
  }

  // ---------------------------------------------------------------------------
  // Main entry: decode a single MessagePack value
  // ---------------------------------------------------------------------------

  decodeValue() {
    if (this.pos >= this.length) {
      throw new Error('Unexpected end of data');
    }

    const fmt = this.readByte();

    // Positive fixint (0x00 - 0x7f)
    if (fmt <= 0x7f) return fmt;

    // Fixmap (0x80 - 0x8f)
    if (fmt >= 0x80 && fmt <= 0x8f) return this.decodeMap(fmt & 0x0f);

    // Fixarray (0x90 - 0x9f)
    if (fmt >= 0x90 && fmt <= 0x9f) return this.decodeArray(fmt & 0x0f);

    // Fixstr (0xa0 - 0xbf)
    if (fmt >= 0xa0 && fmt <= 0xbf) return this.readString(fmt & 0x1f);

    switch (fmt) {
      // nil
      case 0xc0: return null;
      // (unused) 0xc1
      // false / true
      case 0xc2: return false;
      case 0xc3: return true;

      // bin 8 / 16 / 32
      case 0xc4: return this.readBytes(this.readUint8());
      case 0xc5: return this.readBytes(this.readUint16());
      case 0xc6: return this.readBytes(this.readUint32());

      // ext 8 / 16 / 32 (skip type byte + data)
      case 0xc7: { const sz = this.readUint8();  this.readByte(); return this.readBytes(sz); }
      case 0xc8: { const sz = this.readUint16(); this.readByte(); return this.readBytes(sz); }
      case 0xc9: { const sz = this.readUint32(); this.readByte(); return this.readBytes(sz); }

      // float 32 / 64
      case 0xca: return this.readFloat32();
      case 0xcb: return this.readFloat64();

      // uint 8 / 16 / 32 / 64
      case 0xcc: return this.readUint8();
      case 0xcd: return this.readUint16();
      case 0xce: return this.readUint32();
      case 0xcf: return this.readUint64();

      // int 8 / 16 / 32 / 64
      case 0xd0: return this.readInt8();
      case 0xd1: return this.readInt16();
      case 0xd2: return this.readInt32();
      case 0xd3: return this.readInt64();

      // fixext 1 / 2 / 4 / 8 / 16
      case 0xd4: this.readByte(); return this.readBytes(1);
      case 0xd5: this.readByte(); return this.readBytes(2);
      case 0xd6: this.readByte(); return this.readBytes(4);
      case 0xd7: this.readByte(); return this.readBytes(8);
      case 0xd8: this.readByte(); return this.readBytes(16);

      // str 8 / 16 / 32
      case 0xd9: return this.readString(this.readUint8());
      case 0xda: return this.readString(this.readUint16());
      case 0xdb: return this.readString(this.readUint32());

      // array 16 / 32
      case 0xdc: return this.decodeArray(this.readUint16());
      case 0xdd: return this.decodeArray(this.readUint32());

      // map 16 / 32
      case 0xde: return this.decodeMap(this.readUint16());
      case 0xdf: return this.decodeMap(this.readUint32());

      default:
        break;
    }

    // Negative fixint (0xe0 - 0xff)
    if (fmt >= 0xe0) return fmt - 256;

    throw new Error(`Unknown MessagePack format byte: 0x${fmt.toString(16).padStart(2, '0')}`);
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  decode() {
    try {
      return this.decodeValue();
    } catch (_err) {
      // Fallback: return base64-encoded raw data (mirrors Python behaviour)
      return uint8ArrayToBase64(this.data);
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Convert a Uint8Array to a base64 string.
 * Works in both browser (btoa) and service-worker contexts.
 * @param {Uint8Array} bytes
 * @returns {string}
 */
function uint8ArrayToBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Convert a base64 string to a Uint8Array.
 * @param {string} base64
 * @returns {Uint8Array}
 */
function base64ToUint8Array(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Custom JSON replacer that converts Uint8Array and BigInt values to
 * serialisable forms (matching the Python json_serializer behaviour).
 */
function jsonReplacer(_key, value) {
  if (value instanceof Uint8Array) {
    // Try to interpret as UTF-8 text; fall back to base64
    try {
      return _textDecoder.decode(value);
    } catch {
      return uint8ArrayToBase64(value);
    }
  }
  if (typeof value === 'bigint') {
    // If the BigInt fits safely in a Number, convert; otherwise stringify
    if (value >= Number.MIN_SAFE_INTEGER && value <= Number.MAX_SAFE_INTEGER) {
      return Number(value);
    }
    return value.toString();
  }
  return value;
}

// ---------------------------------------------------------------------------
// Public exports
// ---------------------------------------------------------------------------

/**
 * Decode a MessagePack-encoded Uint8Array into a JavaScript value.
 * @param {Uint8Array} uint8Array
 * @returns {*} Decoded JS value (object, array, string, number, etc.)
 */
export function decodeMsgpack(uint8Array) {
  const decoder = new MessagePackDecoder(uint8Array);
  return decoder.decode();
}

/**
 * Decrypt a base64-encoded, MessagePack-encoded string into a JS object.
 * Mirrors the Python `decrypt()` function from utils/xianyu_utils.py.
 *
 * Steps:
 *   1. Clean + pad the base64 input
 *   2. Base64-decode to bytes
 *   3. MessagePack-decode the bytes
 *   4. Return the decoded JS object (with Uint8Array / BigInt normalised via JSON round-trip)
 *
 * On failure at any stage a best-effort result or error object is returned.
 *
 * @param {string} dataStr - base64-encoded MessagePack data
 * @returns {string} JSON string of the decoded result (matches Python's return type)
 */
export function decrypt(dataStr) {
  try {
    // 1. Clean non-base64 characters and pad
    let cleaned = '';
    const validChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    for (let i = 0; i < dataStr.length; i++) {
      if (validChars.indexOf(dataStr[i]) !== -1) {
        cleaned += dataStr[i];
      }
    }
    while (cleaned.length % 4 !== 0) {
      cleaned += '=';
    }

    // 2. Base64 decode
    let decodedBytes;
    try {
      decodedBytes = base64ToUint8Array(cleaned);
    } catch (e) {
      return JSON.stringify({ error: `Base64 decode failed: ${e.message}`, raw_data: dataStr });
    }

    // 3. MessagePack decode
    try {
      const decoder = new MessagePackDecoder(decodedBytes);
      const result = decoder.decodeValue();

      // 4. Serialise to JSON with custom replacer (handles Uint8Array, BigInt)
      return JSON.stringify(result, jsonReplacer);
    } catch (e) {
      // If msgpack fails, try interpreting as plain UTF-8 text
      try {
        const textResult = _textDecoder.decode(decodedBytes);
        return JSON.stringify({ text: textResult });
      } catch {
        // Last resort: hex representation
        let hex = '';
        for (let i = 0; i < decodedBytes.byteLength; i++) {
          hex += decodedBytes[i].toString(16).padStart(2, '0');
        }
        return JSON.stringify({ hex, error: `Decode failed: ${e.message}` });
      }
    }
  } catch (e) {
    return JSON.stringify({ error: `Decrypt failed: ${e.message}`, raw_data: dataStr });
  }
}
