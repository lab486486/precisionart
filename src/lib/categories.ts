export const categories = [
  {
    slug: 'review',
    name: '영화리뷰',
    description: '명장면 타임라인 좌표와 작품 해설',
    wpSlugs: ['영화리뷰', 'review'],
  },
  {
    slug: 'recommend',
    name: '추천글',
    description: '분위기와 취향에 맞춘 영화 추천',
    wpSlugs: ['추천글', 'recommend'],
  },
] as const;

export type CategorySlug = (typeof categories)[number]['slug'];

export function getCategory(slug: string) {
  return categories.find((category) => category.slug === slug);
}

export function categoryPath(slug: string) {
  return `/category/${slug}/`;
}
