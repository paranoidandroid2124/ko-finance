# Python 3.11-slim을 베이스 이미지로 사용
FROM python:3.11-slim

# 시스템 패키지 업데이트 및 필수 빌드 도구 설치
# (lxml, psycopg2-binary 등 라이브러리 설치에 필요할 수 있음)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# pip 업그레이드
RUN pip install --upgrade pip

# 의존성 파일 복사 및 설치
# 먼저 의존성을 설치하여 Docker 빌드 캐시를 활용
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# 소스코드 복사
COPY . .

# uvicorn, celery 등의 명령어는 docker-compose.yaml에서 실행
