import asyncio
import httpx
from bs4 import BeautifulSoup
import re

async def main():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}
    try:
        print("Trying DuckDuckGo via HTTPX...")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://html.duckduckgo.com/html/?q=beauty+salon+in+New+York+City", headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all('a', class_='result__url')
            for link in links:
                print("DDG Link:", link.get('href'))
    except Exception as e:
        print(f"DDG error: {e}")
        
    try:
        print("Trying Bing via HTTPX...")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://www.bing.com/search?q=beauty+salon+in+New+York+City", headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            for h2 in soup.find_all('h2'):
                a = h2.find('a')
                if a and a.get('href') and a.get('href').startswith('http'):
                    print("Bing Link:", a.get('href'))
    except Exception as e:
        print(f"Bing error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
