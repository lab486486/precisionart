// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { movieAdminApi } from './admin-api.mjs';

export default defineConfig({
  site: 'https://precisionart.net',
  trailingSlash: 'always',
  integrations: [
    movieAdminApi(),
    sitemap({
      filter: (page) => !page.includes('/admin') && !page.includes('/p/'),
    }),
  ],
});
