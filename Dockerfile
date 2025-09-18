# Dockerfile
FROM python:3.13-slim

# ── 기본 ENV ────────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# (권장) 호스트 UID/GID를 맞추면 볼륨 권한 이슈가 줄어듦
ARG APP_UID=1000
ARG APP_GID=1000
ARG APP_USER=app
ARG APP_GROUP=app

# ── 시스템 패키지 ───────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      curl \
    && rm -rf /var/lib/apt/lists/*

# ── 앱 유저/그룹 생성 ───────────────────────────────────────────────────────
RUN groupadd -g ${APP_GID} ${APP_GROUP} \
 && useradd -m -u ${APP_UID} -g ${APP_GROUP} -s /bin/bash ${APP_USER}

WORKDIR /app

# ── 파이썬 의존성 ───────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

# ── 앱 소스 복사 & 쓰기 경로 준비 ───────────────────────────────────────────
COPY . .

# staticfiles / media / beat 스케줄 저장소 등 쓰기 가능한 경로 생성
RUN mkdir -p /app/staticfiles /app/media /data \
 && chown -R ${APP_USER}:${APP_GROUP} /app /data

# ── 비루트로 전환 ───────────────────────────────────────────────────────────
USER ${APP_USER}

# 포트 노출(정보용)
EXPOSE 8000

# CMD/ENTRYPOINT는 docker-compose에서 지정
