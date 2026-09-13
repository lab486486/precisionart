import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DEFAULT_XML = path.join(ROOT, 'WordPress.2026-09-13.xml');
const MOVIES_DIR = path.join(ROOT, 'src', 'content', 'movies');
const REDIRECTS = path.join(ROOT, 'public', '_redirects');
const SHORTLINKS = path.join(ROOT, 'public', 'shortlinks.json');
const HIDDEN_CATEGORIES = new Set(['영화지시', 'instruction']);

const MANUAL_REDIRECTS = `/rss/ /rss 301
/rss.xml /rss 301
/rss.xml/ /rss 301
/category/영화리뷰 /category/review/ 301
/category/추천글 /category/recommend/ 301
/category/영화지시 / 301
/privacy-policy /privacy/ 301
/privacy-policy/ /privacy/ 301
`.trim();

function tag(block, name) {
  const match = block.match(
    new RegExp(`<${name}(?:\\s[^>]*)?>(?:<!\\[CDATA\\[(.*?)\\]\\]>|(.*?))</${name}>`, 's'),
  );
  if (!match) return '';
  return (match[1] ?? match[2] ?? '').trim();
}

function decodeSlug(value) {
  let text = String(value || '').trim();
  for (let i = 0; i < 3; i += 1) {
    try {
      const next = decodeURIComponent(text);
      if (next === text) break;
      text = next;
    } catch {
      break;
    }
  }
  return text;
}

function parseFrontmatter(text) {
  if (!text.startsWith('---')) return {};
  const parts = text.split('---', 3);
  const data = {};
  for (const line of (parts[1] || '').split('\n')) {
    if (!line.includes(':')) continue;
    const idx = line.indexOf(':');
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '');
    if (key) data[key] = value;
  }
  return data;
}

function parseItems(xml) {
  return [...xml.matchAll(/<item>(.*?)<\/item>/gs)].map((match) => match[1]);
}

async function main() {
  const xmlPath = process.argv[2] || DEFAULT_XML;
  const xml = await readFile(xmlPath, 'utf8');
  const published = [];
  for (const block of parseItems(xml)) {
    if (tag(block, 'wp:post_type') !== 'post' || tag(block, 'wp:status') !== 'publish') {
      continue;
    }
    const wpCats = [...block.matchAll(/<category domain="category"[^>]*><!\[CDATA\[(.*?)\]\]><\/category>/g)].map(
      (match) => match[1],
    );
    if (wpCats.some((cat) => HIDDEN_CATEGORIES.has(cat))) {
      continue;
    }
    const id = tag(block, 'wp:post_id');
    const link = tag(block, 'link');
    const rawPath = new URL(link).pathname.replace(/\/$/, '').replace(/^\//, '');
    published.push({
      id,
      title: tag(block, 'title'),
      link,
      slug: decodeSlug(rawPath || tag(block, 'wp:post_name')),
    });
  }

  const files = (await readdir(MOVIES_DIR)).filter((name) => name.endsWith('.md'));
  const byId = new Map();
  for (const file of files) {
    const raw = await readFile(path.join(MOVIES_DIR, file), 'utf8');
    const meta = parseFrontmatter(raw);
    if (meta.legacyId) byId.set(String(meta.legacyId), { file, ...meta });
  }

  const missing = published.filter((post) => !byId.has(post.id));
  const slugMismatch = [];
  for (const post of published) {
    const local = byId.get(post.id);
    if (local && local.entrySlug !== post.slug) {
      slugMismatch.push({ id: post.id, xml: post.slug, local: local.entrySlug });
    }
  }

  const shortlinks = {};
  const lines = [MANUAL_REDIRECTS, '', '# WordPress permalinks'];
  for (const post of published) {
    const dest = `/${post.slug}/`;
    shortlinks[post.id] = dest;
    lines.push(`/p/${post.id} ${dest} 301`);
    lines.push(`/p/${post.id}/ ${dest} 301`);
  }
  lines.push('');

  await writeFile(REDIRECTS, `${lines.join('\n')}\n`);
  await writeFile(SHORTLINKS, `${JSON.stringify(shortlinks, null, 2)}\n`);

  console.log(`XML 공개 글 ${published.length}개, 사이트 글 ${files.length}개`);
  if (missing.length) {
    console.log('사이트에 없는 글:');
    for (const post of missing) console.log(`  ${post.id} ${post.title} ${post.link}`);
    process.exitCode = 1;
  } else {
    console.log('모든 공개 글이 /{슬러그}/ 로 연결되어 있습니다.');
  }
  if (slugMismatch.length) {
    console.log('슬러그 불일치:');
    for (const item of slugMismatch) console.log(`  ${item.id} xml=${item.xml} local=${item.local}`);
    process.exitCode = 1;
  }
  console.log(`wrote ${path.relative(ROOT, REDIRECTS)}`);
  console.log(`wrote ${path.relative(ROOT, SHORTLINKS)}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
