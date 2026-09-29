/**
 * Remove the flat white backdrop baked into the DSH mascot artwork and rebuild
 * a multi-size Windows .ico from the result.
 *
 *   node tools/remove_white_bg_icon.mjs            # write assets/
 *   node tools/remove_white_bg_icon.mjs --dry-run  # only write a preview elsewhere
 *
 * The source artwork (assets/dsh-mascot.png) is a 256x256 RGBA image whose
 * background is opaque pure white, so the desktop shortcut showed a white
 * square behind the character.  Only pixels that are *connected to the image
 * border* through near-white pixels are treated as background, therefore white
 * areas enclosed by the character (apron, headdress, highlights) survive.
 *
 * Self-contained: PNG decode/encode via zlib, no third-party dependencies.
 */

import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE); // projects/ai4s-thin-film-mlp
const ASSETS = path.join(ROOT, 'assets');

const SRC_PNG = path.join(ASSETS, 'dsh-mascot.png');
const OUT_PNG = path.join(ASSETS, 'dsh-mascot.png');
const OUT_ICO = path.join(ASSETS, 'dsh-mascot.ico');

const ICO_SIZES = [16, 24, 32, 48, 64, 128, 256];
/** <= this size is stored as a classic BMP/DIB entry (widest compatibility). */
const DIB_MAX = 256;

// --------------------------------------------------------------------- PNG

function decodePng(buf) {
  if (buf.readUInt32BE(0) !== 0x89504e47) throw new Error('not a PNG');
  let off = 8;
  let ihdr = null;
  const idat = [];
  let plte = null;
  let trns = null;

  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('ascii', off + 4, off + 8);
    const data = buf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') {
      ihdr = {
        width: data.readUInt32BE(0),
        height: data.readUInt32BE(4),
        depth: data[8],
        colorType: data[9],
        interlace: data[12],
      };
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'PLTE') plte = Buffer.from(data);
    else if (type === 'tRNS') trns = Buffer.from(data);
    else if (type === 'IEND') break;
    off += 12 + len;
  }
  if (!ihdr) throw new Error('missing IHDR');
  if (ihdr.depth !== 8) throw new Error(`unsupported bit depth ${ihdr.depth}`);
  if (ihdr.interlace !== 0) throw new Error('interlaced PNG not supported');

  const channels = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ihdr.colorType];
  if (!channels) throw new Error(`unsupported color type ${ihdr.colorType}`);

  const raw = zlib.inflateSync(Buffer.concat(idat));
  const { width: w, height: h } = ihdr;
  const stride = w * channels;
  const px = Buffer.alloc(stride * h);

  let p = 0;
  for (let y = 0; y < h; y++) {
    const filter = raw[p++];
    const line = raw.subarray(p, p + stride);
    p += stride;
    const cur = px.subarray(y * stride, (y + 1) * stride);
    const prev = y > 0 ? px.subarray((y - 1) * stride, y * stride) : null;

    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? cur[x - channels] : 0;
      const b = prev ? prev[x] : 0;
      const c = prev && x >= channels ? prev[x - channels] : 0;
      let v = line[x];
      switch (filter) {
        case 0: break;
        case 1: v += a; break;
        case 2: v += b; break;
        case 3: v += (a + b) >> 1; break;
        case 4: {
          const pp = a + b - c;
          const pa = Math.abs(pp - a);
          const pb = Math.abs(pp - b);
          const pc = Math.abs(pp - c);
          v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
          break;
        }
        default: throw new Error(`bad filter ${filter}`);
      }
      cur[x] = v & 0xff;
    }
  }

  const rgba = Buffer.alloc(w * h * 4);
  for (let i = 0, n = w * h; i < n; i++) {
    let r, g, b, al = 255;
    switch (ihdr.colorType) {
      case 0: r = g = b = px[i]; break;
      case 2: r = px[i * 3]; g = px[i * 3 + 1]; b = px[i * 3 + 2]; break;
      case 3: {
        const idx = px[i];
        r = plte[idx * 3]; g = plte[idx * 3 + 1]; b = plte[idx * 3 + 2];
        if (trns && idx < trns.length) al = trns[idx];
        break;
      }
      case 4: r = g = b = px[i * 2]; al = px[i * 2 + 1]; break;
      default: r = px[i * 4]; g = px[i * 4 + 1]; b = px[i * 4 + 2]; al = px[i * 4 + 3]; break;
    }
    rgba[i * 4] = r; rgba[i * 4 + 1] = g; rgba[i * 4 + 2] = b; rgba[i * 4 + 3] = al;
  }
  return { width: w, height: h, data: rgba };
}

