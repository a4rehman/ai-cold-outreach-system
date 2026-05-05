import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.google.com/maps/search/beauty+salon+in+New+York+City", wait_until="domcontentloaded", timeout=45000)
        
        # consent
        consent = await page.query_selector('button[aria-label="Accept all"]')
        if consent: await consent.click()
        
        await asyncio.sleep(5)
        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1)
            
        links = await page.query_selector_all('a')
        for link in links:
            href = await link.get_attribute("href")
            label = await link.get_attribute("aria-label") or ""
            text = await link.inner_text() or ""
            if href and "http" in href:
                print(f"HREF: {href}\nLABEL: {label}\nTEXT: {text}\n---")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
