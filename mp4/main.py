from flask import Flask, render_template, jsonify, request, Response, make_response
import pandas as pd
import time
from functools import wraps
from edgar_utils import get_top_ten_ips, get_sic_code_distribution, get_common_addresses, make_plot, Filing
import matplotlib
matplotlib.use('Agg') 
import geopandas as gpd
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import geopandas as gpd
from shapely.geometry import Point
from zipfile import ZipFile
from bs4 import BeautifulSoup

app = Flask(__name__)
a_clicks = 0
b_clicks = 0
visits = 0
visit_times = {}
visitors = set()

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time.time()
        
        if client_ip in visit_times:
            last_visited = visit_times[client_ip]
            if current_time - last_visited < 60:
                response = make_response(jsonify({"error": "Rate limit exceeded"}), 429)
                response.headers["Retry-After"] = 60 - (current_time - last_visited)
                return response
        
        visit_times[client_ip] = current_time
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    global visits, a_clicks, b_clicks
    version = 'A' if visits % 2 == 0 else 'B'
    visits += 1
    if visits <= 10:
        template_version = f"index_{version}.html"
    else:
        template_version = "index_A.html" if a_clicks > b_clicks else "index_B.html"
    return render_template(template_version)

@app.route('/browse.html')
def browse():
    df = pd.read_csv("./server_log.zip", compression = "zip")
    
    with open("templates/browse.html") as f:
        html = f.read()
        
    return html.format(df.head(500).to_html())

@app.route('/donate.html')
def donate():
    global a_clicks, b_clicks
    version = request.args.get('from')
    if version == 'A':
        a_clicks += 1
    elif version == 'B':
        b_clicks += 1
    return render_template('donate.html')

@app.route('/analysis.html')
def analysis():
    with open("analysis.html") as f:
        html = f.read()
    df = pd.read_csv("./server_log.zip", compression = "zip")
    top_ips = dict(df.groupby(["ip"]).size().sort_index(ascending = False).sort_values(ascending = False, kind = "stable").iloc[0:10])
    
    filings = {}
    
    with ZipFile("docs.zip") as zf:
        for filename in zf.namelist():
            if (filename.endswith(".htm") or filename.endswith(".html")):
                with zf.open(filename, "r") as f:
                    filing_html = str(f.read(), encoding = "utf8")
                    filings[filename] = Filing(filing_html)
    sic_series = pd.Series([int(filing.sic) for filing in list(filings.values()) if filing.sic])
    
    top_sics = dict(sic_series.groupby(sic_series).size().sort_index(ascending = False).sort_values(ascending = False, kind = "stable").iloc[0:10])
    
    list_file = list(df.apply(lambda x: str(int(x["cik"])) + "/" + x["accession"] + "/" + x["extention"], axis = 1))
    
    addresses = []
    for filename in list_file:
        if filename in filings:
            addresses.extend(filings[filename].addresses)
    
    address_series = pd.Series(addresses)
    
    top_addresses = address_series.groupby(address_series).size().sort_index(ascending = False).sort_values(ascending = False, kind = "stable")
    top_addresses = dict(top_addresses[top_addresses >= 300])
                   
    return html.format(top_ips, top_sics, top_addresses)

@app.route('/browse.json')
@rate_limit
def browse_json():
    df = pd.read_csv("./server_log.zip", compression = "zip")
    visitors.add(request.remote_addr)
    return jsonify(df.head(500).to_dict())
def visitors_json():
    return jsonify(list(visitors))

@app.route('/visitors.json')
def visitors_json():
    return jsonify(list(visitors))

@app.route('/dashboard.svg')
def svg():
    return Response(make_plot(), headers={"Content-Type": "image/svg+xml"})



if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, threaded=False)
