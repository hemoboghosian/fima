from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import time
from persian import convert_ar_characters
import re
import jdatetime as jd
import warnings
from bs4 import BeautifulSoup
import requests
import os


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


warnings.filterwarnings(action='ignore')

EdgeWebDriverOptions = webdriver.EdgeOptions()
EdgeWebDriver = webdriver.Edge(options=EdgeWebDriverOptions)

BaseURL = "https://codal.ir/ReportList.aspx?PageNumber="
CodalAllPagesData = pd.DataFrame(columns=['Ticker', 'Name', 'Status', 'Title', 'Code', 'SentTime', 'PublishedTime', 'Link'])
for PageNumber in range(1, 10):
    print(f"Scraping page {PageNumber} from codal...")
    EdgeWebDriver.get(BaseURL + str(PageNumber))
    time.sleep(1)
    PageData = scrape_a_page(EdgeWebDriver)
    if not PageData:
        print("No more pages to scrape.")
        break
    else:
        PageDataDF = pd.DataFrame(PageData, columns=['Ticker', 'Name', 'Status', 'Title', 'Code', 'SentTime', 'PublishedTime', 'Link'])
        PageDataDF.drop(['Status', 'Code', 'SentTime', 'PublishedTime'], axis=1, inplace=True)
        PageDataDF['Ticker'] = PageDataDF['Ticker'].apply(lambda ticker: convert_ar_characters(ticker))
        PageDataDF['Name'] = PageDataDF['Name'].apply(lambda name: convert_ar_characters(name))
        PageDataDF['Title'] = PageDataDF['Title'].apply(lambda title: convert_ar_characters(title))
        NewCodalAllPagesData = pd.concat([CodalAllPagesData, PageDataDF], axis=0)
EdgeWebDriver.quit()
del EdgeWebDriver, BaseURL, PageNumber, EdgeWebDriverOptions, PageData

CodalAllPagesData = pd.DataFrame(CodalAllPagesData, columns=['Ticker', 'Name', 'Status', 'Title',
                                                             'Code', 'SentTime', 'PublishedTime', 'Link'])
CodalAllPagesData.drop(['Status', 'Code', 'SentTime', 'PublishedTime'], axis=1, inplace=True)
CodalAllPagesData['Ticker'] = CodalAllPagesData['Ticker'].apply(lambda ticker: convert_ar_characters(ticker))
CodalAllPagesData['Name'] = CodalAllPagesData['Name'].apply(lambda name: convert_ar_characters(name))
CodalAllPagesData['Title'] = CodalAllPagesData['Title'].apply(lambda title: convert_ar_characters(title))