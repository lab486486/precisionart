import type { APIRoute } from 'astro';
import { categories, categoryPath } from '../lib/categories';
import { absUrl } from '../lib/feed';
import { entryPath, getListedMovies } from '../lib/movies';
import { site } from '../data/site';

export const GET: APIRoute = async () => {
  const movies = await getListedMovies();
  const body = [
    `# ${site.name}`,
    '',
    site.description,
    '',
    '이 사이트는 영화 명장면의 시간 좌표만 안내하며, 영상을 호스팅하거나 스트리밍하지 않습니다.',
    '',
    '## 페이지',
    '',
    `- [홈](${absUrl('/')})`,
    `- [검색](${absUrl('/search/')})`,
    `- [RSS](${absUrl('/rss')})`,
    `- [사이트맵](${absUrl('/sitemap.xml')})`,
    `- [개인정보처리방침](${absUrl('/privacy/')})`,
    ...categories.map((category) => `- [${category.name}](${absUrl(categoryPath(category.slug))})`),
    '',
    '## 영화',
    '',
    ...movies.map((entry) => `- [${entry.data.name}](${absUrl(entryPath(entry))})`),
    '',
  ].join('\n');

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
    },
  });
};
