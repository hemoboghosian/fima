from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
import pandas as pd
import time
import warnings
import re
from bs4 import BeautifulSoup
import jdatetime as jd
from persian import convert_ar_characters


def extract_jalali_date(title):
    match = re.search(r"(\d{4})/(\d{2})/(\d{2})", title)
    if match:
        year, month, day = map(int, match.groups())
        return jd.date(year=year, month=month, day=day)
    return None


def scrape_a_page(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    data = []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) >= 7:
            symbol = cells[0].text.strip()
            company_name = cells[1].text.strip()
            status = cells[2].text.strip() if cells[2].text else "N/A"
            notice_title = cells[3].text.strip()
            code = cells[4].text.strip()
            sent_time = cells[5].text.strip()
            published_time = cells[6].text.strip()
            link = cells[3].find_element(By.TAG_NAME, "a").get_attribute("href") \
                if cells[3].find_elements(By.TAG_NAME, "a") else "N/A"
            data.append([symbol, company_name, status, notice_title, code, sent_time, published_time, link])
    return data


def scrape_monthly_activity_report(driver, table_id):
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table', {'id': table_id})
    header_levels = []
    data = []
    rows = table.find_all('tr')
    num_header_rows = 2
    max_cols = 0

    for i in range(num_header_rows):
        headers = []
        cells = rows[i].find_all(['th', 'td'])
        for cell in cells:
            header_text = cell.text.strip()
            colspan = int(cell.get('colspan', 1))
            rowspan = int(cell.get('rowspan', 1))
            for _ in range(colspan):
                headers.append(header_text)
            for j in range(1, rowspan):
                while len(header_levels) <= i + j:
                    header_levels.append([])
                header_levels[i + j].extend([header_text] * colspan)
        header_levels.append(headers)
        max_cols = max(max_cols, len(headers))

    for level in header_levels:
        level.extend([''] * (max_cols - len(level)))

    multi_index = pd.MultiIndex.from_arrays(header_levels)

    for row in rows[num_header_rows:]:
        row_data = [cell.text.strip() for cell in row.find_all('td')]
        if row_data:
            data.append(row_data[:max_cols])

    df = pd.DataFrame(data, columns=multi_index)
    df.columns = df.columns.droplevel([0, 1])
    return df


def scrape_codal(pages=10, delay=1):
    warnings.filterwarnings(action='ignore')

    options = Options()
    options.headless = True

    service = FirefoxService(executable_path=GeckoDriverManager().install())
    driver = webdriver.Firefox(service=service, options=options)

    base_url = "https://codal.ir/ReportList.aspx?PageNumber="
    all_data = pd.DataFrame(columns=['Ticker', 'Name', 'Title', 'Link'])

    try:
        for page_number in range(1, pages + 1):
            print(f"Scraping page {page_number} from codal...")
            driver.get(base_url + str(page_number))
            time.sleep(delay)

            page_data = scrape_a_page(driver)
            if not page_data:
                print("No more pages to scrape.")
                break

            df = pd.DataFrame(page_data, columns=['Ticker', 'Name', 'Status', 'Title', 'Code', 'SentTime', 'PublishedTime', 'Link'])
            df = df[['Ticker', 'Name', 'Title', 'Link']]
            df['Ticker'] = df['Ticker'].apply(convert_ar_characters)
            df['Name'] = df['Name'].apply(convert_ar_characters)
            df['Title'] = df['Title'].apply(convert_ar_characters)

            all_data = pd.concat([all_data, df], ignore_index=True)

    finally:
        driver.quit()

    return all_data


# df_codal = scrape_codal(pages=5)
