#!/usr/bin/env python3
"""
Chrome 헤드리스 모드 테스트 스크립트
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

def test_chrome():
    try:
        print("ChromeDriver 테스트 시작...")
        
        # ChromeDriver 서비스 설정
        service = Service('/usr/local/bin/chromedriver')
        
        # Chrome 옵션 설정 (극도로 단순화)
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Chrome 브라우저 경로 명시적 지정
        options.binary_location = '/home/allmytour/bin/google-chrome'
        
        print("Chrome 옵션 설정 완료")
        
        # ChromeDriver 실행
        print("ChromeDriver 실행 중...")
        driver = webdriver.Chrome(service=service, options=options)
        print("ChromeDriver 실행 성공!")
        
        # 간단한 테스트
        print("테스트 페이지 접속 중...")
        driver.get("https://www.google.com")
        print(f"페이지 제목: {driver.title}")
        
        # 3초 대기
        time.sleep(3)
        
        # 브라우저 종료
        print("브라우저 종료 중...")
        driver.quit()
        print("테스트 완료!")
        
        return True
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success = test_chrome()
    if success:
        print("✅ Chrome 테스트 성공!")
    else:
        print("❌ Chrome 테스트 실패!")
