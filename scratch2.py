import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("Trying Google Search...")
            await page.goto("https://www.google.com/search?q=beauty+salon+in+New+York+City", wait_until="domcontentloaded", timeout=30000)
            links = await page.query_selector_all('div.g a')
            for link in links:
                href = await link.get_attribute("href")
                if href and href.startswith("http") and "google.com" not in href:
                    print(f"Found Google: {href}")
        except Exception as e:
            print(f"Google error: {e}")
            
        try:
            print("Trying Bing Search...")
            await page.goto("https://www.bing.com/search?q=beauty+salon+in+New+York+City", wait_until="domcontentloaded", timeout=30000)
            links = await page.query_selector_all('li.b_algo h2 a')
            for link in links:
                href = await link.get_attribute("href")
                if href and href.startswith("http") and "bing.com" not in href:
                    print(f"Found Bing: {href}")
        except Exception as e:
            print(f"Bing error: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
