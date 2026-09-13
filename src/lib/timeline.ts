const TIME_RE = /\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?/;
const HINT_TEXT = '좌표를 클릭하면 해당 좌표의 스크린샷을 확인할 수 있습니다.';
const HINT_HTML = `<p class="timeline-hint">${HINT_TEXT}</p>`;

export type MovieLink = {
  name: string;
  path: string;
  slug: string;
};

export function enhanceTimelineHtml(html: string, movies: MovieLink[] = []) {
  return rewriteRecommendLinks(decorateSummaries(insertTimelineHint(html)), movies);
}

function insertTimelineHint(html: string) {
  if (html.includes('class="timeline-hint"')) return html;

  const detailsIdx = html.search(/<details\b/i);
  if (detailsIdx === -1) return html;

  const before = html.slice(0, detailsIdx);
  const headings = [...before.matchAll(/<h2\b[^>]*>[\s\S]*?<\/h2>/gi)];
  const heading = headings.at(-1);
  if (!heading || heading.index == null) return html;
  if (!/좌표|타임라인/.test(heading[0])) return html;

  const insertAt = heading.index + heading[0].length;
  return `${html.slice(0, insertAt)}\n${HINT_HTML}${html.slice(insertAt)}`;
}

function decorateSummaries(html: string) {
  return html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/gi, (block) => {
    if (block.includes('class="timeline-time"') || block.includes("class='timeline-time'")) {
      return block;
    }

    const summaryMatch = block.match(/<summary\b([^>]*)>([\s\S]*?)<\/summary>/i);
    if (!summaryMatch) return block;

    const afterSummary = block.slice((summaryMatch.index ?? 0) + summaryMatch[0].length);
    const timeMatch = afterSummary.match(TIME_RE);
    if (!timeMatch) return block;

    const attrs = summaryMatch[1];
    const title = summaryMatch[2].trim();
    const stamped = `<summary${attrs}><span class="timeline-title">${title}</span><span class="timeline-time">좌표 ${timeMatch[1]}</span></summary>`;
    return block.replace(summaryMatch[0], stamped);
  });
}

function rewriteRecommendLinks(html: string, movies: MovieLink[]) {
  if (movies.length === 0) return html;

  return html.replace(/<a\b[^>]*href="[^"]*"[^>]*>\s*보러가기\s*<\/a>/gi, (anchor, offset: number) => {
    const href = anchor.match(/href="([^"]*)"/i)?.[1] ?? '';
    const before = html.slice(Math.max(0, offset - 900), offset);
    const headings = [...before.matchAll(/<h3\b[^>]*>([\s\S]*?)<\/h3>/gi)];
    const title = stripTags(headings.at(-1)?.[1] ?? '') || titleFromHref(href);
    const dest = resolveRecommendHref(title, href, movies);
    return anchor.replace(/href="[^"]*"/i, `href="${dest}"`);
  });
}

function resolveRecommendHref(title: string, href: string, movies: MovieLink[]) {
  const path = decodeURIComponent((href.split('?')[0] ?? '').replace(/\/+$/, '').replace(/^\//, ''));
  const hrefName = titleFromHref(href);
  const names = [title, hrefName].map(normalizeName).filter(Boolean);

  const matched = movies.find((movie) => {
    const slug = normalizeName(movie.slug);
    const name = normalizeName(movie.name);
    return (
      movie.slug === path ||
      names.includes(name) ||
      names.some((item) => slug === item || slug.startsWith(`${item}좌표`))
    );
  });

  if (matched) return matched.path;
  const query = title || hrefName;
  return query ? `/search/?q=${encodeURIComponent(query)}` : '/search/';
}

function titleFromHref(href: string) {
  const path = decodeURIComponent((href.split('?')[0] ?? '').replace(/\/+$/, '').replace(/^\//, ''));
  const raw = path.split(/-좌표/)[0] ?? path;
  return raw.replace(/-/g, ' ').trim();
}

function stripTags(value: string) {
  return value.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

function normalizeName(value: string) {
  return value
    .toLowerCase()
    .replace(/\(.*?\)/g, '')
    .replace(/[\s_\-:：·.'"]/g, '');
}