function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c = (crc ^ buf[i]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, 'ascii');
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}

function encodePng(width, height, rgba) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;

  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0; // filter: none
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// -------------------------------------------------------- background removal

const LOOSE_MIN = 150; // min(R,G,B) at/above which a border-connected pixel counts as backdrop
const HARD_MIN = 246;  // definitely pure backdrop -> fully transparent
const HARD_SAT = 8;    // ...and near-neutral

function removeWhiteBackground(img) {
  const { width: w, height: h, data } = img;
  const n = w * h;

  const minCh = new Uint8Array(n);
  const sat = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const r = data[i * 4], g = data[i * 4 + 1], b = data[i * 4 + 2];
    minCh[i] = Math.min(r, g, b);
    sat[i] = Math.max(r, g, b) - minCh[i];
  }

  // Multi-source flood fill from the border across "light enough" pixels.
  // Pixels that are already translucent are treated as foreground, which makes
  // re-running on an already-processed file a no-op (no double un-blending).
  const bg = new Uint8Array(n);
  const queue = new Int32Array(n);
  let qh = 0, qt = 0;
  const push = (i) => {
    if (!bg[i] && data[i * 4 + 3] === 255 && minCh[i] >= LOOSE_MIN) { bg[i] = 1; queue[qt++] = i; }
  };
  for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x); }
  for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1); }
  while (qh < qt) {
    const i = queue[qh++];
    const x = i % w, y = (i / w) | 0;
    if (x > 0) push(i - 1);
    if (x < w - 1) push(i + 1);
    if (y > 0) push(i - w);
    if (y < h - 1) push(i + w);
  }

  // Nearest core (fully foreground) pixel, to learn the foreground's darkest
  // channel and therefore how much white the edge pixels are blended with.
  const coreMin = new Uint8Array(n).fill(255);
  const seen = new Uint8Array(n);
  qh = qt = 0;
  for (let i = 0; i < n; i++) {
    if (!bg[i]) { seen[i] = 1; coreMin[i] = minCh[i]; queue[qt++] = i; }
  }
  while (qh < qt) {
    const i = queue[qh++];
    const x = i % w, y = (i / w) | 0;
    const nb = [x > 0 ? i - 1 : -1, x < w - 1 ? i + 1 : -1, y > 0 ? i - w : -1, y < h - 1 ? i + w : -1];
    for (const j of nb) {
      if (j >= 0 && !seen[j]) { seen[j] = 1; coreMin[j] = coreMin[i]; queue[qt++] = j; }
    }
  }

  let cleared = 0, softened = 0;
  const out = Buffer.from(data);
  for (let i = 0; i < n; i++) {
    if (!bg[i]) continue; // interior / character pixel: untouched

    const mn = minCh[i];
    if (mn >= HARD_MIN && sat[i] <= HARD_SAT) {
      out[i * 4 + 3] = 0;
      cleared++;
      continue;
    }

    // Un-blend: observed = a*F + (1-a)*255  =>  a = (255 - mn) / (255 - min(F))
    const denom = Math.max(1, 255 - coreMin[i]);
    let a = (255 - mn) / denom;
    if (!(a > 0)) a = 0;
    if (a > 1) a = 1;

    if (a < 0.02) {
      out[i * 4 + 3] = 0;
      cleared++;
      continue;
    }
    const inv = (1 - a) * 255;
    for (let c = 0; c < 3; c++) {
      const v = (out[i * 4 + c] - inv) / a;
      out[i * 4 + c] = v < 0 ? 0 : v > 255 ? 255 : Math.round(v);
    }
    out[i * 4 + 3] = Math.round(a * 255);
    softened++;
  }
  return { rgba: out, cleared, softened, bgCount: cleared + softened };
}

