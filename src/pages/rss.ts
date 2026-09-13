import type { APIRoute } from 'astro';
import { site } from '../data/site';
import { absUrl, escapeXml, rssItems } from '../lib/feed';

export const GET: APIRoute = async () => {
  const items = await rssItems();
  const self = absUrl('/rss');
  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
    '<channel>',
    `<title>${escapeXml(site.name)}</title>`,
    `<link>${escapeXml(absUrl('/'))}</link>`,
    `<description>${escapeXml(site.description)}</description>`,
    '<language>ko</language>',
    `<atom:link href="${escapeXml(self)}" rel="self" type="application/rss+xml"/>`,
    ...items.map((item) =>
      [
        '<item>',
        `<title>${escapeXml(item.title)}</title>`,
        `<link>${escapeXml(item.link)}</link>`,
        `<guid isPermaLink="true">${escapeXml(item.link)}</guid>`,
        `<pubDate>${item.pubDate.toUTCString()}</pubDate>`,
        `<category>${escapeXml(item.category)}</category>`,
        `<description>${escapeXml(item.description)}</description>`,
        '</item>',
      ].join(''),
    ),
    '</channel>',
    '</rss>',
    '',
  ].join('\n');

  return new Response(body, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
    },
  });
};
