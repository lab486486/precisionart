import type { APIRoute } from 'astro';
import { escapeXml, publicPages } from '../lib/feed';

export const GET: APIRoute = async () => {
  const pages = await publicPages();
  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...pages.map((page) => {
      const lastmod =
        page.lastmod instanceof Date
          ? `<lastmod>${page.lastmod.toISOString()}</lastmod>`
          : '';
      return [
        '<url>',
        `<loc>${escapeXml(page.loc)}</loc>`,
        lastmod,
        `<changefreq>${page.changefreq}</changefreq>`,
        `<priority>${page.priority}</priority>`,
        '</url>',
      ].join('');
    }),
    '</urlset>',
    '',
  ].join('\n');

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
    },
  });
};
