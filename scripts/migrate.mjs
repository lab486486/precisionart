import { access, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DEFAULT_XML = path.join(ROOT, 'WordPress.2026-09-13.xml');
const IMAGE_BASE = process.env.PUBLIC_IMAGE_BASE ?? '';
const HIDDEN_CATEGORIES = new Set(['영화지시', 'instruction']);
const WP_CATEGORY = {
  영화리뷰: 'review',
  review: 'review',
  추천글: 'recommend',
  recommend: 'recommend',
};
const FEATURED_KEYS = new Set(['기생충', '타짜', '박쥐', '인간중독', '히든페이스', '하녀']);
const HEADERS = {
  Accept: 'application/json,text/html;q=0.9,*/*;q=0.8',
  'User-Agent':
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
};

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

function decodeHtml(value = '') {
  return value
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(Number.parseInt(code, 16)))
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#039;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ')
    .trim();
}

function stripHtml(value = '') {
  return decodeHtml(value.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')).trim();
}

function yamlValue(value) {
  if (value === undefined || value === null || value === '') return '';
  const text = String(value)
    .replace(/[\u0000-\u001F\u007F]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return JSON.stringify(text);
}

function toYaml(data) {
  const lines = ['---'];
  for (const [key, value] of Object.entries(data)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${key}: []`);
        continue;
      }
      lines.push(`${key}:`);
      for (const item of value) lines.push(`  - ${yamlValue(item)}`);
    } else if (typeof value === 'boolean' || typeof value === 'number') {
      lines.push(`${key}: ${value}`);
    } else {
      lines.push(`${key}: ${yamlValue(value)}`);
    }
  }
  lines.push('---', '');
  return lines.join('\n');
}

function movieName(title) {
  return title.replace(/\s*좌표[,:].*$/u, '').trim() || title;
}

function movieKey(name) {
  return name.toLowerCase().replace(/[^\w가-힣]+/g, '') || 'movie';
}

function guessCategory(wpCats) {
  for (const cat of wpCats) {
    if (WP_CATEGORY[cat]) return WP_CATEGORY[cat];
  }
  return 'review';
}

function extractField(html, labels) {
  for (const label of labels) {
    const match = html.match(new RegExp(`${label}\\s*[:：]\\s*([^<\\n]+)`, 'i'));
    if (match) return decodeHtml(match[1]).trim();
  }
  return '';
}

function extractYear(tags, html) {
  for (const item of tags) {
    const match = String(item).match(/\b((?:19|20)\d{2})\b/);
    if (match) return match[1];
  }
  const fromHtml = html.match(/\b((?:19|20)\d{2})\s*년/);
  return fromHtml?.[1] || '';
}

function cleanHtml(html) {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

async function saveImage(url) {
  if (!url || !/precisionart\.net\/wp-content\/uploads\//i.test(url)) return url;
  const parsed = new URL(url);
  const relative = decodeURIComponent(parsed.pathname.replace('/wp-content/uploads/', ''));
  const dest = path.join(ROOT, 'public/uploads', relative);
  const publicPath = `/uploads/${relative.split(path.sep).join('/')}`;
  const served = IMAGE_BASE ? `${IMAGE_BASE}${publicPath}` : publicPath;
  try {
    await access(dest);
    return served;
  } catch {
    // download below
  }
  await mkdir(path.dirname(dest), { recursive: true });
  const response = await fetch(url, { headers: HEADERS });
  if (!response.ok) {
    console.warn(`image skip ${response.status} ${url}`);
    return url;
  }
  await writeFile(dest, Buffer.from(await response.arrayBuffer()));
  return served;
}

async function rewriteImages(html) {
  const urls = [...html.matchAll(/src=["']([^"']+)["']/gi)].map((match) => match[1]);
  let next = html;
  for (const url of urls) {
    if (!url.includes('/wp-content/uploads/')) continue;
    const local = await saveImage(url);
    next = next.replaceAll(url, local);
  }
  return next;
}

function parseItems(xml) {
  return [...xml.matchAll(/<item>(.*?)<\/item>/gs)].map((match) => match[1]);
}

async function main() {
  const { readFile } = await import('node:fs/promises');
  const xmlPath = process.argv[2] || DEFAULT_XML;
  const xml = await readFile(xmlPath, 'utf8');
  await mkdir(path.join(ROOT, 'src/content/movies'), { recursive: true });

  const attachments = new Map();
  for (const block of parseItems(xml)) {
    if (tag(block, 'wp:post_type') !== 'attachment') continue;
    attachments.set(tag(block, 'wp:post_id'), tag(block, 'wp:attachment_url') || tag(block, 'guid'));
  }

  const prepared = [];
  for (const block of parseItems(xml)) {
    if (tag(block, 'wp:post_type') !== 'post' || tag(block, 'wp:status') !== 'publish') {
      continue;
    }
    const wpCats = [...block.matchAll(/<category domain="category"[^>]*><!\[CDATA\[(.*?)\]\]><\/category>/g)].map(
      (match) => decodeHtml(match[1]),
    );
    if (wpCats.some((cat) => HIDDEN_CATEGORIES.has(cat))) {
      continue;
    }

    const id = Number(tag(block, 'wp:post_id'));
    const title = decodeHtml(tag(block, 'title'));
    const link = tag(block, 'link');
    const rawPath = new URL(link).pathname.replace(/\/$/, '').replace(/^\//, '');
    const entrySlug = decodeSlug(rawPath || tag(block, 'wp:post_name'));
    const html = await rewriteImages(cleanHtml(tag(block, 'content:encoded')));
    const thumbId = block.match(
      /<wp:meta_key><!\[CDATA\[_thumbnail_id\]\]><\/wp:meta_key>\s*<wp:meta_value><!\[CDATA\[(\d+)\]\]>/,
    );
    const featuredUrl = thumbId ? attachments.get(thumbId[1]) : '';
    const firstImg = html.match(/src=["']([^"']+)["']/);
    const thumbnail = featuredUrl ? await saveImage(featuredUrl) : firstImg?.[1];
    const name = movieName(title);
    const category = guessCategory(wpCats);
    const tags = [...block.matchAll(/<category domain="post_tag"[^>]*><!\[CDATA\[(.*?)\]\]><\/category>/g)].map(
      (match) => decodeHtml(match[1]),
    );
    const excerpt = stripHtml(tag(block, 'excerpt:encoded') || html).slice(0, 180);

    prepared.push({
      title,
      name,
      category,
      year: extractYear(tags, html),
      genre: extractField(html, ['장르']),
      director: extractField(html, ['감독']),
      cast: extractField(html, ['출연']),
      studio: extractField(html, ['제작사']),
      rating: extractField(html, ['에디터 평점']),
      thumbnail,
      excerpt,
      date: tag(block, 'wp:post_date') || tag(block, 'pubDate'),
      updated: tag(block, 'wp:post_modified') || tag(block, 'wp:post_date'),
      tags,
      entrySlug,
      legacyPath: `/${entrySlug}/`,
      movieKey: movieKey(name),
      legacyId: id,
      featured: FEATURED_KEYS.has(name) || category === 'recommend',
      hiddenFromList: false,
      body: html,
    });
    console.log(`converted ${id} ${title}`);
  }

  for (const item of prepared) {
    const { body, ...frontmatter } = item;
    const file = path.join(ROOT, 'src/content/movies', `${item.legacyId}.md`);
    await writeFile(file, `${toYaml(frontmatter)}${body}\n`);
  }

  console.log(`Wrote ${prepared.length} markdown files.`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
