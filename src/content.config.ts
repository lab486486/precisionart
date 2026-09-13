import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const movies = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/movies' }),
  schema: z.object({
    title: z.string(),
    name: z.string(),
    category: z.enum(['review', 'recommend']),
    year: z.string().optional(),
    genre: z.string().optional(),
    director: z.string().optional(),
    cast: z.string().optional(),
    studio: z.string().optional(),
    rating: z.string().optional(),
    thumbnail: z.string().optional(),
    excerpt: z.string().optional(),
    featured: z.boolean().default(false),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    entrySlug: z.string(),
    legacyPath: z.string(),
    canonical: z.string().optional(),
    hiddenFromList: z.boolean().default(false),
    movieKey: z.string().optional(),
    legacyId: z.number().optional(),
  }),
});

export const collections = { movies };
