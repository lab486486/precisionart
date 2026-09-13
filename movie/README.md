# 워드프레스 영화 자동 포스팅 시스템

이 프로젝트는 워드프레스에 **영화 제목, 개봉연도, 이미지 URL, 타임라인, 장면 좌표 메모** 정도만 담은 지시글을 남기면, 파이썬 스크립트가 워드프레스 REST API로 해당 글을 읽고 Gemini API로 영화 리뷰/해설 콘텐츠를 생성한 뒤 워드프레스에 자동 업로드하는 시스템입니다.

첨부해주신 사주봇 예제의 구조를 유지하되, 사주 계산 로직을 제거하고 영화 콘텐츠 생성용 파서와 프롬프트로 교체했습니다. 기본값은 안전하게 `draft` 발행으로 설정되어 있어, 처음에는 자동 생성 결과를 검토한 뒤 공개할 수 있습니다.

## 처리 흐름

```text
워드프레스 '영화지시' 카테고리 글 작성
        ↓
cron이 매시간 main.py 실행
        ↓
REST API로 처리완료 태그가 없는 지시글 조회
        ↓
영화 제목 / 개봉연도 / 이미지 / 타임라인 / 좌표 파싱
        ↓
Gemini가 SEO형 HTML 콘텐츠 생성
        ↓
워드프레스 '영화리뷰' 카테고리에 draft 또는 publish 업로드
        ↓
원본 지시글에 처리완료 태그 추가 및 선택적으로 draft 전환
```

## 파일 구조

| 파일 | 역할 |
|---|---|
| `main.py` | 전체 파이프라인 실행 스크립트입니다. |
| `config.py` | `.env` 값을 읽어 실행 설정을 구성합니다. |
| `wordpress_client.py` | 워드프레스 REST API 조회, 발행, 태그/카테고리 처리를 담당합니다. |
| `instruction_parser.py` | 지시글에서 영화 제목, 개봉연도, 이미지, 타임라인, 좌표를 추출합니다. |
| `gemini_client.py` | Gemini REST API를 호출하고 JSON 응답을 검증합니다. |
| `.env.example` | 실제 접속 정보 입력을 위한 환경 변수 예시입니다. |
| `install_cron.sh` | 매시간 실행 cron 등록을 돕는 스크립트입니다. |
| `requirements.txt` | 필요한 파이썬 패키지 목록입니다. |

## 운영 방식 선택지

요청하신 방식은 서버에서 파이썬과 cron을 사용하는 방식이 가장 직접적입니다. 다만 운영 환경에 따라 다음 두 방식 중 하나를 선택할 수 있습니다.

| 방식 | 장점 | 주의점 | 적합한 경우 |
|---|---|---|---|
| 호스팅 서버 또는 클라우드 서버에서 cron 실행 | 브라우저를 켜두지 않아도 매시간 자동 실행되며, 워드프레스와 같은 서버 환경에서 관리하기 쉽습니다. | 서버에 파이썬 실행 권한과 cron 권한이 필요합니다. | 지금 요청하신 **매시간 자동 확인 및 자동 업로드** 구조에 가장 적합합니다. |
| 로컬 PC에서 작업 스케줄러 또는 cron 실행 | 별도 서버 비용 없이 바로 테스트할 수 있습니다. | PC가 꺼져 있으면 실행되지 않으며, 네트워크 상태에 영향을 받습니다. | 초기 테스트나 소규모 운영에 적합합니다. |

## 설치 방법

먼저 프로젝트 폴더로 이동한 뒤 의존성을 설치합니다.

```bash
cd /path/to/movie_auto_post
python3 -m pip install -r requirements.txt
```

호스팅 환경에서 사용자 영역 설치가 필요하면 다음처럼 실행할 수 있습니다.

```bash
python3 -m pip install --user -r requirements.txt
```

## 환경 변수 설정

`.env.example`을 `.env`로 복사한 뒤 실제 값을 입력합니다.

```bash
cp .env.example .env
nano .env
```

| 변수명 | 설명 | 예시 |
|---|---|---|
| `WP_SITE_URL` | 워드프레스 사이트 주소입니다. 끝에 `/`를 붙이지 않는 것을 권장합니다. | `https://example.com` |
| `WP_USERNAME` | 워드프레스 사용자명입니다. | `admin` |
| `WP_APP_PASSWORD` | 워드프레스 애플리케이션 비밀번호입니다. 공백이 있어도 처리됩니다. | `xxxx xxxx xxxx xxxx xxxx xxxx` |
| `GEMINI_API_KEY` | Gemini API 키입니다. | `AIza...` |
| `GEMINI_MODEL` | 우선 사용할 Gemini 모델입니다. | `gemini-3-flash-preview` |
| `INSTRUCTION_CATEGORY` | 입력 지시글을 올릴 카테고리입니다. | `영화지시` |
| `OUTPUT_CATEGORY` | 자동 생성 글이 발행될 카테고리입니다. | `영화리뷰` |
| `PUBLISH_STATUS` | 새 글 상태입니다. 초기에는 `draft`를 권장합니다. | `draft` 또는 `publish` |
| `INSTRUCTION_POST_ACTION` | 처리 후 원본 지시글 처리 방식입니다. | `tag_draft` |

