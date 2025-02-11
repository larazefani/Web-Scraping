import time
import random
import csv
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (NoSuchElementException,
                                        TimeoutException,
                                        StaleElementReferenceException,
                                        WebDriverException)
from webdriver_manager.chrome import ChromeDriverManager

class SewaKostProScraper:
    def __init__(self, headless=False):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15"
        ]
        self.driver = self.setup_driver(headless)
        self.base_url = "https://www.sewakost.com/kost-jakarta/jenis:Kost+Putri/price:500000-1000000/"
        self.data = []
        self.retry_limit = 3

    def setup_driver(self, headless):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        return driver

    def random_delay(self, min=1, max=3):
        time.sleep(random.uniform(min, max))

    def accept_cookies(self):
        try:
            cookie_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Setuju")]'))
            )
            cookie_btn.click()
            self.random_delay()
        except Exception as e:
            print(f"Cookie consent error: {str(e)}")

    def safe_extract(self, parent, selector):
        try:
            if parent is None:
                return "N/A"
            element = parent.select_one(selector)
            return element.get_text(strip=True) if element else "N/A"
        except Exception:
            return "N/A"

    def scrape_page_listings(self, url):
        for attempt in range(self.retry_limit):
            try:
                print(f"🌐 Loading page: {url}")
                self.driver.get(url)
                
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.item.two-inline"))
                )
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                return soup.select("section#listings article.item.two-inline")
                
            except Exception as e:
                if attempt == self.retry_limit - 1:
                    raise e
                print(f"⚠️ Retrying page load...")
                self.random_delay(3, 5)

    def process_pagination(self):
        page = 1
        while page <= 35:  # Modified to only process pages 1-35
            try:
                print(f"🔄 Processing page {page}...")
                url = f"{self.base_url}.html" if page == 1 else f"{self.base_url}index{page}.html"
                
                listings = self.scrape_page_listings(url)
                
                if not listings:
                    print(f"📭 No listings found on page {page}, moving to next page...")
                else:
                    detail_urls = []
                    for article in listings:
                        link_element = article.select_one("li.title a")
                        if link_element and link_element.get('href'):
                            link = link_element['href']
                            full_url = link if link.startswith('http') else f"https://www.sewakost.com{link}"
                            detail_urls.append(full_url)
                    
                    print(f"🔍 Found {len(detail_urls)} listings on page {page}")
                    
                    for detail_url in detail_urls:
                        print(f"📥 Scraping detail page: {detail_url}")
                        detail_data = self.scrape_detail_page(detail_url)
                        if detail_data:
                            self.data.append(detail_data)
                        self.random_delay(1, 3)
                
                page += 1
                self.random_delay(2, 5)
            
            except Exception as e:
                print(f"🔥 Critical error while processing page {page}: {str(e)}")
                break

    def scrape_detail_page(self, url):
        for attempt in range(self.retry_limit):
            try:
                print(f"Attempt {attempt + 1} for {url}")
                self.driver.get(url)
                
                if "404" in self.driver.title or "Not Found" in self.driver.page_source:
                    print(f"Page not found: {url}")
                    return None
                
                WebDriverWait(self.driver, 20).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                data = {
                    'nama': self.get_nama_kost(soup),
                    'pemilik': self.get_pemilik(soup),
                    'telepon': self.get_phone_number(soup),
                    'harga': self.get_harga(soup),
                    'lokasi': self.get_lokasi(soup),
                    'fasilitas': self.get_fasilitas_detail(soup),
                    'deskripsi': self.get_deskripsi(soup),
                    'url': url
                }
                
                return data
                
            except (TimeoutException, NoSuchElementException, WebDriverException) as e:
                print(f"Attempt {attempt + 1} error: {str(e)}")
                if attempt == self.retry_limit - 1:
                    return None
                self.random_delay(5, 10)
                self.driver.refresh()

    def get_nama_kost(self, soup):
        try:
            return soup.select_one("h1.col-md-10").get_text(strip=True)
        except AttributeError:
            return "N/A"

    def get_pemilik(self, soup):
        try:
            return soup.select_one("div.seller-short li.name").get_text(strip=True)
        except AttributeError:
            return "N/A"

    def get_phone_number(self, soup):
        try:
            whatsapp_div = soup.find('div', {'id': 'df_field_whatsapp'})
            if whatsapp_div:
                phone = whatsapp_div.find('div', class_='value').get_text(strip=True)
                if phone and phone != "N/A":
                    return phone

            show_phone_btn = soup.find("span", text="Lihat Nomor")
            if show_phone_btn:
                return show_phone_btn.find_next("a")['href'].replace("tel:", "")

            return soup.select_one("span.call-owner")['data-phone']
        except (TypeError, AttributeError, KeyError):
            return "N/A"

    def get_harga(self, soup):
        try:
            return soup.select_one("div#df_field_price span").get_text(strip=True)
        except AttributeError:
            return "N/A"

    def get_lokasi(self, soup):
        lokasi = {
            'nama_kost': "N/A",
            'provinsi': "N/A",
            'kota': "N/A",
            'kecamatan': "N/A",
            'kelurahan': "N/A",
            'alamat': "N/A"
        }
        
        try:
            fieldset = soup.find("div", {"id": "fs_1049"})
            if fieldset:
                lokasi['nama_kost'] = fieldset.select_one("#df_field_nama_kost .value").get_text(strip=True)
                lokasi['provinsi'] = fieldset.select_one("#df_field_lokasi .value").get_text(strip=True)
                lokasi['kota'] = fieldset.select_one("#df_field_lokasi_level1 .value").get_text(strip=True)
                lokasi['kecamatan'] = fieldset.select_one("#df_field_lokasi_level2 .value").get_text(strip=True)
                lokasi['kelurahan'] = fieldset.select_one("#df_field_lokasi_level3 .value").get_text(strip=True)
                lokasi['alamat'] = fieldset.select_one("#df_field_address .value").get_text(strip=True)
        except Exception as e:
            print(f"Error extracting location: {str(e)}")
        
        return lokasi

    def get_fasilitas_detail(self, soup):
        fasilitas = {
            'kamar': [],
            'bersama': [],
            'sekitar': []
        }
        
        try:
            fieldset = soup.find("div", {"id": "fs_1050"})
            if fieldset:
                kamar_items = fieldset.select("#df_field_fasilitas_kamar li")
                fasilitas['kamar'] = [li.get_text(strip=True) for li in kamar_items]
                
                bersama_items = fieldset.select("#df_field_fasilitas_kost li")
                fasilitas['bersama'] = [li.get_text(strip=True) for li in bersama_items]
                
                sekitar_items = fieldset.select("#df_field_fasilitas_sekitar li")
                fasilitas['sekitar'] = [li.get_text(strip=True) for li in sekitar_items]
                
        except Exception as e:
            print(f"Error extracting facilities: {str(e)}")
        
        return fasilitas

    def get_deskripsi(self, soup):
        try:
            deskripsi_div = soup.find("div", {"id": "df_field_additional_information"})
            return deskripsi_div.select_one(".value").get_text(" ", strip=True)
        except AttributeError:
            return "N/A"

    def save_to_csv(self, filename='sewakost_data.csv'):
        if not self.data:
            print("No data to save")
            return
        
        flat_data = []
        for item in self.data:
            flat_item = {
                'nama': item['nama'],
                'pemilik': item['pemilik'],
                'telepon': item['telepon'],
                'harga': item['harga'],
                'deskripsi': item['deskripsi'],
                'url': item['url'],
                'lokasi_nama_kost': item['lokasi']['nama_kost'],
                'lokasi_provinsi': item['lokasi']['provinsi'],
                'lokasi_kota': item['lokasi']['kota'],
                'lokasi_kecamatan': item['lokasi']['kecamatan'],
                'lokasi_kelurahan': item['lokasi']['kelurahan'],
                'lokasi_alamat': item['lokasi']['alamat'],
                'fasilitas_kamar': ", ".join(item['fasilitas']['kamar']),
                'fasilitas_bersama': ", ".join(item['fasilitas']['bersama']),
                'fasilitas_sekitar': ", ".join(item['fasilitas']['sekitar'])
            }
            flat_data.append(flat_item)
        
        keys = flat_data[0].keys() if flat_data else []
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            if flat_data:
                writer.writerows(flat_data)
        print(f"Data saved to {filename} ({len(flat_data)} entries)")

    def run(self):
        try:
            print("Starting scraper...")
            self.driver.get(self.base_url)
            self.accept_cookies()
            self.process_pagination()
            self.save_to_csv()
        except Exception as e:
            print(f"Critical error: {str(e)}")
        finally:
            self.driver.quit()
            print("Scraper terminated")

if __name__ == "__main__":
    scraper = SewaKostProScraper(headless=False)
    scraper.run()