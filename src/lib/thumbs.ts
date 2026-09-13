export function cardImage(src?: string) {
  if (!src) return undefined;
  if (!src.startsWith('/uploads/')) return src;
  return `/thumbs/${src.slice('/uploads/'.length).replace(/\.[^.]+$/, '.webp')}`;
}
