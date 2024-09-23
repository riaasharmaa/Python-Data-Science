import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import zipfile
from bs4 import BeautifulSoup
import re
from collections import Counter
import netaddr
from bisect import bisect_left
import difflib
from io import BytesIO
import geopandas as gpd
from shapely.geometry import box
matplotlib.use('Agg')

def anonymize_ip(ip):
    return re.sub(r'[a-zA-Z]', '0', ip)

def ip_to_int(ip):
    return int(netaddr.IPAddress(ip))

ips_df = pd. read_csv('ip2location.csv')
ips_df['start_int'] = ips_df['low'].apply(ip_to_int)
ips_df['end_int'] = ips_df['high'].apply(ip_to_int)

def parse_filing_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    sic_text = soup.find(text=re.compile('Standard Industrial Classification', re.I))  
    if sic_text:
        sic_code = sic_text.find_next().text
        return sic_code
    else:
        return None

def get_top_ips(df, n=10):
    top_ips = df['ip'].value_counts().head(n).to_dict()
    return top_ips

def analyze_sic_codes(df):
    sic_counts = df['sic'].value_counts().to_dict()
    return sic_counts

def common_addresses(filing_objects, threshold=300):
    address_counts = Counter(filing_objects)
    common_addresses = {address: count for address, count in address_counts.items() if count >= threshold}
    return common_addresses

def extract_addresses(html_content):
    return re.findall(r'\d{1,5} \w+ (Street|Avenue|Boulevard|Drive)\, \w+, \w+', html_content)

def get_top_ten_ips(log_df):
    top_ips = log_df['ip'].value_counts().nlargest(10).to_dict()
    return top_ips

def get_sic_code_distribution(docs_zip):
    sic_counts = Counter()
    with zipfile.ZipFile(docs_zip) as z:
        for filename in z.namelist():
            if filename.endswith('.htm') or filename.endswith('.html'):
                with z.open(filename) as f:
                    sic_code = parse_filing_html(f.read().decode('utf-8'))
                    sic_counts[sic_code] += 1
    return dict(sic_counts)

def get_common_addresses(log_df, docs_zip_path):
    address_counter = Counter()
    unique_requests = set(log_df['request'])

    with zipfile.ZipFile(docs_zip_path) as docs_zip:
        for filename in docs_zip.namelist():
            standardized_filename = filename.replace('-', '')
            if standardized_filename in unique_requests:
                with docs_zip.open(filename) as file:
                    html_content = file.read().decode('utf-8')
                    filing = Filing(html_content)
                    address_counter.update(filing.addresses)
    common_addresses = {address: count for address, count in address_counter.items() if count >= 300}
    return common_addresses


def lookup_region(ip, ips_df=ips_df):
    ip = anonymize_ip(ip)
    ip_int = ip_to_int(ip)
    idx = bisect_left(ips_df['start_int'], ip_int) - 1
    if idx >= 0 and ips_df.iloc[idx]['start_int'] <= ip_int <= ips_df.iloc[idx]['end_int']:
        return ips_df.iloc[idx]['region']
    else:
        return None

class Filing:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.dates = self.find_dates()
        self.sic = self.find_sic()
        self.find_addresses(html_content)

    def find_dates(self):
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        return re.findall(date_pattern, str(self.soup))

    def find_sic(self):
        sic_pattern = r'SIC=(\d+)'
        match = re.search(sic_pattern, str(self.soup))
        return int(match.group(1)) if match else None

    def find_addresses(self, html_content):
        self.addresses = []
        for addr_html in re.findall(r'<div class="mailer">([\s\S]+?)</div>', html_content):
            lines = []
            for line in re.findall(r'<span class="mailerAddress">([\s\S]+?)</span>', addr_html):
                lines.append(line.strip())
            if len(lines) > 0:
                self.addresses.append("\n".join(lines))


    def state(self):
        state_pattern = r'\b[A-Z]{2}\b \d{5}'
        match = re.search(state_pattern, str(self.soup))
        return match.group().split()[0] if match else None


def address_zip(address):
    match = re.findall(r'(\d{5})(-?(\d{4}|\d{0}))$', address)
    if len(match) != 0:
        return int(match[0][0])
    else:
        return None

def make_plot():
    us_map = gpd.read_file("shapes/cb_2018_us_state_20m.shp")
    addresses = gpd.read_file("locations.geojson")
    bounding_box = box(-95, 25, -60, 50)
    addresses["zip"] = addresses["address"].apply(address_zip)

    addresses = addresses.dropna()
    addresses = addresses[addresses["zip"] >= 25000]
    addresses = addresses[addresses["zip"] <= 65000]

    fig, ax = plt.subplots()
    us_map.intersection(bounding_box).to_crs("epsg:2022").plot(ax = ax, color = "lightgrey")

    addresses.merge(addresses.intersection(bounding_box).rename("geometry")).to_crs("epsg:2022").plot(ax = ax, column = "zip", legend = "zip", cmap = "RdBu")

    ax.set_axis_off()
    fake_file = BytesIO()
    ax.get_figure().savefig(fake_file, format = "svg", bbox_inches = "tight")
    ax.get_figure().savefig('dashboard.svg')
    plt.close(fig)
    return fake_file.getvalue()
