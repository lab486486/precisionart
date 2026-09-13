import type { APIRoute } from 'astro';
import { categoryLabel, entryPath, getListedMovies, movieDate } from '../lib/movies';
import { cardImage } from '../lib/thumbs';

export const GET: APIRoute = async () => {
  const entries = await getListedMovies();
  const payload = entries.map((entry) => ({
    name: entry.data.name,
    title: entry.data.title,
    excerpt: entry.data.excerpt ?? '',
    href: entryPath(entry),
    category: categoryLabel(entry),
    year: entry.data.year ?? '',
    cast: entry.data.cast ?? '',
    director: entry.data.director ?? '',
    date: movieDate(entry),
    thumbnail: cardImage(entry.data.thumbnail, 200),
    tags: entry.data.tags,
  }));

  return new Response(JSON.stringify(payload), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
};
