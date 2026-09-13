import { getCollection, type CollectionEntry } from 'astro:content';
import { getCategory } from './categories';

export type MovieEntry = CollectionEntry<'movies'>;

export async function getMovies() {
  const entries = await getCollection('movies');
  return entries.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export async function getListedMovies() {
  const entries = await getMovies();
  return entries.filter((entry) => !entry.data.hiddenFromList);
}

export async function getMoviesByCategory(slug: string) {
  const entries = await getListedMovies();
  return entries.filter((entry) => entry.data.category === slug);
}

export async function getFeaturedMovies() {
  const entries = await getListedMovies();
  const featured = entries.filter((entry) => entry.data.featured);
  if (featured.length >= 8) return featured.slice(0, 12);
  return entries.slice(0, 12);
}

export function entryPath(entry: MovieEntry) {
  return `/${entry.data.entrySlug}/`;
}

export function categoryLabel(entry: MovieEntry) {
  return getCategory(entry.data.category)?.name ?? entry.data.category;
}

export function movieDate(entry: MovieEntry) {
  const value = entry.data.updated ?? entry.data.date;
  return value.toISOString().slice(0, 10).replaceAll('-', '.');
}

export function byName(entries: MovieEntry[]) {
  return [...entries].sort((a, b) => a.data.name.localeCompare(b.data.name, 'ko'));
}
