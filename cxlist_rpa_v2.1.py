import os
import time
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager  # 시스템 ChromeDriver 사용으로 주석 처리
from selenium.common.exceptions import TimeoutException, WebDriverException

# ✅ 1. [설정 파일 로드]
# 실행기(UI)에서 내려주는 임시 설정 파일 우선 사용 (환경변수)
runtime_config_path = os.environ.get('CONFIG_FILE_PATH')
default_config_path = os.path.join(os.path.dirname(__file__), 'cx_claim_config.json')
config_file = runtime_config_path if runtime_config_path and os.path.exists(runtime_config_path) else default_config_path

print(f"설정 파일 경로: {config_file}")

try:
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    print(f"설정 파일 로드 완료: {config_file}")
except FileNotFoundError:
    print(f"오류: {config_file} 파일을 찾을 수 없습니다.")
    exit(1)
except json.JSONDecodeError as e:
    print(f"오류: {config_file} 파일 형식이 잘못되었습니다. {e}")
    exit(1)

# ✅ 2. [초기화] 로그 및 결과 디렉토리 생성
today = datetime.now().strftime('%Y%m%d')

# 설정 파일의 로그/결과/클레임 디렉토리 사용
log_dir = config['file_paths']['logs_dir']
result_dir = config['file_paths']['results_dir']
claim_dir = config['file_paths']['claim_list_dir']

# 서버에서 Windows 스타일 경로가 들어온 경우 안전한 로컬 경로로 보정
def _normalize_dir(path_value, fallback_name):
    if not isinstance(path_value, str) or not path_value.strip():
        return os.path.join(os.path.dirname(__file__), fallback_name)
    # Windows 드라이브 경로나 역슬래시 포함 시 보정
    if ":\\" in path_value or "\\" in path_value:
        return os.path.join(os.path.dirname(__file__), fallback_name)
    return path_value

log_dir = _normalize_dir(log_dir, 'logs')
result_dir = _normalize_dir(result_dir, 'results')
claim_dir = _normalize_dir(claim_dir, 'claim_list')

print(f"로그 디렉토리: {log_dir}")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(result_dir, exist_ok=True)
os.makedirs(claim_dir, exist_ok=True)

# 전역 변수
main_window = None
log_file = None
result_file = None
# 프로젝트별 독립적인 Lock 파일 (동시 실행 방지)
try:
    script_dir = os.path.dirname(__file__)
except NameError:
    # __file__이 정의되지 않은 경우 현재 작업 디렉토리 사용
    script_dir = os.getcwd()
lock_file = os.path.join(script_dir, 'cx_claim_scheduler.lock')

# ✅ Lock 파일 관리 (동시 실행 방지)
def check_lock_file():
    """Lock 파일 확인 (동시 실행 방지)"""
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                lock_time = f.read().strip()
            print(f"⚠️ 다른 프로세스가 실행 중입니다. Lock 시간: {lock_time}")
            return False
        except:
            # Lock 파일이 손상된 경우 삭제
            os.remove(lock_file)
            return True
    return True

