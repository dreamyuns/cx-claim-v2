# CX 클레임처리 V2.0 - FastAPI 서버
# 포트: 8004

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
import threading
import time
import subprocess
import signal
import psutil

# FastAPI 앱 생성
app = FastAPI(
    title="CX 클레임처리 시스템 V2.0",
    description="CX 클레임처리 자동화 시스템 - 프론트엔드 연동 버전",
    version="2.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (HTML, CSS, JavaScript 파일들)
frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# 프로젝트 실행기 import
from services.project_executor import get_project_executor

# 업로드 디렉토리 설정
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 결과 디렉토리 설정
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# 로그 디렉토리 설정
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 클레임 리스트 디렉토리 설정
CLAIM_LIST_DIR = Path(__file__).parent / "claim_list"
CLAIM_LIST_DIR.mkdir(exist_ok=True)

# 전역 변수
current_process = None
execution_status = {
    "status": "idle",  # idle, running, completed, error
    "message": "대기 중",
    "progress": 0,
    "start_time": None,
    "end_time": None,
    "execution_id": None
}

# 메인 페이지 라우트
@app.get("/")
async def read_root():
    """메인 페이지 반환"""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return HTMLResponse(content="<h1>CX 클레임처리 V2.0</h1><p>프론트엔드 파일을 찾을 수 없습니다.</p>")

# 서버 상태 확인 API
@app.get("/api/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "message": "CX 클레임처리 시스템 V2.0이 정상 작동 중입니다.",
        "version": "2.0.0",
        "project": "cx_claim"
    }

# 설정 로드 API
@app.get("/api/config")
async def get_config():
    """프로젝트 설정 로드"""
    try:
        # 환경변수로 설정 파일 선택 (기본값: local)
        environment = os.getenv('ENVIRONMENT', 'local')
        config_path = Path(__file__).parent / "config" / f"{environment}.json"
        
        # 설정 파일이 없으면 기본 설정 파일 사용
        if not config_path.exists():
            config_path = Path(__file__).parent / "cx_claim_config.json"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return {"success": True, "config": config}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 설정 저장 API
@app.post("/api/config")
async def save_config(config_data: dict):
    """프로젝트 설정 저장"""
    try:
        # 환경변수로 설정 파일 선택 (기본값: local)
        environment = os.getenv('ENVIRONMENT', 'local')
        config_path = Path(__file__).parent / "config" / f"{environment}.json"
        
        # 설정 파일이 없으면 기본 설정 파일 사용
        if not config_path.exists():
            config_path = Path(__file__).parent / "cx_claim_config.json"
        
        # 기존 설정 로드
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
        except:
            existing_config = {}
        
        # 새 설정과 기존 설정 병합
        existing_config.update(config_data)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(existing_config, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "설정이 저장되었습니다"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 프로젝트 시작 API
@app.post("/api/start")
async def start_project():
    """프로젝트 시작"""
    global execution_status
    
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 이미 실행 중인지 확인
        if not executor.can_start_project():
            return {"success": False, "message": "이미 실행 중입니다."}
        
        # 현재 설정 로드 (환경별 설정 파일 사용)
        environment = os.getenv('ENVIRONMENT', 'local')
        config_path = Path(__file__).parent / "config" / f"{environment}.json"
        
        # 설정 파일이 없으면 기본 설정 파일 사용
        if not config_path.exists():
            config_path = Path(__file__).parent / "cx_claim_config.json"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 프로젝트 시작
        execution_id = executor.start_project(config_data)
        
        # 실행 상태 업데이트
        execution_status.update({
            "status": "running",
            "message": "실행 중",
            "progress": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "execution_id": execution_id
        })
        
        # 백그라운드에서 실행 완료 모니터링 시작
        threading.Thread(target=monitor_execution_completion, args=(execution_id,), daemon=True).start()
        
        return {
            "success": True, 
            "message": "프로젝트가 시작되었습니다.",
            "execution_id": execution_id
        }
        
    except Exception as e:
        execution_status["status"] = "error"
        execution_status["message"] = f"시작 실패: {str(e)}"
        return {"success": False, "message": f"프로젝트 시작 실패: {str(e)}"}

# 프로젝트 중단 API
@app.post("/api/stop")
async def stop_project():
    """프로젝트 중단"""
    global execution_status
    
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 프로젝트 중단
        success = executor.stop_project(force=False)
        
        if success:
            execution_status.update({
                "status": "completed",
                "message": "사용자에 의해 중단됨",
                "end_time": datetime.now().isoformat()
            })
            return {"success": True, "message": "프로젝트가 중단되었습니다."}
        else:
            return {"success": False, "message": "실행 중인 프로젝트가 없습니다."}
            
    except Exception as e:
        return {"success": False, "message": f"프로젝트 중단 실패: {str(e)}"}

# 프로젝트 상태 확인 API
@app.get("/api/status")
async def get_status():
    """프로젝트 실행 상태"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 실행기에서 상태 가져오기
        executor_status = executor.get_status()
        
        if executor_status:
            # 실행 중인 프로젝트가 있는 경우
            return {
                "success": True,
                "status": executor_status["status"],
                "message": f"실행 중 - {executor_status['status']}",
                "progress": 50 if executor_status["status"] == "running" else 100,
                "start_time": executor_status["start_time"],
                "end_time": executor_status.get("end_time"),
                "execution_id": executor_status["execution_id"]
            }
        else:
            # 실행 중인 프로젝트가 없는 경우
            return {
                "success": True,
                "status": "idle",
                "message": "대기 중",
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "execution_id": None
            }
            
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": f"상태 확인 실패: {str(e)}",
            "progress": 0,
            "start_time": None,
            "end_time": None,
            "execution_id": None
        }

# 실행 이력 API
@app.get("/api/history")
async def get_execution_history():
    """실행 이력 조회"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 실행 이력 가져오기
        history = executor.get_history(limit=20)
        
        # 이력 데이터 포맷팅
        formatted_history = []
        for item in history:
            formatted_history.append({
                "execution_id": item["execution_id"],
                "start_time": item["start_time"].isoformat() if isinstance(item["start_time"], datetime) else item["start_time"],
                "end_time": item.get("end_time").isoformat() if item.get("end_time") and isinstance(item["end_time"], datetime) else item.get("end_time"),
                "status": item["status"],
                "duration": item.get("duration"),
                "return_code": item.get("return_code")
            })
        
        return {"success": True, "history": formatted_history}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 데이터 미리보기 API
@app.get("/api/excel-data")
async def get_excel_data():
    """Excel 데이터 미리보기"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # Excel 데이터 미리보기
        data = executor.get_excel_preview_data()
        
        return {"success": True, "data": data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 메일 템플릿 미리보기 API
@app.post("/api/email-preview")
async def preview_email_template(template_data: dict):
    """메일 템플릿 미리보기"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 메일 템플릿 미리보기
        preview = executor.preview_email_template(template_data)
        
        return {"success": True, "preview": preview}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 추가 API들

# 프로젝트 정보 API
@app.get("/api/project-info")
async def get_project_info():
    """프로젝트 전체 정보 반환"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 프로젝트 정보 반환
        project_info = executor.get_project_info()
        
        return project_info
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# Excel 파일 유효성 검사 API
@app.get("/api/validate-excel")
async def validate_excel():
    """Excel 파일 유효성 검사"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # Excel 파일 유효성 검사
        validation = executor.validate_excel_file()
        
        return {"success": True, "validation": validation}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 테스트 모드 데이터 API
@app.get("/api/test-data")
async def get_test_data(start_row: int = 2, end_row: int = 5):
    """테스트 모드 데이터 반환"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 테스트 모드 데이터 반환
        test_data = executor.get_test_mode_data(start_row, end_row)
        
        return {"success": True, "test_data": test_data}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 메일 템플릿 변수 목록 API
@app.get("/api/email-variables")
async def get_email_variables():
    """메일 템플릿 변수 목록 반환"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 템플릿 변수 목록 반환
        variables = executor.get_template_variables()
        
        return variables
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 실행 전 데이터 준비 API
@app.post("/api/prepare-execution")
async def prepare_execution(config_data: dict):
    """실행 전 데이터 준비 및 검증"""
    try:
        # 프로젝트 실행기 가져오기
        executor = get_project_executor()
        
        # 실행 데이터 준비
        preparation = executor.prepare_execution_data(config_data)
        
        return preparation
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===== 실행 완료 모니터링 =====

def monitor_execution_completion(execution_id: str):
    """실행 완료 모니터링 및 자동 파일 정리"""
    try:
        executor = get_project_executor()
        
        # 실행 완료까지 대기
        while True:
            status = executor.get_status()
            if status is None or status.get("status") in ["completed", "failed", "stopped"]:
                break
            time.sleep(5)  # 5초마다 확인
        
        # 실행 완료 후 30초 대기 (사용자가 결과를 다운로드할 시간 제공)
        time.sleep(30)
        
        # 파일 정리 실행
        try:
            import requests
            response = requests.post("http://localhost:8004/api/cleanup-files")
            if response.status_code == 200:
                print(f"실행 완료 후 파일 정리 완료: {execution_id}")
            else:
                print(f"파일 정리 실패: {execution_id}")
        except Exception as e:
            print(f"파일 정리 중 오류: {e}")
            
    except Exception as e:
        print(f"실행 완료 모니터링 오류: {e}")

# ===== 파일 업로드/다운로드 API =====

# CX Excel 파일 업로드 API
@app.post("/api/upload-cx-excel")
async def upload_cx_excel(file: UploadFile = File(...)):
    """CX Excel 파일 업로드"""
    try:
        # 파일 확장자 검증
        allowed_extensions = ['.xlsx', '.xls', '.csv']
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            return {
                "success": False, 
                "error": f"지원하지 않는 파일 형식입니다. 허용된 형식: {', '.join(allowed_extensions)}"
            }
        
        # 파일 크기 검증 (10MB)
        file_content = await file.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB
            return {
                "success": False,
                "error": "파일 크기가 10MB를 초과합니다."
            }
        
        # 파일명 생성 (중복 방지)
        original_filename = Path(file.filename).stem
        file_extension = Path(file.filename).suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{original_filename}_{timestamp}{file_extension}"
        
        # 파일 저장
        file_path = UPLOAD_DIR / new_filename
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # 설정 파일 업데이트 (환경별 설정 파일 사용)
        environment = os.getenv('ENVIRONMENT', 'local')
        config_path = Path(__file__).parent / "config" / f"{environment}.json"
        
        # 설정 파일이 없으면 기본 설정 파일 사용
        if not config_path.exists():
            config_path = Path(__file__).parent / "cx_claim_config.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            config = {}
        
        # 파일 경로 업데이트
        if 'file_paths' not in config:
            config['file_paths'] = {}
        config['file_paths']['cx_excel'] = str(file_path)
        
        # 설정 파일 저장
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": "파일이 성공적으로 업로드되었습니다.",
            "filename": new_filename,
            "file_size": len(file_content),
            "upload_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": f"파일 업로드 실패: {str(e)}"}

# 업로드된 파일 정보 조회 API
@app.get("/api/uploaded-files")
async def get_uploaded_files():
    """업로드된 파일 정보 조회"""
    try:
        files_info = []
        
        # CX Excel 파일 정보 (환경별 설정 파일 사용)
        environment = os.getenv('ENVIRONMENT', 'local')
        config_path = Path(__file__).parent / "config" / f"{environment}.json"
        
        # 설정 파일이 없으면 기본 설정 파일 사용
        if not config_path.exists():
            config_path = Path(__file__).parent / "cx_claim_config.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                cx_excel_path = config.get('file_paths', {}).get('cx_excel', '')
                if cx_excel_path and Path(cx_excel_path).exists():
                    file_stat = Path(cx_excel_path).stat()
                    files_info.append({
                        "type": "cx_excel",
                        "filename": Path(cx_excel_path).name,
                        "file_size": file_stat.st_size,
                        "upload_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "path": str(cx_excel_path)
                    })
        except:
            pass
        
        return {"success": True, "files": files_info}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 결과 파일 다운로드 API (ZIP)
@app.get("/api/download-results")
async def download_results():
    """결과 파일들을 ZIP으로 다운로드"""
    try:
        # ZIP 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"results_{timestamp}.zip"
        zip_path = UPLOAD_DIR / zip_filename
        
        # ZIP 파일 생성
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # results 폴더의 모든 파일 추가 (gitkeep 제외)
            if RESULTS_DIR.exists():
                for file_path in RESULTS_DIR.rglob('*'):
                    if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                        arcname = f"results/{file_path.relative_to(RESULTS_DIR)}"
                        zipf.write(file_path, arcname)
            
            # logs 폴더의 모든 파일 추가 (gitkeep 제외)
            if LOGS_DIR.exists():
                for file_path in LOGS_DIR.rglob('*'):
                    if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                        arcname = f"logs/{file_path.relative_to(LOGS_DIR)}"
                        zipf.write(file_path, arcname)
            
            # claim_list 폴더의 모든 파일 추가 (gitkeep 제외)
            if CLAIM_LIST_DIR.exists():
                for file_path in CLAIM_LIST_DIR.rglob('*'):
                    if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                        arcname = f"claim_list/{file_path.relative_to(CLAIM_LIST_DIR)}"
                        zipf.write(file_path, arcname)
        
        # ZIP 파일이 비어있는지 확인
        if zip_path.stat().st_size == 0:
            zip_path.unlink()  # 빈 파일 삭제
            return {"success": False, "error": "다운로드할 파일이 없습니다."}
        
        # 파일 스트리밍 응답
        def iter_file():
            with open(zip_path, "rb") as file:
                while chunk := file.read(8192):
                    yield chunk
            # 전송 완료 후 임시 ZIP 파일 삭제
            zip_path.unlink()
        
        return StreamingResponse(
            iter_file(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
        
    except Exception as e:
        return {"success": False, "error": f"다운로드 실패: {str(e)}"}

# 결과 파일 목록 조회 API
@app.get("/api/results-list")
async def get_results_list():
    """결과 파일 목록 조회"""
    try:
        results_info = {
            "results": [],
            "logs": [],
            "claim_list": []
        }
        
        # results 폴더 파일들 (gitkeep 제외)
        if RESULTS_DIR.exists():
            for file_path in RESULTS_DIR.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                    file_stat = file_path.stat()
                    results_info["results"].append({
                        "filename": file_path.name,
                        "file_size": file_stat.st_size,
                        "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "path": str(file_path)
                    })
        
        # logs 폴더 파일들 (gitkeep 제외)
        if LOGS_DIR.exists():
            for file_path in LOGS_DIR.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                    file_stat = file_path.stat()
                    results_info["logs"].append({
                        "filename": file_path.name,
                        "file_size": file_stat.st_size,
                        "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "path": str(file_path)
                    })
        
        # claim_list 폴더 파일들 (gitkeep 제외)
        if CLAIM_LIST_DIR.exists():
            for file_path in CLAIM_LIST_DIR.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.gitkeep'):
                    file_stat = file_path.stat()
                    results_info["claim_list"].append({
                        "filename": file_path.name,
                        "file_size": file_stat.st_size,
                        "modified_time": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "path": str(file_path)
                    })
        
        return {"success": True, "files": results_info}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# 파일 정리 API (실행 완료 후 호출)
@app.post("/api/cleanup-files")
async def cleanup_files():
    """실행 완료 후 파일 정리"""
    try:
        cleaned_files = []
        
        # 업로드된 파일들 삭제
        for file_path in UPLOAD_DIR.glob('*'):
            if file_path.is_file():
                file_path.unlink()
                cleaned_files.append(file_path.name)
        
        # results 폴더 파일들 삭제
        if RESULTS_DIR.exists():
            for file_path in RESULTS_DIR.rglob('*'):
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_files.append(f"results/{file_path.name}")
        
        # logs 폴더 파일들 삭제
        if LOGS_DIR.exists():
            for file_path in LOGS_DIR.rglob('*'):
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_files.append(f"logs/{file_path.name}")
        
        # claim_list 폴더 파일들 삭제
        if CLAIM_LIST_DIR.exists():
            for file_path in CLAIM_LIST_DIR.rglob('*'):
                if file_path.is_file():
                    file_path.unlink()
                    cleaned_files.append(f"claim_list/{file_path.name}")
        
        return {
            "success": True,
            "message": f"{len(cleaned_files)}개의 파일이 정리되었습니다.",
            "cleaned_files": cleaned_files
        }
        
    except Exception as e:
        return {"success": False, "error": f"파일 정리 실패: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)