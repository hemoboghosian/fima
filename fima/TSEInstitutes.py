import pandas as pd
import requests


def _get_institute_types():
    params = {"offset": 1, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/instituteTypes"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    institute_types = pd.DataFrame(response.json())
    return institute_types


def _get_institute_kinds():
    params = {"offset": 1, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/instituteTypes/0/instituteKinds"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    institute_kinds = pd.DataFrame(response.json())
    return institute_kinds


def _get_cities():
    params = {"offset": 1, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/cities"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    cities = pd.DataFrame(response.json())
    return cities


def _get_provinces():
    params = {"offset": 1, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/provinces"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    provinces = pd.DataFrame(response.json())
    return provinces


def _get_license_statuses():
    params = {"offset": 0, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/licenseStatuses"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    license_status = pd.DataFrame(response.json())
    return license_status


def _get_activity_types():
    params = {"offset": 0, "limit": 10, "lng": "fa"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    url = "https://cfi.rbcapi.ir/activityTypes"
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    activity_types = pd.DataFrame(response.json())
    return activity_types


def get_all_institutions():
    url = "https://cfi.rbcapi.ir/institutes"
    params = {"offset": 0, "limit": 10000, "lng": "fa", "name": "", "city": "", "province": "", "instituteType": "",
              "instituteKind": "", "activityType": "", "licenseType": "", "status": ""}

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
               "Accept": "application/json, text/plain, */*"}
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    institutions = pd.DataFrame(response.json().get("data", []))
    institutions.drop(columns=['InstituteTypeId', 'InstituteKindId', 'StateId', 'Id', 'InquiryStatus'], inplace=True)
    return institutions
