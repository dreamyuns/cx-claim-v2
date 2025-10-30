# project_executor.py - CX 클레임처리 시스템 v2.0 프로젝트 실행기
import os
import json
import uuid
import time
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 서비스 매니저들 import
from .email_manager import EmailManager
from .excel_manager import ExcelManager

class CXClaimExecutor:
    """CX 클레임처리 프로젝트 실행 관리자 v2.0"""
    
    def __init__(self):
        self.running_process = None
        self.execution_history = []
        self.current_execution_id = None
        self.script_path = Path(__file__).parent.parent / "cxlist_rpa_v2.1.py"
        self.config_path = Path(__file__).parent.parent / "cx_claim_config.json"
        self.temp_configs_dir = Path(__file__).parent.parent / "temp_configs"
        
        # 서비스 매니저들 초기화
        self.email_manager = EmailManager()
        self.excel_manager = ExcelManager()
        
        # temp_configs 디렉토리 생성
        self.temp_configs_dir.mkdir(exist_ok=True)
        
        print("CX 클레임처리 실행기 v2.0 초기화 완료")
        print(f"스크립트 경로: {self.script_path}")
        print(f"설정 파일 경로: {self.config_path}")
        print("EmailManager 및 ExcelManager 초기화 완료")
    
    def can_start_project(self) -> bool:
        """프로젝트 시작 가능 여부 확인"""
        if self.running_process is not None:
            return False
        
        if not self.script_path.exists():
            print(f"스크립트 파일이 존재하지 않음: {self.script_path}")
            return False
            
        return True
    
    def start_project(self, config_data: Dict) -> str:
        """프로젝트 시작"""
        if not self.can_start_project():
            raise Exception("프로젝트 시작 불가: 이미 실행 중이거나 스크립트 파일이 없습니다")
        
        try:
            execution_id = str(uuid.uuid4())
            temp_config_path = self._create_runtime_config(config_data, execution_id)
            
            # 환경변수 설정
            env = os.environ.copy()
            env['CONFIG_FILE_PATH'] = str(temp_config_path)
            env['EXECUTION_MODE'] = 'web_interface'  # 웹 인터페이스에서 실행
            env['EXECUTION_ID'] = execution_id
            env['PYTHONUNBUFFERED'] = '1'  # Python 출력 버퍼링 비활성화
            env['PYTHONIOENCODING'] = 'utf-8'  # 인코딩 설정
            env['PYTHONLEGACYWINDOWSSTDIO'] = '1'  # Windows에서 인코딩 문제 해결
            
            print(f"프로젝트 시작: CX 클레임처리")
            print(f"실행 ID: {execution_id}")
            print(f"스크립트 경로: {self.script_path}")
            print(f"임시 설정 파일: {temp_config_path}")
            
            # 프로세스 시작
            process = subprocess.Popen(
                ["python", "-u", str(self.script_path)],  # -u 플래그로 버퍼링 비활성화
                stdout=subprocess.PIPE,  # 출력 캡처
                stderr=subprocess.PIPE,  # 에러 캡처
                text=True,
                encoding='utf-8',  # 명시적 인코딩 설정
                errors='replace',  # 인코딩 오류 시 대체 문자 사용
                cwd=str(self.script_path.parent),
                env=env,
                bufsize=0,  # 버퍼 크기 0으로 설정
                universal_newlines=True
            )
            
            # 실행 정보 저장
            execution_info = {
                "execution_id": execution_id,
                "process": process,
                "start_time": datetime.now(),
                "status": "running",
                "config": config_data
            }
            
            self.running_process = execution_info
            self.current_execution_id = execution_id
            
            # 실행 이력에 추가
            self.execution_history.append({
                "execution_id": execution_id,
                "start_time": execution_info["start_time"],
                "status": "running",
                "config": config_data
            })
            
            # 모니터링 스레드 시작
            monitor_thread = threading.Thread(
                target=self._monitor_execution,
                args=(execution_id, process),
                daemon=False
            )
            monitor_thread.start()
            
            print(f"프로젝트 시작 완료: CX 클레임처리 (실행 ID: {execution_id})")
            return execution_id
            
        except Exception as e:
            print(f"프로젝트 시작 실패: {e}")
            raise e
    
    def stop_project(self, force: bool = False) -> bool:
        """프로젝트 중지"""
        if self.running_process is None:
            return False
        
        try:
            process = self.running_process.get("process")
            execution_id = self.running_process.get("execution_id")  # 실행 ID 미리 저장
            
            if process:
                if force:
                    # 강제 종료
                    process.kill()
                    print("프로젝트 강제 중지: CX 클레임처리")
                else:
                    # 정상 종료
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                        print("프로젝트 정상 중지: CX 클레임처리")
                    except subprocess.TimeoutExpired:
                        process.kill()
                        print("프로젝트 강제 중지 (타임아웃): CX 클레임처리")
            
            # 실행 이력 업데이트 (실행 ID를 미리 저장한 값 사용)
            for history_item in reversed(self.execution_history):
                if history_item["execution_id"] == execution_id and history_item["status"] == "running":
                    history_item["status"] = "stopped"
                    history_item["end_time"] = datetime.now()
                    break
            
            # 실행 중인 프로젝트에서 제거
            self.running_process = None
            self.current_execution_id = None
            
            return True
            
        except Exception as e:
            print(f"프로젝트 중지 실패: {e}")
            return False
    
    def get_status(self) -> Optional[Dict]:
        """프로젝트 상태 반환"""
        if self.running_process is None:
            return None
        
        info = self.running_process
        process = info.get("process")
        
        if process:
            return_code = process.poll()
            if return_code is not None:
                # 프로세스가 완료됨
                info["status"] = "completed" if return_code == 0 else "failed"
                info["end_time"] = datetime.now()
                info["return_code"] = return_code
                
                # 실행 시간 계산
                duration = info["end_time"] - info["start_time"]
                duration_str = str(duration).split('.')[0]
                
                # 실행 이력 업데이트
                for history_item in reversed(self.execution_history):
                    if history_item["execution_id"] == info["execution_id"]:
                        history_item["status"] = info["status"]
                        history_item["end_time"] = info["end_time"]
                        history_item["return_code"] = return_code
                        history_item["duration"] = duration_str
                        break
                
                # 실행 중인 프로젝트에서 제거
                self.running_process = None
                self.current_execution_id = None
                
                # 임시 설정 파일 정리
                self._cleanup_temp_config(info["execution_id"])
                
                return {
                    "execution_id": info["execution_id"],
                    "start_time": info["start_time"].isoformat(),
                    "end_time": info["end_time"].isoformat(),
                    "status": info["status"],
                    "duration": duration_str,
                    "return_code": return_code
                }
            else:
                # 프로세스가 아직 실행 중
                return {
                    "execution_id": info["execution_id"],
                    "start_time": info["start_time"].isoformat(),
                    "status": "running",
                    "duration": str(datetime.now() - info["start_time"]).split('.')[0]
                }
        
        return None
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """실행 이력 반환"""
        return self.execution_history[-limit:]
    
    def _monitor_execution(self, execution_id: str, process: subprocess.Popen):
        """실행 상태 모니터링"""
        try:
            print(f"모니터링 시작: {execution_id}")
            
            # 프로세스 완료까지 대기 (더 안전한 방식)
            try:
                # 프로세스가 정상적으로 완료될 때까지 대기
                stdout, stderr = process.communicate(timeout=None)  # 무제한 대기
                return_code = process.returncode
                
                print(f"프로세스 완료: {execution_id}, 반환 코드: {return_code}")
                if stdout:
                    print(f"stdout: {stdout}")
                if stderr:
                    print(f"stderr: {stderr}")
                    
            except subprocess.TimeoutExpired:
                print(f"프로세스 타임아웃: {execution_id}")
                process.kill()
                return_code = -1
            except UnicodeDecodeError as e:
                print(f"인코딩 오류 (무시): {e}")
                # 인코딩 오류는 무시하고 프로세스 반환 코드 사용
                return_code = process.returncode if process.returncode is not None else 0
            except Exception as e:
                print(f"프로세스 실행 오류: {e}")
                return_code = -1
            
            # 프로세스 완료 시 상태 업데이트
            self._update_project_status_from_monitor(execution_id, return_code)
            
        except Exception as e:
            print(f"모니터링 오류 ({execution_id}): {e}")
            self._update_project_status_from_monitor(execution_id, -1)
    
    def _update_project_status_from_monitor(self, execution_id: str, return_code: int):
        """모니터링에서 프로젝트 상태 업데이트"""
        try:
            if self.running_process and self.running_process["execution_id"] == execution_id:
                print(f"모니터링에서 프로젝트 상태 업데이트: {execution_id}")
                
                # 실행 정보 업데이트
                self.running_process["status"] = "completed" if return_code == 0 else "failed"
                self.running_process["end_time"] = datetime.now()
                self.running_process["return_code"] = return_code
                
                # 실행 시간 계산
                duration = self.running_process["end_time"] - self.running_process["start_time"]
                duration_str = str(duration).split('.')[0]
                
                # 실행 이력 업데이트
                for history_item in reversed(self.execution_history):
                    if history_item["execution_id"] == execution_id:
                        history_item["status"] = self.running_process["status"]
                        history_item["end_time"] = self.running_process["end_time"]
                        history_item["return_code"] = return_code
                        history_item["duration"] = duration_str
                        break
                
                # 실행 중인 프로젝트에서 제거
                self.running_process = None
                self.current_execution_id = None
                
                # 임시 설정 파일 정리
                self._cleanup_temp_config(execution_id)
                
                print(f"모니터링 완료: CX 클레임처리 -> {self.running_process['status'] if self.running_process else 'completed'}")
                
        except Exception as e:
            print(f"상태 업데이트 실패 ({execution_id}): {e}")
    
    def _create_runtime_config(self, config_data: Dict, execution_id: str) -> str:
        """런타임 설정 파일 생성"""
        try:
            # 기본 설정 파일 로드
            with open(self.config_path, 'r', encoding='utf-8') as f:
                base_config = json.load(f)
            
            # 프론트엔드 설정과 병합
            merged_config = self._merge_configs(base_config, config_data)
            
            # 임시 설정 파일 생성
            temp_config_path = self.temp_configs_dir / f"cx_claim_{execution_id}.json"
            
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                json.dump(merged_config, f, ensure_ascii=False, indent=2)
            
            print(f"런타임 설정 파일 생성: {temp_config_path}")
            return str(temp_config_path)
            
        except Exception as e:
            print(f"런타임 설정 파일 생성 실패: {e}")
            raise e
    
    def _convert_path_for_server(self, file_path: str) -> str:
        """Windows 경로를 서버 경로로 변환"""
        if not file_path:
            return file_path
            
        # Windows 경로인지 확인 (C:\ 또는 \\로 시작)
        if file_path.startswith(('C:\\', 'D:\\', 'E:\\', 'F:\\', '\\\\')):
            # Windows 경로를 Linux 경로로 변환
            # 예: C:\Users\윤성균\Documents\... → /home/user/projects/...
            
            # 프로젝트 루트 디렉토리 기준으로 변환
            project_root = Path(__file__).parent.parent
            
            # 파일명만 추출
            filename = Path(file_path).name
            
            # 서버 경로로 변환
            server_path = project_root / "data" / filename
            
            return str(server_path)
        
        return file_path

    def _merge_configs(self, base_config: Dict, frontend_config: Dict) -> Dict:
        """설정 병합"""
        merged = base_config.copy()
        
        # 프론트엔드 설정을 기본 설정에 병합
        for key, value in frontend_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key].update(value)
            else:
                merged[key] = value
        
        # 파일 경로 변환 적용
        if 'file_paths' in merged:
            file_paths = merged['file_paths']
            for path_key, path_value in file_paths.items():
                if isinstance(path_value, str):
                    file_paths[path_key] = self._convert_path_for_server(path_value)
        
        return merged
    
    def _cleanup_temp_config(self, execution_id: str):
        """임시 설정 파일 정리"""
        try:
            for config_file in self.temp_configs_dir.glob(f"cx_claim_{execution_id}.json"):
                config_file.unlink()
                print(f"임시 설정 파일 삭제: {config_file}")
        except Exception as e:
            print(f"임시 설정 파일 정리 실패: {e}")
    
    # ===== EmailManager 기능 통합 =====
    
    def get_email_templates(self):
        """메일 템플릿 반환"""
        return self.email_manager.get_email_templates()
    
    def save_email_templates(self, templates):
        """메일 템플릿 저장"""
        return self.email_manager.save_email_templates(templates)
    
    def preview_email_template(self, template_data):
        """메일 템플릿 미리보기"""
        return self.email_manager.preview_template(template_data)
    
    def get_template_variables(self):
        """템플릿 변수 목록 반환"""
        return self.email_manager.get_template_variables()
    
    def validate_email_template(self, template_text):
        """메일 템플릿 유효성 검사"""
        return self.email_manager.validate_template(template_text)
    
    # ===== ExcelManager 기능 통합 =====
    
    def get_excel_preview_data(self, limit=5):
        """Excel 데이터 미리보기"""
        return self.excel_manager.get_preview_data(limit)
    
    def get_test_mode_data(self, start_row=2, end_row=5):
        """테스트 모드 데이터 반환"""
        return self.excel_manager.get_test_mode_data(start_row, end_row)
    
    def validate_excel_file(self):
        """Excel 파일 유효성 검사"""
        return self.excel_manager.validate_excel_file()
    
    def read_excel_data(self, sheet_name="list"):
        """Excel 파일에서 데이터 읽기"""
        return self.excel_manager.read_excel_data(sheet_name)
    
    # ===== 통합 기능 =====
    
    def get_project_info(self):
        """프로젝트 전체 정보 반환"""
        try:
            # Excel 데이터 미리보기
            excel_data = self.get_excel_preview_data()
            
            # 메일 템플릿 정보
            email_templates = self.get_email_templates()
            
            # Excel 파일 유효성 검사
            excel_validation = self.validate_excel_file()
            
            # 현재 실행 상태
            current_status = self.get_status()
            
            return {
                "success": True,
                "project_info": {
                    "excel_data": excel_data,
                    "email_templates": email_templates,
                    "excel_validation": excel_validation,
                    "current_status": current_status,
                    "execution_history": self.get_history(limit=5)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def prepare_execution_data(self, config_data):
        """실행 전 데이터 준비 및 검증"""
        try:
            # Excel 파일 유효성 검사
            excel_validation = self.validate_excel_file()
            if not excel_validation["valid"]:
                return {
                    "success": False,
                    "error": f"Excel 파일 검증 실패: {excel_validation['message']}"
                }
            
            # 메일 템플릿 유효성 검사
            email_templates = self.get_email_templates()
            if not email_templates["success"]:
                return {
                    "success": False,
                    "error": f"메일 템플릿 로드 실패: {email_templates.get('error', '알 수 없는 오류')}"
                }
            
            # 테스트 모드 데이터 준비 (테스트 모드가 활성화된 경우)
            test_data = None
            if config_data.get("excel_settings", {}).get("test_mode", {}).get("enabled", False):
                start_row = config_data.get("excel_settings", {}).get("test_mode", {}).get("start_row", 2)
                end_row = config_data.get("excel_settings", {}).get("test_mode", {}).get("end_row", 5)
                test_data = self.get_test_mode_data(start_row, end_row)
            
            return {
                "success": True,
                "preparation_data": {
                    "excel_validation": excel_validation,
                    "email_templates": email_templates,
                    "test_data": test_data,
                    "total_data_count": excel_validation.get("row_count", 0)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"실행 데이터 준비 실패: {str(e)}"
            }

# 전역 인스턴스
cx_claim_executor = CXClaimExecutor()

def get_project_executor() -> CXClaimExecutor:
    """프로젝트 실행기 인스턴스 반환"""
    return cx_claim_executor