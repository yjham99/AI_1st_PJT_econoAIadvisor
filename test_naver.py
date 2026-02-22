import requests
from bs4 import BeautifulSoup

def get_naver_price(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 현재가
        new_total = soup.select_one(".new_totalinfo") # 명확한 컨테이너
        if not new_total:
            # 다른 패턴 (rate_info)
            rate_info = soup.find('div', {'class': 'rate_info'})
            today = rate_info.find('p', {'class': 'no_today'})
            price = today.find('span', {'class': 'blind'}).text.replace(',', '')
            
            exday = rate_info.find('p', {'class': 'no_exday'})
            # 등락률은 보통 blind 중 하나
            blinds = exday.find_all('span', {'class': 'blind'})
            # [어제보다, 2,600, 상승, 1.46, 퍼센트]
            rate = 0.0
            if len(blinds) >= 4:
                try: 
                    rate = float(blinds[3].text)
                    if "하락" in blinds[2].text: rate = -rate
                except: pass
            
            return {"price": float(price), "rate": rate}
            
        # .new_totalinfo 패턴
        price_tag = new_total.select_one(".no_today .blind")
        price = price_tag.text.replace(',', '')
        
        rate_tag = new_total.select_one(".no_exday .blind")
        # 이쪽은 전일대비만 나올 수도 있음.
        
        return {"price": float(price), "rate": 0.0} # 등락률은 일단 0
    except Exception as e:
        print(f"Error {code}: {e}")
        return None

if __name__ == "__main__":
    for c in ['005930', '000660']:
        print(get_naver_price(c))