> 보안을 위해 `.env` 파일은 공개 저장소에 올리지 마세요. 워드프레스 앱 비밀번호와 Gemini API 키는 노출되면 즉시 폐기하고 재발급해야 합니다.

## 워드프레스 지시글 작성 형식

워드프레스에서 `영화지시` 카테고리로 글을 작성합니다. 아래처럼 최소 정보만 입력하면 됩니다.

```text
영화제목: 파묘
개봉연도: 2024
이미지: https://example.com/wp-content/uploads/2024/film-poster.jpg

타임라인:
00:00 오프닝의 분위기
00:12 첫 번째 긴장 포인트
00:45 핵심 장면 전환
01:20 결말부에서 다시 봐야 할 장면

좌표:
poster_focus: x=120, y=80, w=640, h=360
scene_01: x=20%, y=35%, note=인물 시선과 배경 대비

메모:
스포일러를 직접 쓰기보다는 분위기와 해석 중심으로 작성.
모바일 독자가 읽기 쉽게 카드형 요약 포함.
```

제목에서도 영화명을 추정할 수 있지만, 안정적인 자동화를 위해 본문에 `영화제목:`과 `개봉연도:`를 명시하는 방식을 권장합니다. 이미지는 워드프레스 편집기에 직접 넣어도 되고, `이미지:` 줄에 URL로 입력해도 됩니다.

## 테스트 실행

처음에는 반드시 `--dry-run`으로 파싱과 생성 가능 여부를 확인하세요. 이 옵션은 새 글을 발행하지 않고 로그만 출력합니다.

```bash
python3 main.py --dry-run --max-posts 1 --log-level DEBUG
```

발행까지 테스트하되 임시글로 저장하려면 다음처럼 실행합니다.

```bash
python3 main.py --max-posts 1 --status draft
```

문제가 없으면 `.env`의 `PUBLISH_STATUS`를 `publish`로 바꾸거나 실행 시 `--status publish`를 사용할 수 있습니다.

## cron 등록

매시간 실행하려면 다음 명령을 사용할 수 있습니다.

```bash
cd /path/to/movie_auto_post
./install_cron.sh
```

수동으로 등록하려면 `crontab -e`에 아래 줄을 추가합니다.

```cron
0 * * * * cd /path/to/movie_auto_post && /usr/bin/python3 main.py >> /path/to/movie_auto_post/cron.log 2>&1
```

운영 중 로그 확인은 다음과 같이 합니다.

```bash
tail -f /path/to/movie_auto_post/cron.log
tail -f /path/to/movie_auto_post/movie_auto_post.log
```

## 주요 실행 옵션

| 명령 | 설명 |
|---|---|
| `python3 main.py --dry-run` | 실제 발행 없이 테스트합니다. |
| `python3 main.py --max-posts 1` | 한 번에 1개만 처리합니다. |
| `python3 main.py --status draft` | 생성 글을 임시글로 저장합니다. |
| `python3 main.py --status publish` | 생성 글을 즉시 공개합니다. |
| `python3 main.py --action tag` | 원본 지시글에 완료 태그만 붙입니다. |
| `python3 main.py --action tag_draft` | 원본 지시글에 완료 태그를 붙이고 임시글로 전환합니다. |
| `python3 main.py --model gemini-2.5-flash` | 특정 Gemini 모델을 지정합니다. |

## 운영상 주의점

Gemini API는 모델명과 계정 쿼터에 따라 호출 실패가 발생할 수 있습니다. 이 스크립트는 fallback 모델과 재시도 로직을 포함하지만, 무료 쿼터를 초과하면 다음 cron 실행까지 기다리거나 Gemini 결제/쿼터 설정을 조정해야 합니다.

워드프레스 REST API 인증은 일반 비밀번호가 아니라 **애플리케이션 비밀번호**를 사용하는 것이 전제입니다. 워드프레스 관리자 화면의 사용자 프로필에서 애플리케이션 비밀번호를 발급한 뒤 `.env`에 입력하세요.

처음 운영할 때는 `PUBLISH_STATUS=draft`와 `MAX_POSTS_PER_RUN=1`로 시작하는 것을 권장합니다. 생성 품질과 레이아웃이 확인되면 `publish` 및 처리 개수를 늘리면 됩니다.
