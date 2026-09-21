export const SEARCH_GENERICS = [
  '한국영화',
  '한국 영화',
  '하이라이트',
  'highlight',
  '엑기스',
  '타임라인',
  '명장면',
  '신스틸러',
  '좌표',
  '장면',
  '검색',
  '영화',
];

export const SEARCH_KEYWORDS = ['엑기스', '하이라이트', '좌표', '명장면', '한국영화', '영화'];

export function meaningfulQuery(raw: string) {
  let query = raw.trim().toLowerCase();
  const terms = [...SEARCH_GENERICS].sort((a, b) => b.length - a.length);
  for (const term of terms) {
    query = query.split(term.toLowerCase()).join(' ');
  }
  return query.replace(/\s+/g, ' ').trim();
}
