# services/excel_manager.py - Excel 데이터 관리
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import json

class ExcelManager:
    def __init__(self):
        self.config_path = Path(__file__).parent.parent / "cx_claim_config.json"
        self.config = self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            return {}
    
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

    def get_excel_file_path(self):
        """Excel 파일 경로 반환"""
        excel_path = self.config.get('file_paths', {}).get('cx_excel', 'data/cx_list.xlsx')
        
        # Windows 경로를 서버 경로로 변환
        excel_path = self._convert_path_for_server(excel_path)
        
        # 상대 경로인 경우 프로젝트 루트 기준으로 변환
        if not os.path.isabs(excel_path):
            project_root = Path(__file__).parent.parent
            excel_path = project_root / excel_path
        
        return Path(excel_path)
    
    def read_excel_data(self, sheet_name="list"):
        """Excel 파일에서 데이터 읽기"""
        try:
            excel_path = self.get_excel_file_path()
            
            if not excel_path.exists():
                raise FileNotFoundError(f"Excel 파일을 찾을 수 없습니다: {excel_path}")
            
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            return df
            
        except Exception as e:
            print(f"Excel 파일 읽기 실패: {e}")
            return None
    
    def get_preview_data(self, limit=5):
        """데이터 미리보기 (통계 + 샘플 데이터)"""
        try:
            df = self.read_excel_data()
            
            if df is None or df.empty:
                return {
                    "total_count": 0,
                    "today_count": 0,
                    "category_stats": {},
                    "manager_stats": {},
                    "sample_data": []
                }
            
            # 기본 통계
            total_count = len(df)
            
            # 오늘 처리 대상 수 (요청날짜가 오늘인 것)
            today = datetime.now().strftime('%Y-%m-%d')
            today_count = 0
            if '요청날짜' in df.columns:
                try:
                    df['요청날짜'] = pd.to_datetime(df['요청날짜']).dt.strftime('%Y-%m-%d')
                    today_count = len(df[df['요청날짜'] == today])
                except:
                    today_count = 0
            
            # 요청 분류별 통계
            category_stats = {}
            if '요청분류' in df.columns:
                category_counts = df['요청분류'].value_counts()
                category_stats = category_counts.to_dict()
            
            # 담당자별 통계
            manager_stats = {}
            if '담당자' in df.columns:
                manager_counts = df['담당자'].value_counts()
                manager_stats = manager_counts.to_dict()
            
            # 샘플 데이터 (최대 limit개)
            sample_data = []
            sample_df = df.head(limit)
            
            for index, row in sample_df.iterrows():
                sample_data.append({
                    "no": row.get('NO', ''),
                    "order_number": row.get('주문번호', ''),
                    "customer_name": row.get('고객명', ''),
                    "request_category": row.get('요청분류', ''),
                    "request_reason": row.get('요청사유', ''),
                    "request_content": row.get('요청사항', ''),
                    "manager": row.get('담당자', ''),
                    "request_date": row.get('요청날짜', '')
                })
            
            return {
                "total_count": total_count,
                "today_count": today_count,
                "category_stats": category_stats,
                "manager_stats": manager_stats,
                "sample_data": sample_data,
                "columns": list(df.columns)
            }
            
        except Exception as e:
            print(f"데이터 미리보기 실패: {e}")
            return {
                "total_count": 0,
                "today_count": 0,
                "category_stats": {},
                "manager_stats": {},
                "sample_data": [],
                "error": str(e)
            }
    
    def get_test_mode_data(self, start_row=2, end_row=5):
        """테스트 모드 데이터 반환"""
        try:
            df = self.read_excel_data()
            
            if df is None or df.empty:
                return []
            
            # 테스트 모드 적용 (행 번호는 1부터 시작하므로 -1)
            start_idx = max(0, start_row - 1)
            end_idx = min(len(df), end_row)
            
            test_df = df.iloc[start_idx:end_idx]
            
            test_data = []
            for index, row in test_df.iterrows():
                test_data.append({
                    "no": row.get('NO', ''),
                    "order_number": row.get('주문번호', ''),
                    "customer_name": row.get('고객명', ''),
                    "request_category": row.get('요청분류', ''),
                    "request_reason": row.get('요청사유', ''),
                    "request_content": row.get('요청사항', ''),
                    "manager": row.get('담당자', ''),
                    "request_date": row.get('요청날짜', '')
                })
            
            return test_data
            
        except Exception as e:
            print(f"테스트 모드 데이터 조회 실패: {e}")
            return []
    
    def validate_excel_file(self):
        """Excel 파일 유효성 검사"""
        try:
            excel_path = self.get_excel_file_path()
            
            if not excel_path.exists():
                return {
                    "valid": False,
                    "message": f"Excel 파일을 찾을 수 없습니다: {excel_path}"
                }
            
            df = self.read_excel_data()
            
            if df is None:
                return {
                    "valid": False,
                    "message": "Excel 파일을 읽을 수 없습니다."
                }
            
            # 필수 컬럼 확인
            required_columns = ['주문번호', '고객명', '요청분류', '요청사유', '요청사항', '담당자']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    "valid": False,
                    "message": f"필수 컬럼이 없습니다: {', '.join(missing_columns)}"
                }
            
            # 데이터 개수 확인
            if len(df) == 0:
                return {
                    "valid": False,
                    "message": "처리할 데이터가 없습니다."
                }
            
            return {
                "valid": True,
                "message": f"Excel 파일이 유효합니다. (총 {len(df)}개 행)",
                "row_count": len(df),
                "columns": list(df.columns)
            }
            
        except Exception as e:
            return {
                "valid": False,
                "message": f"Excel 파일 검증 실패: {str(e)}"
            }
