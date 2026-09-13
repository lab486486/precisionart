import { categories, categoryPath } from './categories';
import { entryPath, getListedMovies, getMovies } from './movies';
import { site } from '../data/site';

export function escapeXml(value: string) {
  return value.replace(/[<>&'"]/g, (char) => {
    switch (char) {
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '&':
        return '&amp;';
      case "'":
        return '&apos;';
      default:
        return '&quot;';
    }
  });
}

export function absUrl(path: string) {
  return new URL(path, `${site.url}/`).href;
}

export async function publicPages() {
  const entries = await getMovies();
  const pages = [
    { loc: absUrl('/'), lastmod: latestDate(entries), changefreq: 'daily', priority: '1.0' },
    { loc: absUrl('/search/'), changefreq: 'weekly', priority: '0.4' },
    { loc: absUrl('/privacy/'), changefreq: 'yearly', priority: '0.2' },
    { loc: absUrl('/rss'), changefreq: 'daily', priority: '0.3' },
    ...categories.map((category) => ({
      loc: absUrl(categoryPath(category.slug)),
      changefreq: 'weekly',
      priority: '0.7',
    })),
    ...entries.map((entry) => ({
      loc: absUrl(entry.data.canonical ?? entryPath(entry)),
      lastmod: entry.data.updated ?? entry.data.date,
      changefreq: 'monthly',
      priority: entry.data.hiddenFromList ? '0.3' : '0.8',
    })),
  ];

  const seen = new Set<string>();
  return pages.filter((page) => {
    if (seen.has(page.loc)) return false;
    seen.add(page.loc);
    return true;
  });
}

export async function rssItems() {
  const entries = await getListedMovies();
  return entries.map((entry) => ({
    title: entry.data.title,
    link: absUrl(entryPath(entry)),
    description: entry.data.excerpt ?? entry.data.title,
    pubDate: entry.data.updated ?? entry.data.date,
    category: entry.data.category,
  }));
}

function latestDate(entries: Awaited<ReturnType<typeof getMovies>>) {
  return entries.reduce((latest, entry) => {
    const value = entry.data.updated ?? entry.data.date;
    return value > latest ? value : latest;
  }, new Date(0));
}
