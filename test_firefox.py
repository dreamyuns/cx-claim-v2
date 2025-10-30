#!/usr/bin/env python3
"""
Firefox 헤드리스 모드 테스트 스크립트
"""

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import time

def test_firefox():
    try:
        print("Firefox 테스트 시작...")
        
        # Firefox 옵션 설정
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--width=1920')
        options.add_argument('--height=1080')
        
        print("Firefox 옵션 설정 완료")
        
        # Firefox 실행
        print("Firefox 실행 중...")
        driver = webdriver.Firefox(options=options)
        print("Firefox 실행 성공!")
        
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
    success = test_firefox()
    if success:
        print("✅ Firefox 테스트 성공!")
    else:
        print("❌ Firefox 테스트 실패!")
