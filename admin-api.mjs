import { Buffer } from 'node:buffer';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const QUEUE_DIR = path.join(ROOT, 'src', 'content', 'queue');
const MOVIES_DIR = path.join(ROOT, 'src', 'content', 'movies');
const UPLOAD_DIR = path.join(ROOT, 'public', 'uploads');

const IMAGE_EXT = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
  'image/gif': 'gif',
};

const CATEGORIES = new Set(['review', 'recommend']);

function send(res, status, payload) {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function yamlScalar(value) {
  if (typeof value === 'boolean' || typeof value === 'number') return String(value);
  if (value == null || value === '') return '""';
  return JSON.stringify(String(value));
}

function dumpFrontmatter(data) {
  const lines = ['---'];
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${key}: []`);
        continue;
      }
      lines.push(`${key}:`);
      for (const item of value) lines.push(`  - ${yamlScalar(item)}`);
      continue;
    }
    if (typeof value === 'boolean' || typeof value === 'number') {
      lines.push(`${key}: ${value}`);
      continue;
    }
    lines.push(`${key}: ${yamlScalar(value)}`);
  }
  lines.push('---', '');
  return `${lines.join('\n')}`;
}

function coerceYaml(value) {
  const text = String(value ?? '').trim();
  if (text === 'true') return true;
  if (text === 'false') return false;
  if (text === '[]') return [];
  if (text !== '' && /^-?\d+(\.\d+)?$/.test(text)) return Number(text);
  return text.replace(/^["']|["']$/g, '');
}

function parseMarkdown(text) {
  const stripped = text.replace(/^\uFEFF/, '');
  if (!stripped.startsWith('---')) return { data: {}, body: stripped };
  const rest = stripped.slice(3);
  const end = rest.indexOf('\n---');
  if (end === -1) return { data: {}, body: stripped };
  const raw = rest.slice(0, end);
  const body = rest.slice(end + 4).replace(/^\n/, '');
  const data = {};
  let current;
  for (const line of raw.split('\n')) {
    if (!line.trim()) continue;
    const listValue = line.match(/^  - (.*)$/);
    if (current && listValue) {
      data[current].push(coerceYaml(listValue[1]));
      continue;
    }
    const match = line.match(/^([A-Za-z0-9_]+):\s*(.*)$/);
    if (!match) continue;
    current = match[1];
    const value = match[2];
    if (value === '' || value === '[]') {
      data[current] = [];
      if (value === '[]') current = undefined;
      continue;
    }
    data[current] = coerceYaml(value);
    current = undefined;
  }
  return { data, body };
}

function parseFrontmatter(text) {
  return parseMarkdown(text).data;
}

function safeFile(name) {
  const file = path.basename(String(name || ''));
  if (!file.endsWith('.md') || file.startsWith('_') || file.includes('..')) {
    throw new Error('글 파일을 확인해 주세요.');
  }
  return file;
}

function safeName(name) {
  const cleaned = String(name || '')
    .trim()
    .replace(/[\\/]/g, '')
    .replace(/\s+/g, ' ');
  if (!cleaned || cleaned.includes('..')) {
    throw new Error('영화 제목을 확인해 주세요.');
  }
  return cleaned;
}

function fileStem(name) {
  return (
    safeName(name)
      .replace(/[^\w가-힣.-]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'movie'
  );
}

async function listPosts() {
  let names = [];
  try {
    names = await readdir(MOVIES_DIR);
  } catch {
    return [];
  }
  const items = [];
  for (const file of names.sort()) {
    if (!file.endsWith('.md')) continue;
    const { data } = parseMarkdown(await readFile(path.join(MOVIES_DIR, file), 'utf8'));
    items.push({
      file,
      name: data.name || file.replace(/\.md$/, ''),
      title: data.title || '',
      category: data.category || '',
      entrySlug: data.entrySlug || '',
      path: data.legacyPath || (data.entrySlug ? `/${data.entrySlug}/` : ''),
      hiddenFromList: Boolean(data.hiddenFromList),
      featured: Boolean(data.featured),
    });
  }
  return items.sort((a, b) => a.name.localeCompare(b.name, 'ko'));
}

async function readPost(file) {
  const dest = path.join(MOVIES_DIR, safeFile(file));
  const { data, body } = parseMarkdown(await readFile(dest, 'utf8'));
  return { file: path.basename(dest), ...data, body };
}

async function writePost(file, patch) {
  const dest = path.join(MOVIES_DIR, safeFile(file));
  const current = parseMarkdown(await readFile(dest, 'utf8'));
  const category = String(patch.category ?? current.data.category ?? '');
  if (!CATEGORIES.has(category)) {
    throw new Error('카테고리를 선택해 주세요.');
  }
  const next = {
    ...current.data,
    title: String(patch.title || current.data.title || '').trim(),
    name: safeName(patch.name || current.data.name),
    category,
    year: String(patch.year || '').trim(),
    genre: String(patch.genre || '').trim(),
    director: String(patch.director || '').trim(),
    cast: String(patch.cast || '').trim(),
    thumbnail: String(patch.thumbnail || '').trim(),
    excerpt: String(patch.excerpt || '').trim(),
    featured: Boolean(patch.featured),
    hiddenFromList: Boolean(patch.hiddenFromList),
    updated: new Date().toISOString().slice(0, 19),
  };
  const body = String(patch.body ?? current.body ?? '').replace(/\s+$/, '') + '\n';
  await writeFile(dest, `${dumpFrontmatter(next)}${body}`, 'utf8');
  return { ok: true, file: path.basename(dest), path: next.legacyPath || `/${next.entrySlug}/` };
}

async function listQueue() {
  let names = [];
  try {
    names = await readdir(QUEUE_DIR);
  } catch {
    return [];
  }
  const items = [];
  for (const file of names.sort()) {
    if (!file.endsWith('.md') || file.startsWith('_') || file.toLowerCase() === 'readme.md') {
      continue;
    }
    const raw = await readFile(path.join(QUEUE_DIR, file), 'utf8');
    const meta = parseFrontmatter(raw);
    items.push({
      file,
      name: meta.name || file.replace(/\.md$/, ''),
      category: meta.category || '',
      status: meta.status || '',
      note: meta.note || '',
      year: meta.year || '',
    });
  }
  return items;
}

function normalizeApiPath(url = '') {
  return url.split('?')[0].replace(/\/$/, '') || '/';
}

export function movieAdminApi() {
  return {
    name: 'movie-admin-api',
    hooks: {
      'astro:server:setup'({ server }) {
        server.middlewares.stack.unshift({
          route: '',
          handle: async (req, res, next) => {
            const url = normalizeApiPath(req.url || '');
            if (!url.startsWith('/api/movie-')) return next();

            try {
              if (url === '/api/movie-queue' && req.method === 'GET') {
                return send(res, 200, { items: await listQueue() });
              }

              if (url === '/api/movie-queue' && req.method === 'POST') {
                const body = JSON.parse((await readBody(req)).toString('utf8') || '{}');
                const name = safeName(body.name);
                const category = String(body.category || '');
                if (!CATEGORIES.has(category)) {
                  return send(res, 400, { error: '카테고리를 선택해 주세요.' });
                }
                await mkdir(QUEUE_DIR, { recursive: true });
                const dest = path.join(QUEUE_DIR, `${fileStem(name)}.md`);
                const markdown = dumpFrontmatter({
                  name,
                  category,
                  year: String(body.year || '').trim(),
                  thumbnail: String(body.thumbnail || '').trim(),
                  timeline: String(body.timeline || '').trim(),
                  featured: Boolean(body.featured),
                  status: 'pending',
                  note: String(body.note || '').trim(),
                });
                await writeFile(dest, markdown, 'utf8');
                return send(res, 200, { ok: true, file: path.basename(dest) });
              }

              if (url === '/api/movie-posts' && req.method === 'GET') {
                return send(res, 200, { items: await listPosts() });
              }

              if (url === '/api/movie-post' && req.method === 'GET') {
                const query = new URL(req.url || '/', 'http://localhost').searchParams;
                return send(res, 200, await readPost(query.get('file')));
              }

              if (url === '/api/movie-post' && req.method === 'POST') {
                const body = JSON.parse((await readBody(req)).toString('utf8') || '{}');
                return send(res, 200, await writePost(body.file, body));
              }

              if (url === '/api/movie-upload' && req.method === 'POST') {
                const body = JSON.parse((await readBody(req)).toString('utf8') || '{}');
                const mime = String(body.mime || '');
                const ext = IMAGE_EXT[mime];
                if (!ext) {
                  return send(res, 400, { error: 'jpg, png, webp, gif만 올릴 수 있습니다.' });
                }
                const data = String(body.data || '').replace(/^data:[^;]+;base64,/, '');
                const buffer = Buffer.from(data, 'base64');
                if (!buffer.length || buffer.length > 5 * 1024 * 1024) {
                  return send(res, 400, { error: '이미지 크기는 5MB 이하만 됩니다.' });
                }
                const rawName = String(body.filename || `movie.${ext}`).replace(/[\\/]/g, '');
                const stem = rawName.replace(/\.[^.]+$/, '').replace(/[^\w가-힣.-]+/g, '-') || 'movie';
                const filename = `${stem}-${Date.now()}.${ext}`;
                await mkdir(UPLOAD_DIR, { recursive: true });
                await writeFile(path.join(UPLOAD_DIR, filename), buffer);
                return send(res, 200, { url: `/uploads/${filename}` });
              }

              return send(res, 404, { error: '없는 API입니다.' });
            } catch (error) {
              return send(res, 500, {
                error: error instanceof Error ? error.message : '저장에 실패했습니다.',
              });
            }
          },
        });
      },
    },
  };
}
