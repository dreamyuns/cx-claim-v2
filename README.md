# CX 클레임처리 시스템 V2.0

고객 클레임 자동 처리 및 관리 시스템

## 🚀 주요 기능

- **파일 업로드**: CX Excel 파일을 웹에서 직접 업로드
- **자동 처리**: 클레임 데이터 자동 처리 및 메일 발송
- **결과 다운로드**: 처리 결과를 ZIP 파일로 다운로드
- **자동 정리**: 실행 완료 후 파일 자동 삭제

## 📁 프로젝트 구조

```
CX_클레임처리V2.0/
├── config/
│   ├── local.json      # 로컬 개발용 설정
│   └── server.json     # 서버 배포용 설정
├── frontend/
│   └── index.html      # 웹 인터페이스
├── services/
│   ├── project_executor.py
│   ├── excel_manager.py
│   └── email_manager.py
├── uploads/            # 업로드된 파일 저장
├── results/            # 처리 결과 저장
├── logs/               # 로그 파일 저장
├── claim_list/         # 클레임 리스트 저장
├── main.py             # FastAPI 서버
└── requirements.txt    # Python 패키지 목록
```

## 🛠️ 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 로컬 개발 실행
```bash
# Windows
python main.py

# Linux/Mac
ENVIRONMENT=local python main.py
```

### 3. 서버 배포 실행
```bash
# 서버 환경
ENVIRONMENT=server python main.py
```

## ⚙️ 환경 설정

### 로컬 개발 (local.json)
- Windows 경로 사용
- 개발용 설정

### 서버 배포 (server.json)
- Linux 경로 사용
- 프로덕션용 설정

## 🌐 웹 인터페이스

서버 실행 후 브라우저에서 접속:
```
http://localhost:8004
```

## 📋 사용 방법

1. **파일 업로드**: CX Excel 파일을 업로드
2. **설정 확인**: 로그인 정보 및 실행 설정 확인
3. **프로젝트 실행**: 자동 처리 시작
4. **결과 다운로드**: 처리 완료 후 ZIP 파일 다운로드

## 🔧 환경변수

- `ENVIRONMENT`: 설정 파일 선택 (local/server, 기본값: local)

## 📝 API 엔드포인트

- `GET /api/health`: 서버 상태 확인
- `GET /api/config`: 설정 로드
- `POST /api/config`: 설정 저장
- `POST /api/upload-cx-excel`: Excel 파일 업로드
- `GET /api/download-results`: 결과 파일 다운로드
- `POST /api/start`: 프로젝트 시작
- `POST /api/stop`: 프로젝트 중단
- `GET /api/status`: 실행 상태 확인

## 🚀 서버 배포

1. 서버에 Python 환경 구축
2. ChromeDriver 설치
3. 프로젝트 파일 업로드
4. 환경변수 설정: `ENVIRONMENT=server`
5. 서버 실행

## 📞 지원

문제가 발생하면 로그 파일을 확인하거나 개발팀에 문의하세요.