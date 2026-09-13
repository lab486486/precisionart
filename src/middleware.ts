import { defineMiddleware } from 'astro:middleware';

export const onRequest = defineMiddleware(({ request, redirect }, next) => {
  const path = new URL(request.url).pathname;
  if (path === '/rss.xml') {
    return redirect('/rss', 301);
  }
  return next();
});
