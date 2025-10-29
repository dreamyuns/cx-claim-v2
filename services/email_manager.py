# services/email_manager.py - 메일 템플릿 관리
import json
from pathlib import Path
from datetime import datetime

class EmailManager:
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
    
    def get_email_templates(self):
        """메일 템플릿 반환"""
        try:
            templates = self.config.get('email_template', {})
            return {
                "success": True,
                "templates": {
                    "subject_template": templates.get('subject_template', ''),
                    "body_template": templates.get('body_template', '')
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def save_email_templates(self, templates):
        """메일 템플릿 저장"""
        try:
            # 기존 설정 로드
            config = self.load_config()
            
            # 템플릿 업데이트
            if 'email_template' not in config:
                config['email_template'] = {}
            
            config['email_template'].update(templates)
            
            # 설정 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "message": "메일 템플릿이 저장되었습니다."
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def preview_template(self, template_data):
        """메일 템플릿 미리보기"""
        try:
            from .excel_manager import ExcelManager
            
            # Excel 데이터 가져오기
            excel_manager = ExcelManager()
            excel_df = excel_manager.read_excel_data()
            
            if excel_df is None or excel_df.empty:
                return {
                    "success": False, 
                    "error": "데이터를 불러올 수 없습니다. 다시 확인해주세요"
                }
            
            # Excel 첫 번째 행 데이터 가져오기
            first_row = excel_df.iloc[0]
            
            # Excel 데이터 매핑
            sample_data = {
                'Book NO': str(first_row.get('주문번호', '')),
                '투숙자': str(first_row.get('고객명', '')),
                '투숙자명': str(first_row.get('고객명', '')),
                '요청분류': str(first_row.get('요청분류', '')),
                '요청사유': str(first_row.get('요청사유', '')),
                '요청사항': str(first_row.get('요청사항', '')),
                '요청날짜': str(first_row.get('요청날짜', '')),
                '담당자': str(first_row.get('담당자', '')),
                # Excel에 없는 데이터는 기본값
                '체크인': '2024-01-15',
                '체크아웃': '2024-01-17',
                '숙소': '그랜드 호텔 서울',
                '투숙자 연락처': '010-1234-5678',
                '박수': '2박',
                '객실수': '1',
                '객실명': '디럭스 룸',
                '상품명': '서울 2박 3일 패키지'
            }
            
            # 사용자 입력 템플릿 우선 사용
            templates = self.config.get('email_template', {})
            subject_template = template_data.get('subject_template') or templates.get('subject_template', '')
            body_template = template_data.get('body_template') or templates.get('body_template', '')
            
            # 제목 생성
            preview_subject = subject_template
            for key, value in sample_data.items():
                preview_subject = preview_subject.replace(f'{{{key}}}', str(value))
            
            # 본문 생성
            preview_body = body_template
            for key, value in sample_data.items():
                preview_body = preview_body.replace(f'{{{key}}}', str(value))
            
            return {
                "success": True,
                "preview": {
                    "subject": preview_subject,
                    "body": preview_body,
                    "sample_data": sample_data
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_template_variables(self):
        """템플릿에서 사용 가능한 변수 목록 반환"""
        try:
            templates = self.config.get('email_template', {})
            subject_template = templates.get('subject_template', '')
            body_template = templates.get('body_template', '')
            
            # 템플릿에서 변수 추출
            import re
            variables = set()
            
            # {변수명} 패턴 찾기
            pattern = r'\{([^}]+)\}'
            variables.update(re.findall(pattern, subject_template))
            variables.update(re.findall(pattern, body_template))
            
            # 변수 설명 매핑
            variable_descriptions = {
                '체크인': '체크인 날짜 (YYYY-MM-DD)',
                '체크아웃': '체크아웃 날짜 (YYYY-MM-DD)',
                '숙소': '숙소명',
                '투숙자': '투숙자명',
                'Book NO': '예약 컨펌번호',
                '요청날짜': '클레임 요청 날짜',
                '담당자': '담당자명',
                '요청분류': '요청 분류',
                '투숙자명': '투숙자명 (투숙자와 동일)',
                '투숙자 연락처': '투숙자 연락처',
                '박수': '박수 (예: 2박)',
                '객실수': '객실 수',
                '객실명': '객실명',
                '상품명': '상품명',
                '요청사유': '요청 사유',
                '요청사항': '요청 사항'
            }
            
            variable_list = []
            for var in sorted(variables):
                variable_list.append({
                    "name": var,
                    "description": variable_descriptions.get(var, "설명 없음"),
                    "example": self.get_variable_example(var)
                })
            
            return {
                "success": True,
                "variables": variable_list
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_variable_example(self, variable_name):
        """변수 예시값 반환"""
        examples = {
            '체크인': '2024-01-15',
            '체크아웃': '2024-01-17',
            '숙소': '그랜드 호텔 서울',
            '투숙자': '김철수',
            'Book NO': 'BK123456789',
            '요청날짜': '2024-01-10',
            '담당자': '이영희',
            '요청분류': '객실변경',
            '투숙자명': '김철수',
            '투숙자 연락처': '010-1234-5678',
            '박수': '2박',
            '객실수': '1',
            '객실명': '디럭스 룸',
            '상품명': '서울 2박 3일 패키지',
            '요청사유': '객실 업그레이드 요청',
            '요청사항': '더 큰 객실로 변경하고 싶습니다.'
        }
        return examples.get(variable_name, '예시값')
    
    def validate_template(self, template_text):
        """템플릿 유효성 검사"""
        try:
            # 기본 검사
            if not template_text or not template_text.strip():
                return {
                    "valid": False,
                    "message": "템플릿이 비어있습니다."
                }
            
            # 변수 형식 검사
            import re
            variables = re.findall(r'\{([^}]+)\}', template_text)
            
            if not variables:
                return {
                    "valid": True,
                    "message": "템플릿이 유효합니다. (변수 없음)"
                }
            
            # 중괄호 짝 검사
            open_count = template_text.count('{')
            close_count = template_text.count('}')
            
            if open_count != close_count:
                return {
                    "valid": False,
                    "message": "중괄호가 올바르지 않습니다."
                }
            
            return {
                "valid": True,
                "message": f"템플릿이 유효합니다. ({len(variables)}개 변수 사용)",
                "variables": variables
            }
            
        except Exception as e:
            return {
                "valid": False,
                "message": f"템플릿 검증 실패: {str(e)}"
            }
