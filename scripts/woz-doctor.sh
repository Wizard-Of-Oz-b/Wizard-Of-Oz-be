#!/usr/bin/env bash
set -euo pipefail

hdr(){ echo; echo "== $1 =="; }

hdr "Docker 상태"
docker compose ps

hdr "web 바인딩 확인"
docker compose logs --tail=80 web | grep -E "Listening at:" || true
docker compose exec -T web sh -lc 'cat /proc/1/cmdline | tr "\0" " "' || true

hdr "호스트에서 엔드포인트 체크"
curl -sfI http://127.0.0.1:8000/            | head -n 1 || true
curl -sfI http://127.0.0.1:8000/api/schema/ | head -n 1
curl -sfI http://127.0.0.1:8000/api/docs/   | head -n 1

hdr "컨테이너 내부에서도 자기 자신 체크"
docker compose exec -T web bash -lc 'curl -sfI http://127.0.0.1:8000/api/schema/ | head -n 1'
docker compose exec -T web bash -lc 'curl -sfI http://127.0.0.1:8000/api/docs/   | head -n 1'

hdr "Postgres 라이브 체크"
docker compose exec -T db bash -lc 'pg_isready -U "${POSTGRES_USER:-shop}" -d "${POSTGRES_DB:-shopapi}"'

hdr "Redis 체크"
docker compose exec -T redis redis-cli ping

hdr "Celery 워커 핑"
docker compose exec -T worker bash -lc 'celery -A config inspect ping || true'

hdr "대표 API 라우트 존재(인증 필요하면 401/403도 OK)"
curl -sI http://127.0.0.1:8000/api/v1/shipments/ | head -n 1 || true

WEBHOOK_PATH="$(grep -E '^SMARTPARCEL_CALLBACK_PATH=' .env.docker 2>/dev/null | cut -d= -f2- || echo /api/v1/webhooks/shipments/sweettracker/)"
hdr "웹훅 엔드포인트 존재(GET이면 405 기대)"
curl -sI "http://127.0.0.1:8000${WEBHOOK_PATH}" | head -n 1 || true

echo; echo "== 완료 ✅ =="
