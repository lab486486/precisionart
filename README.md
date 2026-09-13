# 프리시전아트

워드프레스 `precisionart.net`을 Astro + GitHub + Cloudflare Pages로 옮긴 영화 명장면 좌표 검색 사이트입니다. 영상은 호스팅하지 않고 몇 분 몇 초 타임라인만 안내합니다.

새 글은 `/admin/`에 영화 제목, 개봉연도, 타임라인만 넣으면 대기 파일이 생기고, GitHub Action이 DeepSeek로 `src/content/movies/*.md`를 만든 뒤 Cloudflare가 뿌립니다.

## 로컬 실행

```bash
npm install
npm run migrate   # 워드프레스 내보내기에서 글/이미지 가져오기
npm run import:wxr
npm run dev
```

- 사이트: http://localhost:4321
- 관리자(글 지시): http://localhost:4321/admin/ — 공개 메뉴에는 없습니다.

## 콘텐츠

- 글: `src/content/movies/*.md`
- 작성 지시: `src/content/queue/*.md` (`status: pending`)
- 워드프레스 보내기 주소 점검: `npm run import:wxr`
- 이미지: `public/uploads/`
- 홈 검색 칩: `src/data/site.ts`

글 URL은 기존과 같이 `/{슬러그}/`입니다. `영화지시` 카테고리 글은 공개 목록, 사이트맵, RSS에 넣지 않습니다.

## 글 작성 흐름

1. `/admin/`에서 제목, 개봉연도, 타임라인, 썸네일을 넣습니다.
2. `src/content/queue/{이름}.md`가 `status: pending`으로 저장됩니다.
3. 이 파일을 GitHub에 올리면 `Publish movie` 워크플로가 DeepSeek로 본문을 씁니다.
4. 생성된 마크다운이 커밋되고, Cloudflare Pages가 다시 빌드합니다.

로컬에서만 시험하려면 `.env`에 `DEEPSEEK_API_KEY`를 넣고 다음을 실행합니다.

```bash
pip install -r scripts/requirements.txt
python3 scripts/publish_movie.py --max-posts 1
```

기존 워드프레스용 파이썬은 `movie/`에 그대로 두었습니다. 새 발행은 `scripts/publish_movie.py`를 씁니다. `movie/.env`는 커밋하지 마세요.

GitHub Secrets:

- `DEEPSEEK_API_KEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

선택 변수 `DEEPSEEK_MODEL`(기본 `deepseek-v4-flash`). Cloudflare Pages 프로젝트 이름은 워크플로의 `precisionart`와 같게 맞춥니다.

## Cloudflare Pages

1. 이 저장소를 GitHub에 올립니다.
2. Cloudflare Pages에서 프레임워크 `Astro`, 빌드 명령 `npm run build`, 출력 `dist`로 연결합니다.
3. 도메인 `precisionart.net`을 Pages에 붙입니다.

`public/_redirects`가 예전 카테고리 URL과 `/p/{id}` 짧은 주소를 새 경로로 보냅니다. 한글 퍼머링크의 퍼센트 인코딩 self-redirect는 넣지 않습니다.