// ------------------------------------------------------------------ scaling

/** Area-average downscale on premultiplied alpha (avoids dark/white halos). */
function downscale(img, size) {
  const { width: sw, height: sh, data } = img;
  const out = Buffer.alloc(size * size * 4);
  const sx = sw / size, sy = sh / size;
  for (let y = 0; y < size; y++) {
    const y0 = Math.floor(y * sy), y1 = Math.max(y0 + 1, Math.floor((y + 1) * sy));
    for (let x = 0; x < size; x++) {
      const x0 = Math.floor(x * sx), x1 = Math.max(x0 + 1, Math.floor((x + 1) * sx));
      let r = 0, g = 0, b = 0, a = 0, cnt = 0;
      for (let yy = y0; yy < y1 && yy < sh; yy++) {
        for (let xx = x0; xx < x1 && xx < sw; xx++) {
          const i = (yy * sw + xx) * 4;
          const al = data[i + 3] / 255;
          r += data[i] * al; g += data[i + 1] * al; b += data[i + 2] * al; a += al;
          cnt++;
        }
      }
      const o = (y * size + x) * 4;
      if (cnt === 0 || a === 0) { out[o + 3] = 0; continue; }
      out[o] = Math.min(255, Math.round(r / a));
      out[o + 1] = Math.min(255, Math.round(g / a));
      out[o + 2] = Math.min(255, Math.round(b / a));
      out[o + 3] = Math.round((a / cnt) * 255);
    }
  }
  return { width: size, height: size, data: out };
}

// ---------------------------------------------------------------------- ICO

function dibEntry(img) {
  const { width: w, height: h, data } = img;
  const header = Buffer.alloc(40);
  header.writeUInt32LE(40, 0);
  header.writeInt32LE(w, 4);
  header.writeInt32LE(h * 2, 8); // XOR bitmap + AND mask
  header.writeUInt16LE(1, 12);
  header.writeUInt16LE(32, 14);
  header.writeUInt32LE(0, 16); // BI_RGB

  const xor = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) {
    const src = (h - 1 - y) * w * 4; // bottom-up
    for (let x = 0; x < w; x++) {
      const s = src + x * 4, d = (y * w + x) * 4;
      xor[d] = data[s + 2]; xor[d + 1] = data[s + 1]; xor[d + 2] = data[s]; xor[d + 3] = data[s + 3];
    }
  }
  const maskStride = Math.ceil(w / 32) * 4;
  const mask = Buffer.alloc(maskStride * h); // all zero: alpha channel decides
  return Buffer.concat([header, xor, mask]);
}

function buildIco(master) {
  const entries = [];
  for (const size of ICO_SIZES) {
    const scaled = size === master.width ? master : downscale(master, size);
    const payload = size <= DIB_MAX ? dibEntry(scaled) : encodePng(size, size, scaled.data);
    entries.push({ size, payload });
  }
  const header = Buffer.alloc(6 + entries.length * 16);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(entries.length, 4);
  let offset = header.length;
  entries.forEach((e, i) => {
    const o = 6 + i * 16;
    header[o] = e.size >= 256 ? 0 : e.size;
    header[o + 1] = e.size >= 256 ? 0 : e.size;
    header[o + 2] = 0; header[o + 3] = 0;
    header.writeUInt16LE(1, o + 4);
    header.writeUInt16LE(32, o + 6);
    header.writeUInt32LE(e.payload.length, o + 8);
    header.writeUInt32LE(offset, o + 12);
    offset += e.payload.length;
  });
  return Buffer.concat([header, ...entries.map((e) => e.payload)]);
}

