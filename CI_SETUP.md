# CI/CD 설정 가이드

이 프로젝트는 GitHub Actions를 사용한 CI/CD 파이프라인이 설정되어 있습니다.

## 🚀 설정된 기능들

### 코드 품질 검사
- **Black**: 코드 포맷팅 자동화
- **isort**: import 문 정렬
- **flake8**: 코드 린팅 (PEP8 준수)
- **bandit**: 보안 취약점 검사
- **mypy**: 타입 체킹 (타입 어노테이션 검증)

### 테스트
- **pytest**: 단위/통합 테스트 실행
- **pytest-cov**: 코드 커버리지 측정
- **pytest-xdist**: 병렬 테스트 실행

### Docker
- **개발 환경**: `Dockerfile.dev` 빌드 테스트
- **프로덕션 환경**: `Dockerfile.prod` 빌드 테스트

## 📋 워크플로우

### PR 워크플로우 (`.github/workflows/ci.yml`)
Pull Request 생성 시 자동으로 실행됩니다:

1. **환경 설정**
   - Python 3.13 설치
   - uv 패키지 매니저 설치
   - 의존성 설치

2. **코드 품질 검사**
   - Black 포맷팅 검사
   - isort import 정렬 검사
   - flake8 린팅
   - bandit 보안 검사
   - mypy 타입 체킹

3. **테스트 실행**
   - PostgreSQL, Redis 서비스 시작
   - pytest 실행 (커버리지 포함)
   - Codecov 업로드

4. **Docker 빌드**
   - 개발/프로덕션 이미지 빌드 테스트

## 🛠️ 로컬 개발 환경 설정

### 1. 의존성 설치
```bash
uv sync --dev
```

### 2. Pre-commit 설정 (선택사항)
```bash
uv run pre-commit install
```

### 3. 코드 품질 도구 실행

#### 포맷팅 적용
```bash
# Black 포맷팅
uv run black domains/ config/ shared/ api/ manage.py

# isort import 정렬
uv run isort domains/ config/ shared/ api/ manage.py
```

#### 검사만 실행
```bash
# Black 검사
uv run black --check --diff domains/ config/ shared/ api/ manage.py

# isort 검사
uv run isort --check-only --diff domains/ config/ shared/ api/ manage.py

# flake8 린팅
uv run flake8 domains/ config/ shared/ api/ manage.py

# bandit 보안 검사
uv run bandit -r domains/ config/ shared/ api/ -x tests/

# mypy 타입 체킹
uv run mypy domains/ --show-error-codes
```

### 4. 테스트 실행
```bash
# 전체 테스트
uv run pytest

# 커버리지 포함
uv run pytest --cov=domains --cov-report=html

# 병렬 실행
uv run pytest -n auto
```

## 🐳 Docker 빌드

### 개발 환경
```bash
docker build -f Dockerfile.dev -t shopapi:dev .
```

### 프로덕션 환경
```bash
docker build -f Dockerfile.prod -t shopapi:prod .
```

## 📊 코드 품질 설정

### Black 설정
- 라인 길이: 88자
- 타겟 Python 버전: 3.13
- migrations 폴더 제외

### isort 설정
- Black 호환 프로필
- Django 인식
- 프로젝트별 import 섹션 구분

### flake8 설정
- 최대 라인 길이: 88자
- Black 호환 무시 규칙
- migrations 폴더 제외

### bandit 설정
- tests 폴더 제외
- 일부 false positive 규칙 제외

## 🔧 문제 해결

### CI 실패 시 확인사항

1. **포맷팅 오류**
   ```bash
   uv run black domains/ config/ shared/ api/ manage.py
   uv run isort domains/ config/ shared/ api/ manage.py
   ```

2. **린팅 오류**
   ```bash
   uv run flake8 domains/ config/ shared/ api/ manage.py
   ```

3. **테스트 실패**
   ```bash
   uv run pytest -v
   ```

4. **Docker 빌드 실패**
   ```bash
   docker build -f Dockerfile.dev .
   ```

### 환경 변수 설정

#### CI에서 자동 설정되는 환경 변수들:
```yaml
# 데이터베이스 설정
DB_HOST: localhost
DB_PORT: 5432
DB_NAME: shopapi_test
DB_USER: postgres
DB_PASSWORD: postgres

# Redis 설정
REDIS_HOST: localhost
REDIS_PORT: 6379
REDIS_DB: 0

# Django 설정
DJANGO_SECRET_KEY: test-secret-key-for-ci-very-long-and-secure
DEBUG: false
ALLOWED_HOSTS: localhost,127.0.0.1
```

#### 로컬 개발용 .env 파일 예시:
프로젝트 루트에 `.env` 파일을 생성하세요:

```bash
# Django 설정
DJANGO_SECRET_KEY=your-secret-key-here-make-it-long-and-secure
DEBUG=1
ALLOWED_HOSTS=127.0.0.1,localhost

# 데이터베이스 설정 (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shopapi
DB_USER=postgres
DB_PASSWORD=your-db-password

# Redis 설정
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 외부 API 키들 (선택사항)
SWEETTRACKER_API_KEY=your-sweettracker-api-key
TOSS_SECRET_KEY=your-toss-secret-key
SMARTPARCEL_HOST=your-smartparcel-host

# 소셜 로그인 설정 (선택사항)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
KAKAO_CLIENT_ID=your-kakao-client-id
KAKAO_CLIENT_SECRET=your-kakao-client-secret
```

## 📈 다음 단계

추가로 설정할 수 있는 기능들:

1. **배포 자동화**
   - 스테이징/프로덕션 환경 배포
   - Docker 이미지 레지스트리 푸시

2. **고급 품질 검사**
   - mypy 타입 체크
   - SonarCloud 연동
   - 성능 테스트

3. **알림 설정**
   - Slack/Discord 알림
   - 이메일 알림

4. **보안 강화**
   - Dependabot 설정
   - 취약점 스캔 자동화
