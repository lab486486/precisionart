import { mkdir, readdir, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import sharp from 'sharp';

const ROOT = path.resolve(import.meta.dirname, '..');
const MOVIES = path.join(ROOT, 'src', 'content', 'movies');
const PUBLIC_DIR = path.join(ROOT, 'public');
const SIZES = [200, 360];

async function thumbnailPaths() {
  const files = await readdir(MOVIES);
  const paths = new Set();
  for (const file of files) {
    if (!file.endsWith('.md')) continue;
    const text = await readFile(path.join(MOVIES, file), 'utf8');
    const match = text.match(/^thumbnail:\s*["']?([^"'\n]+)["']?/m);
    const src = match?.[1]?.trim();
    if (src?.startsWith('/uploads/')) paths.add(src);
  }
  return [...paths];
}

async function needsBuild(src, dest) {
  try {
    const [from, to] = await Promise.all([stat(src), stat(dest)]);
    return from.mtimeMs > to.mtimeMs;
  } catch {
    return true;
  }
}

const paths = await thumbnailPaths();
await mkdir(path.join(PUBLIC_DIR, 'thumbs'), { recursive: true });

for (const src of paths) {
  const input = path.join(PUBLIC_DIR, src.replace(/^\//, ''));
  const rel = src.slice('/uploads/'.length).replace(/\.[^.]+$/, '.webp');
  for (const width of SIZES) {
    const dest = path.join(PUBLIC_DIR, 'thumbs', String(width), rel);
    await mkdir(path.dirname(dest), { recursive: true });
    if (!(await needsBuild(input, dest))) continue;
    await sharp(input)
      .rotate()
      .resize(width, null, { withoutEnlargement: true })
      .webp({ quality: 62 })
      .toFile(dest);
    console.log(`thumb ${path.relative(PUBLIC_DIR, dest)}`);
  }
}

console.log(`card thumbs ${paths.length}개`);