// --------------------------------------------------------------------- main

const dryRun = process.argv.includes('--dry-run');
const src = decodePng(fs.readFileSync(SRC_PNG));
console.log(`source  ${src.width}x${src.height} RGBA`);

// Anything already transparent is left alone; this is idempotent.
const opaque = src.data.some((_, i) => i % 4 === 3 && src.data[i] === 255);
if (!opaque) console.log('note: source already has transparency, processing anyway');

const { rgba, cleared, softened } = removeWhiteBackground(src);
const total = src.width * src.height;
console.log(`backdrop removed: ${cleared} fully transparent, ${softened} edge pixels softened ` +
            `(${(((cleared + softened) / total) * 100).toFixed(1)}% of the canvas)`);

const master = { width: src.width, height: src.height, data: rgba };
const ico = buildIco(master);

/** Composite over a checkerboard so transparency is visible to the naked eye. */
function checker(img, cell = 16) {
  const { width: w, height: h, data } = img;
  const out = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const dark = ((x / cell) | 0) % 2 === ((y / cell) | 0) % 2;
      const base = dark ? 90 : 200;
      const a = data[i + 3] / 255;
      for (let c = 0; c < 3; c++) out[i + c] = Math.round(data[i + c] * a + base * (1 - a));
      out[i + 3] = 255;
    }
  }
  return { width: w, height: h, data: out };
}

if (dryRun) {
  const dir = path.join(ASSETS, 'backup');
  fs.writeFileSync(path.join(dir, 'dsh-mascot.nobg-preview.png'), encodePng(master.width, master.height, rgba));
  const cb = checker(master);
  fs.writeFileSync(path.join(dir, 'dsh-mascot.nobg-checker.png'), encodePng(cb.width, cb.height, cb.data));
  console.log(`dry run: wrote ${path.relative(ROOT, path.join(dir, 'dsh-mascot.nobg-preview.png'))}`);
  console.log(`dry run: wrote ${path.relative(ROOT, path.join(dir, 'dsh-mascot.nobg-checker.png'))}`);

  // Quantitative edge audit: is any near-white opaque pixel left touching the
  // transparent area (that would read as a white halo on the desktop)?
  const w = master.width, h = master.height;
  let fringe = 0, maxFringe = 0, interiorWhite = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      if (rgba[i + 3] === 0) continue;
      const mn = Math.min(rgba[i], rgba[i + 1], rgba[i + 2]);
      const st = Math.max(rgba[i], rgba[i + 1], rgba[i + 2]) - mn;
      let touches = false;
      for (let dy = -1; dy <= 1 && !touches; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
          if (rgba[(ny * w + nx) * 4 + 3] === 0) { touches = true; break; }
        }
      }
      if (touches) {
        if (mn >= 235 && st <= 12) { fringe++; maxFringe = Math.max(maxFringe, mn); }
      } else if (mn >= 245 && st <= 8) interiorWhite++;
    }
  }
  console.log(`edge audit: ${fringe} near-white pixels still touch transparency, ` +
              `${interiorWhite} enclosed white pixels preserved`);
} else {
  fs.writeFileSync(OUT_PNG, encodePng(master.width, master.height, rgba));
  fs.writeFileSync(OUT_ICO, ico);
  console.log(`wrote ${path.relative(ROOT, OUT_PNG)} (${fs.statSync(OUT_PNG).size} bytes)`);
  console.log(`wrote ${path.relative(ROOT, OUT_ICO)} (${fs.statSync(OUT_ICO).size} bytes, sizes ${ICO_SIZES.join('/')})`);
}
