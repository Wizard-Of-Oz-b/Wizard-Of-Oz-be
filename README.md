## 🛍️ Shop API
<small>

**Django REST Framework 기반 쇼핑몰 백엔드 API**

JWT 인증, 상품·주문·결제·배송·관리자 기능을 포함한 eCommerce 백엔드입니다.  
Docker 기반으로 개발/운영 환경을 분리하여 손쉽게 실행·배포할 수 있습니다.

</small>
---

### 🚀 주요 기능
<small>

| Domain | 설명 | 담당자 |
|:--------|:-----|:----|
| **Accounts** | 회원가입, 로그인(JWT), 사용자 정보 및 주소 관리 |이형운
| **Catalog** | 카테고리 / 상품 / 재고 관리 (`option_key` 기반 옵션) |이 혁
| **Carts** | 장바구니 CRUD, 옵션별 수량 및 재고 검증 |이 혁
| **Orders** | Checkout, 주문 생성 및 상태 관리 (paid / canceled / refunded) |이 혁
| **Payments** | Toss Payments 테스트 API 연동 (승인 / 취소 / 환불) |이 혁
| **Shipments** | 배송지 및 출고 처리 로직 |이형운
| **Admin API** | 관리자용 상품/주문/사용자 관리 (권한 기반 접근 제어) |이 혁

</small>
---

### ⚙️ 기술 스택
<small>

- Django - 웹 프레임워크
- Django REST Framework - API 개발
- Python - 프로그래밍 언어
- 데이터베이스 - RDS
- Pillow 11.3.0 - 이미지 처리
- uv - 빠른 Python 패키지 관리자
- python-dotenv 1.1.1 - 환경변수 관리
- Django Filter 25.1 - API 필터링
- 컨테이너화 & 배포 - Docker,Docker Compose - 멀티 컨테이너 오케스트레이션 
- Nginx 1.29 - 리버스 프록시 및 정적 파일 서빙
- PostgresSQL 16 - 데이터베이스 컨테이너
- Redis 7 - 캐시 컨테이너
- 비동기 작업 - Celery 5.5.3 - 비동기 작업 큐
- Django Celery Beat 2.8.1 - 스케줄링
- Celery[redis] - Redis 브로커
- 인증 & 보안 :
- HTTPS: SSL/TLS 암호화
- JWT: Bearer 토큰 인증
- CORS: Cross-Origin Resource Sharing 설정
- CSRF: Cross-Site Request Forgery 보호
- Security Headers: HSTS, XSS 보호 등
- social Auth Django - 소셜로그인
- 테스트 :
- pytest: 8.4.2 - 메인 테스트 프레임워크
- pytest-cov: 7.0.0 - 코드 커버리지
- 외부api :
- 결제 - TossApi
- 배송 추적 - SweetTracker API
- 소셜 로그인 -  OAuth 2.0 (Google, Naver, Kakao)
- HTTP 클라이언트 라이브러리
- requests - 외부 API 호출용 (Python)
- httpx - 비동기 HTTP 클라이언트 (Python)
- 도메인생성 :
- DuckDNS - 서브 도메인생성
- Let's Encrypt - 인증서생성

</small>

---

### 🧱 실행 방법

#### 1️⃣ 개발 환경
<small>

```bash
docker compose -f docker-compose.dev.yml --env-file .env.docker up -d --build
```

> Swagger Docs: [http://localhost:8000/api/v1/docs/](http://localhost:8000/api/v1/docs/)

</small>

---

#### 2️⃣ 운영 환경

<small>

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

> SSL, DB, Secret Key 등은 `.env.prod` 에서 관리

</small>

---

### 🔑 주요 API 엔드포인트

<small>

| Path | Method | Description |
|:-----|:--------|:------------|
| `/api/v1/users/me/addresses/` | GET/POST | 사용자 주소 관리 |
| `/api/v1/categories/` | GET | 카테고리 목록 |
| `/api/v1/products/` | GET | 상품 목록 |
| `/api/v1/carts/me/` | GET | 내 장바구니 |
| `/api/v1/orders/checkout/` | POST | 주문 생성 & 결제 진행 |
| `/api/v1/orders/purchases/{id}/cancel/` | POST | 주문 취소 |
| `/api/v1/payments/toss/confirm/` | POST | Toss 결제 승인 |
| `/api/v1/payments/toss/cancel/` | POST | Toss 결제 취소 |

</small>

---

### 💳 Toss Payments 테스트 결제 흐름

<small>

1️⃣ 장바구니에 상품 담기 → `/api/v1/carts/me/`  
2️⃣ 프론트엔드에서 Toss 결제창 호출  
3️⃣ 결제 성공 시 → `/api/v1/payments/toss/confirm/` 호출  
4️⃣ 서버에서 승인 후 `Purchase`, `OrderItem` 생성 및 재고 차감  
5️⃣ 결제 취소 시 → `/api/v1/payments/toss/cancel/` 처리  

> ✅ 결제 상태와 재고 동기화는 트랜잭션으로 관리됩니다.

</small>

---

---

### 🧪 테스트

<small>

```bash
pytest -v --cov=domains
```

> coverage 목표: **70% 이상**

</small>

---

### 🌐 배포 및 관리

<small>

- Docker 기반 CI/CD 자동화 (GitHub Actions)  
- `.env.prod` 기반 비밀 설정 및 SSL 관리  
- 배포링크: https://ozshop-kappa.vercel.app/

</small>

---

### 📜 API 문서

<small>

Swagger UI:  
👉 [http://localhost:8000/api/v1/docs/](http://localhost:8000/api/v1/docs/)

API 명세서:  
👉https://docs.google.com/spreadsheets/d/10ZFZkOtX4p99eucWjzxIToOO066tvRGgaQlU0hdBDfk/edit?gid=926332624#gid=926332624

ERD:  
👉https://dbdiagram.io/d/68bffa8b61a46d388e28b9e6

### 📜 발표자료

👉https://wizardofoz-seven.vercel.app/

**📍Author:** Wizard-Of-Oz-be
  
**📧 Contact:**   
이형운 : dlguddns2@naver.com  
이혁 : dnwlslzx12@gmail.com

</small>