def create_lock_file():
    """Lock 파일 생성"""
    try:
        with open(lock_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
    except:
        return False

def remove_lock_file():
    """Lock 파일 제거"""
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

# ✅ 자동 인덱스 파일명 생성 함수
def generate_log_filename(base_dir, prefix, today):
    index = 1
    while True:
        file_name = f"{prefix}_{index:03}_{today}.txt"
        full_path = os.path.join(base_dir, file_name)
        if not os.path.exists(full_path):
            return full_path
        index += 1

# ✅ 로그 및 결과 파일명 자동 생성
log_file = generate_log_filename(log_dir, "발송여부", today)
result_file = generate_log_filename(result_dir, "에러로그", today)

# ✅ 안전한 타이밍 접근자
def get_timing(name, default_seconds):
    try:
        return float(config.get('timing', {}).get(name, default_seconds))
    except Exception:
        return float(default_seconds)

# ✅ 로그 파일에 기록
def log_debug(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_content = f"[{timestamp}] {message}"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_content + '\n')
    print(message)

# ✅ 결과 파일에 기록
def log_result(order_number, email_subject, status, timestamp):
    result_content = f"{order_number}\t{email_subject}\t{status}\t{timestamp}"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(result_content + '\n')
    log_debug(f"결과 기록: {result_content}")

# ✅ 에러 로그 기록
def log_error(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    error_content = f"[{timestamp}] ERROR: {message}"
    with open(result_file, 'a', encoding='utf-8') as f:
        f.write(error_content + '\n')
    print(f"ERROR: {message}")

# ✅ 실행 시작 로그
def log_start():
    log_debug("=" * 60)
    log_debug(f"실행 파일: cxlist_rpa_v2.1.py")
    log_debug(f"실행 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_debug(f"로그 파일: {log_file}")
    log_debug(f"에러 로그 파일: {result_file}")
    log_debug("=" * 60)

# ✅ 파일명 특수문자 제거 함수
def clean_filename(filename):
    # 별표, 동그라미, 세모 등 특수문자 제거
    special_chars = ['*', '●', '▲', '■', '◆', '★', '☆', '◎', '○', '△', '□', '◇']
    for char in special_chars:
        filename = filename.replace(char, '')
    # 파일명에 사용할 수 없는 문자 제거
    filename = re.sub(r'[<>:"/\\|?]', '', filename)
    return filename.strip()

# ✅ 박수 계산 함수
def calculate_nights(checkin_str, checkout_str):
    try:
        checkin = datetime.strptime(checkin_str, '%Y-%m-%d')
        checkout = datetime.strptime(checkout_str, '%Y-%m-%d')
        nights = (checkout - checkin).days
        return f"{nights}박"
    except:
        return "계산불가"

# ✅ Book NO에서 시간 정보 제거 함수
def clean_book_no(book_no):
    """Book NO에서 시간 정보(00:00:00)를 제거합니다."""
    if not book_no:
        return book_no
    
    # 시간 패턴 제거 (00:00:00, 12:34:56 등)
    book_no = re.sub(r'\s+\d{2}:\d{2}:\d{2}$',  '', str(book_no))
    return book_no.strip()

# ✅ 날짜 형식 변환 함수
def format_date_to_yyyy_mm_dd(date_value):
    """날짜를 YYYY-MM-DD 형식으로 변환합니다."""
    if not date_value or pd.isna(date_value):
        return ""
    
    try:
        # pandas datetime 객체인 경우
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y-%m-%d')
        
        # 문자열인 경우
        date_str = str(date_value)
        
        # 이미 YYYY-MM-DD 형식인 경우
        if re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # 다른 형식의 날짜를 파싱하여 YYYY-MM-DD로 변환
        try:
            # 다양한 날짜 형식 시도
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y']:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
        except:
            pass
        
        return date_str
    except:
        return str(date_value)

# ✅ 3. [엑셀 파일 읽기]
def read_cx_excel_data(excel_file_path, sheet_name, test_mode=None):
    """cx_list.xlsx 파일에서 데이터를 읽어옵니다."""
    try:
        print(f"3-0. 엑셀 파일 읽기: {excel_file_path}")
        
        # 엑셀 파일 읽기
        df = pd.read_excel(excel_file_path, sheet_name=sheet_name)
        print(f"3-0-1. 엑셀 파일 읽기 완료: {len(df)}개 행")
        print(f"3-0-2. 컬럼명: {list(df.columns)}")
        
        # 테스트 모드 적용
        if test_mode and test_mode.get('enabled', False):
            start_row = test_mode.get('start_row', 2) - 2  # 2행을 0으로 하는 상대 인덱스
            end_row = test_mode.get('end_row', len(df) + 1) - 1  # 2행 기준 상대 인덱스
            df = df.iloc[start_row:end_row]
            print(f"3-0-3. 테스트 모드 적용: {test_mode['start_row']}~{test_mode['end_row']}행 ({len(df)}개)")
        
        # 데이터 추출
        excel_data = []
        for index, row in df.iterrows():
            order_number = str(row['주문번호']).strip() if pd.notna(row['주문번호']) else ""
            
            if order_number and order_number != 'nan':
                excel_data.append({
                    'no': row['NO'] if pd.notna(row['NO']) else "",
                    'request_date': format_date_to_yyyy_mm_dd(row['요청날짜']),
                    'manager': row['담당자'] if pd.notna(row['담당자']) else "",
                    'order_number': order_number,
                    'customer_name': row['고객명'] if pd.notna(row['고객명']) else "",
                    'request_category': row['요청분류'] if pd.notna(row['요청분류']) else "",
                    'request_reason': row['요청사유'] if pd.notna(row['요청사유']) else "",
                    'request_content': row['요청사항'] if pd.notna(row['요청사항']) else ""
                })
                print(f"3-0-4. 데이터 {len(excel_data)}: 주문번호={order_number}, 담당자={row['담당자']}")
        
        print(f"3-0-5. 최종 처리 데이터: {len(excel_data)}개")
        return excel_data
        
    except Exception as e:
        print(f"3-0. 엑셀 파일 읽기 실패: {e}")
        log_error(f"엑셀 파일 읽기 실패: {e}")
        return []

# ✅ 4. [주문번호로 검색]
def search_order_by_number(order_number):
    """주문번호로 검색하여 검색결과 페이지로 이동합니다."""
    try:
        print(f"4-1. 주문번호 검색: {order_number}")
        
        # 검색 URL 생성 (모든 파라미터 포함)
        search_url = (
            f"{config['urls']['base_url']}/orders?"
            f"appointDayType=&"
            f"exChannelId=&"
            f"nationIdx=&"
            f"addr1Idx=&"
            f"gradeType=&"
            f"perPage=20&"
            f"orderChannelIdx=&"
            f"ratepalnSaleType=&"
            f"saleType=&"
            f"payStatus=&"
            f"orderProductStatus=&"
            f"orderRateplanType=&"
            f"dateType=useDate&"
            f"startDate=&"
            f"endDate=&"
            f"searchType=orderNum&"
            f"keyword={order_number}"
        )
        print(f"4-1-1. 검색 URL: {search_url}")
        
        # 검색 페이지로 이동
        driver.get(search_url)
        time.sleep(get_timing('page_load_wait', 2))
        print(f"4-1-2. 검색 페이지 이동 완료")
        
        # 검색 결과 페이지 안정화 대기
        time.sleep(2)
        print(f"4-1-3. 검색 후 페이지 제목: {driver.title}")
        
        return True
        
    except Exception as e:
        print(f"4-1. 주문번호 검색 실패: {e}")
        log_error(f"주문번호 {order_number} 검색 실패: {e}")
        return False

# ✅ 5. [HTML 요소에서 데이터 추출]
def extract_reservation_data(order_number):
    """검색 결과 페이지에서 예약 정보를 추출합니다."""
    try:
        print(f"5-1. 예약 정보 추출: {order_number}")
        
        # 주문번호가 포함된 행 찾기
        order_row = None
        try:
            # data-order_num 속성으로 찾기
            order_row = driver.find_element(By.CSS_SELECTOR, f"tr[data-order_num='{order_number}']")
        except:
            # 주문번호 링크로 찾기
            try:
                order_link = driver.find_element(By.CSS_SELECTOR, f"a.blue_link[href='/orders/{order_number}']")
                order_row = order_link.find_element(By.XPATH, "./ancestor::tr")
            except:
                print(f"5-1-1. 주문번호 {order_number} 행을 찾을 수 없습니다.")
                return None
        
        if not order_row:
            print(f"5-1-2. 주문번호 {order_number} 데이터를 찾을 수 없습니다.")
            return None
        
        # 데이터 추출
        data = {}
        
        # 체크인/체크아웃 날짜
        try:
            checkin = order_row.get_attribute('data-checkin')
            checkout = order_row.get_attribute('data-checkout')
            data['checkin'] = checkin if checkin else ""
            data['checkout'] = checkout if checkout else ""
            data['nights'] = calculate_nights(checkin, checkout) if checkin and checkout else ""
        except Exception as e:
            print(f"5-1-3. 체크인/체크아웃 추출 실패: {e}")
            data['checkin'] = ""
            data['checkout'] = ""
            data['nights'] = ""
        
        # 숙소명, 객실명, 상품명
        try:
            order_title = order_row.find_element(By.CSS_SELECTOR, "div.order_title")
            divs = order_title.find_elements(By.TAG_NAME, "div")
            
            if len(divs) >= 1:
                # 숙소명 (버튼 제거 후 텍스트 추출)
                hotel_text = divs[0].text.strip()
                # 버튼 텍스트 제거 (숫자나 아이콘)
                hotel_text = re.sub(r'^\d+\s*', '', hotel_text)  # 앞의 숫자 제거
                data['hotel_name'] = hotel_text
            else:
                data['hotel_name'] = ""
            
            if len(divs) >= 2:
                # 객실명 (● 제거)
                room_text = divs[1].text.strip()
                data['room_name'] = room_text.replace('●', '').strip()
            else:
                data['room_name'] = ""
            
            if len(divs) >= 3:
                # 상품명 (LMS확인 링크 제거)
                product_text = divs[2].text.strip()
                data['product_name'] = product_text.replace('LMS확인', '').strip()
            else:
                data['product_name'] = ""
                
        except Exception as e:
            print(f"5-1-4. 숙소/객실/상품명 추출 실패: {e}")
            data['hotel_name'] = ""
            data['room_name'] = ""
            data['product_name'] = ""
        
        # 투숙자명, 연락처
        try:
            guest_cell = order_row.find_elements(By.TAG_NAME, "td")[13]  # 투숙자명 컬럼
            guest_divs = guest_cell.find_elements(By.TAG_NAME, "div")
            
            if len(guest_divs) >= 1:
                data['guest_name'] = guest_divs[0].text.strip()
            else:
                data['guest_name'] = ""
            
            if len(guest_divs) >= 2:
                data['guest_phone'] = guest_divs[1].text.strip()
            else:
                data['guest_phone'] = ""
                
        except Exception as e:
            print(f"5-1-5. 투숙자 정보 추출 실패: {e}")
            data['guest_name'] = ""
            data['guest_phone'] = ""
        
        # 객실수
        try:
            room_count_cell = order_row.find_elements(By.TAG_NAME, "td")[8]  # 객실수 컬럼
            room_count_div = room_count_cell.find_element(By.TAG_NAME, "div")
            data['room_count'] = room_count_div.text.strip()
        except Exception as e:
            print(f"5-1-6. 객실수 추출 실패: {e}")
            data['room_count'] = ""
        
        # Book NO (컨펌번호)
        try:
            confirm_form = order_row.find_element(By.CSS_SELECTOR, "form.send_confirm")
            confirm_input = confirm_form.find_element(By.CSS_SELECTOR, "input.confirm_input")
            raw_book_no = confirm_input.get_attribute('value')
            data['book_no'] = clean_book_no(raw_book_no)
        except Exception as e:
            print(f"5-1-7. Book NO 추출 실패: {e}")
            data['book_no'] = ""
        
        print(f"5-1-8. 추출 완료: {data}")
        return data
        
    except Exception as e:
        print(f"5-1. 데이터 추출 실패: {e}")
        log_error(f"주문번호 {order_number} 데이터 추출 실패: {e}")
        return None

# ✅ 6. [엑셀 파일 생성]
def create_claim_excel(order_number, hotel_name, data):
    """클레임 엑셀 파일을 생성합니다."""
    try:
        print(f"6-1. 클레임 엑셀 파일 생성: {order_number}")
        
        # 파일명 생성 (주문번호_숙소명_날짜 형식)
        clean_hotel_name = clean_filename(hotel_name)
        excel_filename = f"{order_number}_{clean_hotel_name}_{today}_001.xlsx"
        excel_path = os.path.join(claim_dir, excel_filename)
        
        # 중복 파일명 처리
        index = 1
        while os.path.exists(excel_path):
            excel_filename = f"{order_number}_{clean_hotel_name}_{today}_{index:03}.xlsx"
            excel_path = os.path.join(claim_dir, excel_filename)
            index += 1
        
        # 데이터프레임 생성
        df_data = {
            '숙소명': [data.get('hotel_name', '')],
            '주문번호': [order_number],
            '투숙자명': [data.get('guest_name', '')],
            '투숙자 연락처': [data.get('guest_phone', '')],
            '체크인': [data.get('checkin', '')],
            '체크아웃': [data.get('checkout', '')],
            '박수': [data.get('nights', '')],
            '객실수': [data.get('room_count', '')],
            '객실명': [data.get('room_name', '')],
            '상품명': [data.get('product_name', '')],
            'Book NO': [data.get('book_no', '')]
        }
        
        df = pd.DataFrame(df_data)
        
        # 엑셀 파일 저장
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"6-1-1. 엑셀 파일 저장 완료: {excel_path}")
        
        return excel_path
        
    except Exception as e:
        print(f"6-1. 엑셀 파일 생성 실패: {e}")
        log_error(f"주문번호 {order_number} 엑셀 파일 생성 실패: {e}")
        return None

# ✅ 7. [메일 텍스트 생성]
def create_email_content(cx_data, web_data):
    """메일 제목과 본문을 생성합니다."""
    try:
        print(f"7-1. 메일 내용 생성")
        
        # 템플릿 가져오기
        subject_template = config['email_template']['subject_template']
        body_template = config['email_template']['body_template']
        
        # 데이터 매핑
        template_data = {
            '체크인': web_data.get('checkin', ''),
            '체크아웃': web_data.get('checkout', ''),
            '숙소': web_data.get('hotel_name', ''),
            '투숙자': web_data.get('guest_name', ''),
            'Book NO': web_data.get('book_no', ''),
            '요청날짜': str(cx_data.get('request_date', '')),
            '담당자': cx_data.get('manager', ''),
            '요청분류': cx_data.get('request_category', ''),
            '투숙자명': web_data.get('guest_name', ''),
            '투숙자 연락처': web_data.get('guest_phone', ''),
            '박수': web_data.get('nights', ''),
            '객실수': web_data.get('room_count', ''),
            '객실명': web_data.get('room_name', ''),
            '상품명': web_data.get('product_name', ''),
            '요청사유': cx_data.get('request_reason', '').replace('cx_list.xlsx_', ''),
            '요청사항': cx_data.get('request_content', '').replace('cx_list.xlsx_', '')
        }
        
        # 제목 생성
        email_subject = subject_template
        for key, value in template_data.items():
            email_subject = email_subject.replace(f'{{{key}}}', str(value))
        
        # 본문 생성
        email_body = body_template
        for key, value in template_data.items():
            email_body = email_body.replace(f'{{{key}}}', str(value))
        
        print(f"7-1-1. 메일 제목: {email_subject}")
        print(f"7-1-2. 메일 본문 길이: {len(email_body)}자")
        
        return email_subject, email_body
        
    except Exception as e:
        print(f"7-1. 메일 내용 생성 실패: {e}")
        log_error(f"메일 내용 생성 실패: {e}")
        return None, None

# ✅ 8. [메일 텍스트 파일 저장]
def save_email_file(email_subject, email_body, order_number, hotel_name):
    """메일 내용을 텍스트 파일로 저장합니다."""
    try:
        print(f"8-1. 메일 텍스트 파일 저장")
        
        # 파일명 생성
        clean_subject = clean_filename(email_subject)
        txt_filename = f"{clean_subject}_001.txt"
        txt_path = os.path.join(result_dir, txt_filename)
        
        # 중복 파일명 처리
        index = 1
        while os.path.exists(txt_path):
            txt_filename = f"{clean_subject}_{index:03}.txt"
            txt_path = os.path.join(result_dir, txt_filename)
            index += 1
        
        # 파일 내용 작성
        file_content = f"제목: {email_subject}\n\n{email_body}"
        
        # 파일 저장
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        print(f"8-1-1. 메일 텍스트 파일 저장 완료: {txt_path}")
        return txt_path
        
    except Exception as e:
        print(f"8-1. 메일 텍스트 파일 저장 실패: {e}")
        log_error(f"메일 텍스트 파일 저장 실패: {e}")
        return None

# ✅ 9. [메인 처리 함수]
def process_claim_requests():
    """클레임 요청을 처리합니다."""
    try:
        print("9-1. 클레임 요청 처리 시작...")
        
        # 엑셀 파일 읽기
        cx_data_list = read_cx_excel_data(
            config['file_paths']['cx_excel'],
            "list",
            config['excel_settings'].get('test_mode')
        )
        
        if not cx_data_list:
            print("9-1-1. 처리할 데이터가 없습니다.")
            return
        
        print(f"9-1-2. {len(cx_data_list)}개 데이터 처리 시작")
        
        # 각 데이터 처리
        for i, cx_data in enumerate(cx_data_list, 1):
            order_number = cx_data['order_number']
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n--- {i}/{len(cx_data_list)} 처리 시작: 주문번호 {order_number} ---")
            
            # 1. 주문번호로 검색
            if not search_order_by_number(order_number):
                log_result(order_number, "검색실패", "검색실패", timestamp)
                continue
            
            # 2. 웹에서 데이터 추출
            web_data = extract_reservation_data(order_number)
            if not web_data:
                log_result(order_number, "데이터추출실패", "데이터추출실패", timestamp)
                continue
            
            # 3. 엑셀 파일 생성
            excel_path = create_claim_excel(order_number, web_data.get('hotel_name', ''), web_data)
            if not excel_path:
                log_result(order_number, "엑셀생성실패", "엑셀생성실패", timestamp)
                continue
            
            # 4. 메일 내용 생성
            email_subject, email_body = create_email_content(cx_data, web_data)
            if not email_subject or not email_body:
                log_result(order_number, "메일생성실패", "메일생성실패", timestamp)
                continue
            
            # 5. 메일 텍스트 파일 저장
            txt_path = save_email_file(email_subject, email_body, order_number, web_data.get('hotel_name', ''))
            if not txt_path:
                log_result(order_number, "파일저장실패", "파일저장실패", timestamp)
                continue
            
            # 6. 성공 로그 기록
            log_result(order_number, email_subject, "성공", timestamp)
            
            print(f"--- {i}/{len(cx_data_list)} 처리 완료: 성공 ---")
        
        print("9-1-3. 모든 데이터 처리 완료!")
        
    except Exception as e:
        print(f"9-1. 처리 중 오류 발생: {e}")
        log_error(f"메인 처리 중 오류: {e}")

# ✅ 10. [메인 실행]
def main():
    global main_window, driver
    try:
        # Lock 파일 확인
        if not check_lock_file():
            print("다른 프로세스가 실행 중입니다. 종료합니다.")
            return
        
        # Lock 파일 생성
        if not create_lock_file():
            print("Lock 파일 생성 실패. 종료합니다.")
            return
        
        # 실행 시작 로그
        log_start()
        
        # Chrome 설정
        print("Chrome 설정 중...")
        options = Options()

        # 서버 환경을 위한 헤드리스 모드 설정 (최신 크롬 권장 플래그)
        options.add_argument('--headless=new')  # GUI 없이 실행
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')

        # 지역/UA 설정 및 간단 반봇 우회 플래그
        options.add_argument('--lang=ko-KR')
        options.add_argument('--accept-lang=ko-KR,ko')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36')
        try:
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
        except Exception:
            pass

        # Linux 환경에서 Chrome/ChromeDriver 경로 자동 감지 (우선순위: 사용자 홈 설치 → 시스템)
        possible_chrome_bins = [
            '/usr/bin/google-chrome',                 # 시스템 설치 우선
            '/home/allmytour/bin/google-chrome',      # 사용자 홈 래퍼/바이너리
            '/opt/google/chrome/chrome',
            '/snap/bin/chromium'
        ]
        chrome_bin = next((p for p in possible_chrome_bins if os.path.exists(p)), None)
        if chrome_bin:
            options.binary_location = chrome_bin
            print(f"Chrome binary: {chrome_bin}")
        else:
            print("경고: Chrome 실행 파일을 찾지 못했습니다. PATH 의존 실행을 시도합니다.")

        possible_drivers = [
            '/home/allmytour/bin/chromedriver',
            '/usr/local/bin/chromedriver',
            '/usr/bin/chromedriver'
        ]
        driver_path = next((p for p in possible_drivers if os.path.exists(p)), None)
        if driver_path:
            print(f"ChromeDriver: {driver_path}")
            service = Service(driver_path)
        else:
            print("경고: ChromeDriver 파일을 찾지 못했습니다. PATH 상의 chromedriver 사용을 시도합니다.")
            service = Service()  # PATH 검색에 위임

        print("독립 실행 모드: 헤드리스 모드")

        driver = webdriver.Chrome(service=service, options=options)
        print("Chrome 설정 완료!")
        
        # 헤드리스 모드에서는 창 크기 설정이 옵션에서 처리됨
        # driver.maximize_window()  # 헤드리스 모드에서는 사용 불가
        # driver.set_window_position(0, 0)  # 헤드리스 모드에서는 사용 불가
        # driver.set_window_size(1920, 1080)  # 옵션에서 이미 설정됨
        
        # WebDriverWait 설정
        wait = WebDriverWait(driver, 30)  # 30초 대기
        
        # 로그인
        try:
            print(f"로그인 페이지 접속: {config['login']['url']}")
            # 페이지 로드 타임아웃 설정 (늘림)
            try:
                driver.set_page_load_timeout(60)
            except Exception:
                pass

            # 1차 진입
            try:
                driver.get(config['login']['url'])
            except TimeoutException:
                print("페이지 로드 타임아웃 - 재시도 1회")
                try:
                    driver.get(config['login']['url'])
                except TimeoutException:
                    print("페이지 로드 타임아웃 - 현재 상태에서 진행 시도")

            # about:blank 대응 - 명시적 로그인 경로로 재시도
            if driver.current_url.strip().lower().startswith("about:blank"):
                fallback_login = config['login']['url'].rstrip('/') + '/login'
                print(f"about:blank 감지 → {fallback_login} 재진입")
                try:
                    driver.get(fallback_login)
                except TimeoutException:
                    print("fallback 경로도 타임아웃 - 요소 대기로 진행")

            # 로그인 폼 요소 대기 (존재 + 클릭 가능)
            user_id_field = wait.until(EC.element_to_be_clickable((By.NAME, "userId")))
            password_field = wait.until(EC.element_to_be_clickable((By.NAME, "userPasswd")))
            print("로그인 페이지 로드 완료")

            # 로그인 폼 입력
            user_id_field.clear()
            user_id_field.send_keys(config['login']['user_id'])
            print("사용자 ID 입력 완료")

            password_field.clear()
            password_field.send_keys(config['login']['password'])
            print("비밀번호 입력 완료")

            # 로그인 버튼 클릭 (재조회 기반 3회 재시도 → 최종 Enter)
            print("로그인 버튼 찾는 중...")
            clicked = False
            selectors = [
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//input[@type='submit' or contains(translate(@value,'login','LOGIN'),'LOGIN')]")
            ]
            for attempt in range(3):
                try:
                    # 매 시도마다 새로 locate (stale 방지)
                    btn = None
                    for by, sel in selectors:
                        elems = driver.find_elements(by, sel)
                        if elems:
                            btn = elems[0]
                            break
                    if not btn:
                        # 잠깐 대기 후 다음 루프
                        time.sleep(0.5)
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked = True
                    print(f"로그인 버튼 클릭 완료 (시도 {attempt+1})")
                    break
                except Exception:
                    time.sleep(0.5)
                    continue

            if not clicked:
                password_field.send_keys(Keys.ENTER)
                print("로그인 제출 (Enter 키)")

            # 로그인 후 전환 대기 (URL/타이틀 변화 혹은 특정 요소 대기)
            try:
                wait.until(lambda d: "login" not in d.current_url.lower())
            except TimeoutException:
                pass

            time.sleep(2)
            print(f"로그인 후 페이지 제목: {driver.title}")
            print("로그인 완료!")
            
        except Exception as e:
            print(f"로그인 실패: {e}")
            log_error(f"로그인 실패: {e}")
            return
        
        # 예약목록 페이지 이동
        orders_url = config['urls']['base_url'] + config['urls']['orders_page']
        print(f"예약목록 페이지 이동: {orders_url}")
        driver.get(orders_url)
        time.sleep(get_timing('page_load_wait', 2))
        
        # 메인창 핸들 저장
        main_window = driver.current_window_handle
        print(f"메인창 핸들 저장: {main_window}")
        
        # 클레임 요청 처리
        process_claim_requests()
        
        print("모든 작업 완료!")
        
    except Exception as e:
        print(f"메인 실행 중 오류 발생: {e}")
        # 실패 시 현재 화면 스냅샷/HTML 저장
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = os.path.join(result_dir, f"error_screenshot_{ts}.png")
            html_path = os.path.join(result_dir, f"error_page_{ts}.html")
            if 'driver' in globals():
                driver.save_screenshot(screenshot_path)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print(f"에러 스크린샷 저장: {screenshot_path}")
                print(f"에러 HTML 저장: {html_path}")
        except Exception as se:
            print(f"에러 증빙 저장 중 추가 오류: {se}")
        log_error(f"메인 실행 중 오류: {e}")
    finally:
        # Lock 파일 제거
        remove_lock_file()
        
        # 브라우저 종료
        if 'driver' in globals():
            print("브라우저를 종료합니다.")
            driver.quit()

if __name__ == "__main__":
    main()
