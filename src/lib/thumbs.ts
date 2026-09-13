export type CardWidth = 200 | 360;

export function cardImage(src?: string, width: CardWidth = 360) {
  if (!src) return undefined;
  if (!src.startsWith('/uploads/')) return src;
  return `/thumbs/${width}/${src.slice('/uploads/'.length).replace(/\.[^.]+$/, '.webp')}`;
}
