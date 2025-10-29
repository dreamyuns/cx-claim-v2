# CX 클레임처리 V2.0 - FastAPI 서버
# 포트: 8004

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json
import os
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
        
        # 현재 설정 로드
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)