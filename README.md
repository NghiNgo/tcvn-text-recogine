# Installation and Deployment Guide

This guide will walk you through the process of setting up and deploying the project using Python's virtual environment (venv) and Gunicorn.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation

1. Create a `requirements.txt` file in the project root with the following content:
  ```
  blinker==1.8.2
  click==8.1.7
  et-xmlfile==1.1.0
  Flask==3.0.3
  gunicorn==23.0.0
  importlib_metadata==8.2.0
  itsdangerous==2.2.0
  Jinja2==3.1.4
  MarkupSafe==2.1.5
  numpy==1.24.4
  openpyxl==3.1.5
  packaging==24.1
  pandas==2.0.3
  PyPDF2==3.0.1
  python-dateutil==2.9.0.post0
  pytz==2024.1
  six==1.16.0
  typing_extensions==4.12.2
  tzdata==2024.1
  Werkzeug==3.0.3
  zipp==3.20.0
  ```

2. Create a `app.py` file in the project root with the following content:
```
import io
from flask import Flask, request, jsonify, render_template
from PyPDF2 import PdfReader
import re
import pandas as pd
import numpy as np
import json
import concurrent.futures
import multiprocessing

app = Flask(__name__)

def extract_page_text(page):
    return page.extract_text()

def extract_text_from_pdf(pdf_file):
    pdf_bytes = pdf_file.read()
    
    reader = PdfReader(io.BytesIO(pdf_bytes))
    
    with multiprocessing.Pool() as pool:
        texts = pool.map(extract_page_text, reader.pages)
    
    return "\n\n".join(texts)

def process_pdf(pdf_file):
    text = extract_text_from_pdf(pdf_file)
    results = []
    patterns = [
        r"TCVN\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"QCVN(?:\s+[A-Za-z0-9Đ-]+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*[A-Z]+)?)?",
        r"TCXD\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"TCXDVN\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"TCN\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"ACI\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"ASTM\s*[A-Z]?\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"BHT\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"IEC\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"IEEE\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"TCCS\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"NFPA\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"TC\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"ITU(?:-[TR])?\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?"
    ]

    # Load the Excel file
    df = pd.read_excel('TCKT.xlsx')
    
    # Use the first and last three columns
    first_col = df.columns[1]
    last_cols = df.columns[-3:]
    
    if isinstance(df, pd.DataFrame):
        check_phrases = df[first_col].str.strip().tolist()
    else:
        check_phrases = [str(item).strip() for item in df]

    results_dict = {
        f'col_{i}': dict(zip(df[first_col].str.strip(), df[col]))
        for i, col in enumerate(last_cols, start=-3)
    }

    def handle_nan(value):
        if pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
            return None
        return value

    def process_page(page_data):
        page_num, page_text = page_data
        page_results = []
        standards = ["TCVN", "QCVN", "TCXD", "TCXDVN", "TCN", "ACI", "ASTM", "BHT", "IEC", "IEEE", "TCCS", "NFPA", "TC", "ITU"]
        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phrase = re.sub(r'\s+', '', match.group().strip())
                
                line_num = page_text[:match.start()].count('\n') + 1
                base_text = next((standard for standard in standards if phrase.startswith(standard)), "")
                
                after_text = ""
                if base_text:
                    index = page_text.find(base_text, match.start())
                    if index != -1:
                        after_text = page_text[index+len(base_text):index+len(base_text)+50].strip()
                        for standard in standards:
                            if standard in after_text:
                                after_text = re.sub(r'\s+', ' ', after_text[:after_text.index(standard) + len(standard)])
                                break
                        else:
                            after_text = re.sub(r'\s+', ' ', after_text[:24])

                updated_phrase = f"{base_text} {after_text}".strip() if base_text else ""
                
                updated_phrase_normalized = re.sub(r'\s+', '', updated_phrase).strip()
                matching_check_phrase = next((cp for cp in check_phrases if re.sub(r'\s+', '', cp).strip() in updated_phrase_normalized), None)
                matching_results = [
                    handle_nan(results_dict[f'col_{i}'].get(matching_check_phrase))
                    for i in range(-3, 0)
                ] if matching_check_phrase else [None] * 3

                first_col_value = df[first_col].loc[df[first_col].str.strip() == matching_check_phrase].values[0] if matching_check_phrase else None

                if first_col_value is None and "TCVN" in phrase:
                    custom_phrase = phrase.replace("-", ":")
                    if custom_phrase.startswith("TCVN"):
                        base_text = "TCVN"
                        after_text = custom_phrase[4:].strip()
                        index = page_text.find(custom_phrase, match.start())
                        if index != -1:
                            after_text = page_text[index+4:index+54].strip()
                            for standard in standards:
                                if standard in after_text:
                                    after_text = re.sub(r'\s+', ' ', after_text[:after_text.index(standard) + len(standard)])
                                    break
                            else:
                                after_text = re.sub(r'\s+', ' ', after_text[:24])

                    updated_phrase_normalized = re.sub(r'\s+', '', custom_phrase).strip()
                    matching_check_phrase = next((cp for cp in check_phrases if re.sub(r'\s+', '', cp).strip() in updated_phrase_normalized), None)
                    matching_results = [
                        handle_nan(results_dict[f'col_{i}'].get(matching_check_phrase))
                        for i in range(-3, 0)
                    ] if matching_check_phrase else [None] * 3

                    first_col_value = df[first_col].loc[df[first_col].str.strip() == matching_check_phrase].values[0] if matching_check_phrase else None

                page_results.append({
                    "phrase": updated_phrase,
                    "page": page_num,
                    "line": line_num,
                    "base_text": base_text,
                    "after_text": after_text,
                    "updated_phrase": updated_phrase,
                    "matching_check_phrase": matching_check_phrase,
                    "first_col_value": first_col_value,
                    "matching_result_3": matching_results[0],
                    "matching_result_2": matching_results[1],
                    "matching_result_1": matching_results[2],
                    "standard_type": base_text if base_text else "Unknown",
                    "numeric_part": re.search(r'\d+', phrase).group() if re.search(r'\d+', phrase) else "",
                    "full_reference": f"{base_text} {after_text}".strip()
                })
                
        return page_results

    pages = list(enumerate(text.split('\n\n'), 1))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_page, pages))
    
    return [item for sublist in results for item in sublist]


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith('.pdf'):
        results = process_pdf(file)
        return json.dumps(results, ensure_ascii=False, default=str)
    else:
        return jsonify({"error": "Invalid file type"}), 400

if __name__ == '__main__':
    app.run(debug=True)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)
```

3. Create new folder `templates`
   
4. Create file `index.html` inside templates folder
```
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KIỂM TRA HSDA - Version 1.1</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300..800;1,300..800&display=swap"
      rel="stylesheet"
    />
    <link
      rel="icon"
      href="{{ url_for('static', filename='evn.png') }}"
      type="image/png"
    />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.17.0/xlsx.full.min.js"></script>
    <style>
      body {
        font-family: "Open Sans", sans-serif;
        max-width: 1000px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f0f4f8;
        color: #333;
      }
      h1 {
        color: #2c3e50;
        text-align: center;
        margin-bottom: 30px;
        font-weight: 700;
      }
      #upload-form {
        background-color: #fff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
      }
      input[type="file"] {
        display: block;
        width: 100%;
        padding: 10px;
        margin-bottom: 15px;
        border: 2px solid #ddd;
        border-radius: 4px;
        transition: border-color 0.3s;
      }
      input[type="file"]:hover {
        border-color: #3498db;
      }
      button {
        background-color: #3498db;
        color: white;
        padding: 12px 20px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        font-weight: 700;
      }
      button:hover {
        background-color: #2980b9;
      }
      #results {
        background-color: #fff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      }
      #results h2 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-weight: 700;
      }
      .result-item {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
      }
      .result-item:hover {
        transform: translateY(-2px);
      }
      .result-item strong {
        color: #2c3e50;
        font-weight: 700;
      }
      .pagination {
        display: flex;
        justify-content: center;
        margin-top: 20px;
      }
      .pagination button {
        margin: 0 5px;
        padding: 8px 12px;
        background-color: #ecf0f1;
        color: #2c3e50;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
      }
      .pagination button:hover {
        background-color: #bdc3c7;
      }
      .pagination button.active {
        background-color: #3498db;
        color: white;
      }
      .spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #3498db;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
      }

      @keyframes spin {
        0% {
          transform: rotate(0deg);
        }
        100% {
          transform: rotate(360deg);
        }
      }

      #search-container {
        background-color: #fff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
      }

      #search-input,
      #standard-type-select {
        flex-grow: 1;
        padding: 10px;
        border: 2px solid #ddd;
        border-radius: 4px;
        transition: border-color 0.3s;
        font-family: "Open Sans", sans-serif;
      }

      #search-input:focus,
      #standard-type-select:focus {
        outline: none;
        border-color: #3498db;
      }

      #search-container button {
        flex-shrink: 0;
      }

      .file-input-wrapper {
        position: relative;
        display: inline-block;
        cursor: pointer;
        margin-right: 10px;
      }

      .file-input-wrapper input[type="file"] {
        position: absolute;
        left: 0;
        top: 0;
        opacity: 0;
        cursor: pointer;
        width: 100%;
        height: 100%;
      }

      .file-input-wrapper label {
        display: inline-block;
        padding: 10px 20px;
        background-color: #f0f0f0;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 16px;
        transition: all 0.3s ease;
      }

      .file-input-wrapper:hover label {
        background-color: #e0e0e0;
      }

      .file-input-wrapper input[type="file"]:focus + label {
        outline: 2px solid #007bff;
      }

      /* Optional: Style for showing selected file name */
      .file-input-wrapper::after {
        content: attr(data-text);
        font-size: 14px;
        color: #555;
        margin-left: 10px;
      }

      #changelog {
        background-color: #fff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-top: 30px;
      }

      #changelog h2 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 20px;
      }

      #changelog-list {
        list-style-type: none;
        padding-left: 0;
      }

      #changelog-list li {
        margin-bottom: 15px;
      }

      #changelog-list ul {
        margin-top: 5px;
      }

      .result-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 20px;
      }

      @media (min-width: 768px) {
        .result-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }

      .result-item {
        break-inside: avoid;
        page-break-inside: avoid;
      }

      .modal {
        display: none;
        position: fixed;
        z-index: 1;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0, 0, 0, 0.4);
      }

      .modal-content {
        background-color: #fefefe;
        margin: 15% auto;
        padding: 20px;
        border: 1px solid #888;
        width: 80%;
        max-width: 600px;
        border-radius: 8px;
      }

      .close {
        color: #aaa;
        float: right;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
      }

      .close:hover,
      .close:focus {
        color: #000;
        text-decoration: none;
        cursor: pointer;
      }

      .button-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 15px;
      }

      .left-buttons {
        display: flex;
        gap: 10px;
      }

      #open-changelog {
        display: block;
        margin: 20px auto;
        padding: 10px 20px;
        background-color: #7f8c8d;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        margin-left: auto;
      }

      #open-changelog:hover {
        background-color: #95a5a6;
      }

      .button {
        display: inline-block;
        padding: 12px 20px;
        background-color: #2ecc71;
        color: white;
        text-decoration: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        font-weight: 700;
        font-size: 16px; /* Add this line */
      }

      button {
        background-color: #3498db;
        color: white;
        padding: 12px 20px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        font-weight: 700;
        font-size: 16px; /* Add this line */
      }

      .button:hover {
        background-color: #27ae60;
      }

      #statistics-container {
        background-color: #fff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
      }

      #statistics-container h2 {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-weight: 700;
      }

      .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 20px;
      }

      .stat-item {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        cursor: pointer;
        transition: background-color 0.3s, transform 0.2s, box-shadow 0.2s;
      }

      .stat-item:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        background-color: #e8f4fd;
      }

      .stat-item h3 {
        color: #2c3e50;
        margin-bottom: 10px;
        font-weight: 600;
        font-size: 1rem;
      }

      .stat-count {
        font-size: 1.5rem;
        font-weight: 700;
        color: #3498db;
      }

      .stat-item.total {
        background-color: #3498db;
        color: white;
      }

      .stat-item.total h3 {
        color: white;
      }

      .stat-item.total .stat-count {
        color: white;
      }

      @media (max-width: 768px) {
        .stats-grid {
          grid-template-columns: repeat(2, 1fr);
        }
      }

      @media (max-width: 480px) {
        .stats-grid {
          grid-template-columns: 1fr;
        }
      }

      .modal-title {
        color: #2c3e50;
        border-bottom: 2px solid #3498db;
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-weight: 700;
      }

      .logo-container {
        text-align: center;
        margin-bottom: 20px;
      }

      .logo {
        max-width: 200px;
        height: auto;
      }

      .stat-item.active {
        background-color: #3498db;
        color: white;
        transform: translateY(-5px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
      }

      .stat-item.active h3,
      .stat-item.active .stat-count {
        color: white;
      }
    </style>
  </head>
  <body>
    <div class="logo-container">
      <img
        src="{{ url_for('static', filename='pecc4.png') }}"
        alt="Logo 1"
        class="logo"
      />
    </div>
    <h1>KIỂM TRA HSDA - IT P8</h1>
    <form id="upload-form">
      <div class="file-input-wrapper">
        <input type="file" id="pdf-file" accept=".pdf" required />
        <label for="pdf-file">Chọn file</label>
      </div>
      <div class="button-row">
        <div class="left-buttons">
          <button type="submit">Tải lên và xử lý</button>
          <a id="download-xlsx" href="#" class="button" style="display: none">
            Tải xuống XLSX
          </a>
        </div>
        <div>
          <a id="open-changelog" href="#" class="button"
            >Xem nhật ký thay đổi</a
          >
        </div>
      </div>
    </form>
    <div id="statistics-container" style="display: none">
      <h2>Thống kê</h2>
      <div class="stats-grid">
        <div class="stat-item" onclick="filterByType('all')">
          <h3>Tổng cộng</h3>
          <span id="total-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TCVN')">
          <h3>TCVN</h3>
          <span id="tcvn-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('QCVN')">
          <h3>QCVN</h3>
          <span id="qcvn-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TCXD')">
          <h3>TCXD</h3>
          <span id="tcxd-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TCXDVN')">
          <h3>TCXDVN</h3>
          <span id="tcxdvn-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TCN')">
          <h3>TCN</h3>
          <span id="tcn-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('ACI')">
          <h3>ACI</h3>
          <span id="aci-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('ASTM')">
          <h3>ASTM</h3>
          <span id="astm-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('BHT')">
          <h3>BHT</h3>
          <span id="bht-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('IEC')">
          <h3>IEC</h3>
          <span id="iec-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('IEEE')">
          <h3>IEEE</h3>
          <span id="ieee-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TCCS')">
          <h3>TCCS</h3>
          <span id="tccs-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('NFPA')">
          <h3>NFPA</h3>
          <span id="nfpa-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TC')">
          <h3>TC</h3>
          <span id="tc-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('ITU')">
          <h3>ITU</h3>
          <span id="itu-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('Unknown')">
          <h3>Không tìm thấy</h3>
          <span id="unknown-count" class="stat-count">0</span>
        </div>
      </div>
    </div>
    <div id="search-container" style="display: none">
      <input
        type="text"
        id="search-input"
        placeholder="Nhập từ khóa..."
        style="display: none"
      />
      <!-- <button onclick="applyFilters()">Tìm kiếm</button> -->
      <select id="standard-type-select" onchange="applyFilters()" style="display: none;">
        <option value="all">Tất cả</option>
        <option value="TCVN">TCVN</option>
        <option value="QCVN">QCVN</option>
        <option value="TCXD">TCXD</option>
        <option value="TCXDVN">TCXDVN</option>
        <option value="TCN">TCN</option>
        <option value="ACI">ACI</option>
        <option value="ASTM">ASTM</option>
        <option value="BHT">BHT</option>
        <option value="IEC">IEC</option>
        <option value="IEEE">IEEE</option>
        <option value="TCCS">TCCS</option>
        <option value="NFPA">NFPA</option>
        <option value="TC">TC</option>
        <option value="ITU">ITU</option>
        <option value="Unknown">Không tìm thấy</option>
      </select>
    </div>
    <div
      id="loading"
      style="display: none; text-align: center; margin-top: 20px"
    >
      <p>Đang xử lý... Từ từ khoai nó mới nhừ...</p>
      <div class="spinner"></div>
    </div>
    <div id="results"></div>
    <div id="changelog-modal" class="modal">
      <div class="modal-content">
        <span class="close">&times;</span>
        <h2 class="modal-title">Nhật ký thay đổi</h2>
        <ul id="changelog-list"></ul>
      </div>
    </div>
    <script>
      let allResults = [];
      let filteredResults = [];
      const itemsPerPage = 10;
      let currentPage = 1;

      document
        .getElementById("pdf-file")
        .addEventListener("change", function (e) {
          var fileName = e.target.files[0]
            ? e.target.files[0].name
            : "No file selected";
          this.parentNode.setAttribute("data-text", fileName);
        });

      document
        .getElementById("upload-form")
        .addEventListener("submit", function (e) {
          e.preventDefault();
          var formData = new FormData();
          var fileInput = document.getElementById("pdf-file");
          formData.append("file", fileInput.files[0]);

          document.getElementById("loading").style.display = "block";
          document.getElementById("results").innerHTML = "";
          // document.getElementById("search-container").style.display = "none";

          fetch("/upload", {
            method: "POST",
            body: formData,
          })
            .then((response) => {
              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
              }
              return response.json();
            })
            .then((data) => {
              allResults = data;
              filteredResults = allResults;
              const stats = calculateStatistics(allResults);
              document.getElementById("total-count").textContent = Object.values(stats).reduce((a, b) => a + b, 0);
              document.getElementById("tcvn-count").textContent = stats.TCVN;
              document.getElementById("qcvn-count").textContent = stats.QCVN;
              document.getElementById("tcxd-count").textContent = stats.TCXD;
              document.getElementById("tcxdvn-count").textContent =
                stats.TCXDVN;
              document.getElementById("tcn-count").textContent = stats.TCN;
              document.getElementById("aci-count").textContent = stats.ACI;
              document.getElementById("astm-count").textContent = stats.ASTM;
              document.getElementById("bht-count").textContent = stats.BHT;
              document.getElementById("iec-count").textContent = stats.IEC;
              document.getElementById("ieee-count").textContent = stats.IEEE;
              document.getElementById("tccs-count").textContent = stats.TCCS;
              document.getElementById("nfpa-count").textContent = stats.NFPA;
              document.getElementById("tc-count").textContent = stats.TC;
              document.getElementById("itu-count").textContent = stats.ITU;
              document.getElementById("unknown-count").textContent =
                stats.Unknown;
              displayResults(1);
              // document.getElementById("search-container").style.display =
              //   "flex";
              document.getElementById("statistics-container").style.display =
                "block";
              document.getElementById("download-xlsx").style.display =
                "inline-block";
            })
            .catch((error) => {
              console.error("Error:", error);
              document.getElementById("results").innerHTML =
                "<p>An error occurred while processing the file: " +
                error.message +
                "</p>";
            })
            .finally(() => {
              document.getElementById("loading").style.display = "none";
            });
        });
        
      function filterByType(type) {
        document.querySelectorAll('.stat-item').forEach(item => {
          item.classList.remove('active');
        });

        const clickedItem = document.querySelector(`.stat-item[onclick="filterByType('${type}')"]`);
        if (clickedItem) {
          clickedItem.classList.add('active');
        }

        document.getElementById('standard-type-select').value = type;
        applyFilters();
      }


      function displayResults(page) {
        currentPage = page;
        const startIndex = (page - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const pageResults = filteredResults.slice(startIndex, endIndex);

        var resultsDiv = document.getElementById("results");
        if (pageResults.length > 0) {
          var html = `<h2>Kết quả tìm được: (${filteredResults.length})</h2>`;

          // Group results by standard_type
          const groupedResults = groupByStandardType(pageResults);

          for (const [standardType, items] of Object.entries(groupedResults)) {
            html += `<h3>${standardType}</h3>`;
            html += '<div class="result-grid">';
            items.forEach((item) => {
              html += `
              <div class="result-item">
                <strong>Tìm theo:</strong> ${item.phrase}<br>
                <strong>Trang:</strong> ${item.page}, <strong>Dòng:</strong> ${
                item.line
              }<br>
                ${
                  item.matching_check_phrase
                    ? `<strong>Mã số:</strong> ${item.first_col_value}<br>`
                    : `<strong>Mã số:</strong> <span style="color: brown;">Không tìm thấy</span><br>`
                }
                ${
                  item.matching_result_3
                    ? `<strong>Tình trạng:</strong> ${item.matching_result_3}<br>`
                    : `<strong>Tình trạng:</strong> <span style="color: brown;">Không tìm thấy</span><br>`
                }
                ${
                  item.matching_result_2
                    ? `<strong>Văn bản thay thế:</strong> <span style="color: red;">${item.matching_result_2}</span><br>`
                    : ""
                }
              </div>`;
            });
            html += "</div>";
          }

          html += generatePagination();
          resultsDiv.innerHTML = html;
        } else if (filteredResults.error) {
          resultsDiv.innerHTML = "<p>Error: " + filteredResults.error + "</p>";
        } else {
          resultsDiv.innerHTML = "<p>Không tìm thấy nội dung phù hợp</p>";
        }
      }

      function downloadXLSX() {
        const exportData = filteredResults.map((item) => ({
          "Tìm theo": item.phrase,
          Trang: item.page,
          Dòng: item.line,
          "Mã số": item.matching_check_phrase || "Không tìm thấy",
          "Tình trạng": item.matching_result_3 || "Không tìm thấy",
          "Văn bản thay thế": item.matching_result_2 || "",
        }));

        const worksheet = XLSX.utils.json_to_sheet(exportData);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Results");
        XLSX.writeFile(workbook, "results.xlsx");
      }

      document
        .getElementById("download-xlsx")
        .addEventListener("click", function (e) {
          e.preventDefault();
          downloadXLSX();
        });

      function groupByStandardType(results) {
        return results.reduce((acc, item) => {
          (acc[item.standard_type] = acc[item.standard_type] || []).push(item);
          return acc;
        }, {});
      }

      const changeLog = [
        {
          version: "1.2",
          date: "2024-09-24",
          changes: [
            "Thêm các quy chuẩn mới: TCXD, TCXDVN, TCN, ACI, ASTM, BHT, IEC, IEEE, TCCS, NFPA, TC, ITU",
          ],
        },
        {
          version: "1.1",
          date: "2024-09-19",
          changes: [
            "Cải thiện hiệu suất tìm kiếm",
            "Thêm chức năng tải xuống file XLSX",
          ],
        },
        {
          version: "1.0",
          date: "2024-08-14",
          changes: [
            "Phát hành ban đầu",
            "Chức năng xử lý PDF cơ bản",
            "Khả năng tìm kiếm và lọc",
          ],
        }
      ];

      function displayChangeLog() {
        const changelogList = document.getElementById("changelog-list");
        changelogList.innerHTML = "";

        changeLog.forEach((version) => {
          const li = document.createElement("li");
          li.innerHTML = `
            <strong>Version ${version.version}</strong> (${version.date})
            <ul>
              ${version.changes.map((change) => `<li>${change}</li>`).join("")}
            </ul>
          `;
          changelogList.appendChild(li);
        });
      }

      const modal = document.getElementById("changelog-modal");
      document
        .getElementById("open-changelog")
        .addEventListener("click", function (e) {
          e.preventDefault();
          modal.style.display = "block";
          displayChangeLog();
        });
      const span = document.getElementsByClassName("close")[0];

      span.onclick = function () {
        modal.style.display = "none";
      };

      window.onclick = function (event) {
        if (event.target == modal) {
          modal.style.display = "none";
        }
      };

      function generatePagination() {
        const totalPages = Math.ceil(filteredResults.length / itemsPerPage);
        let paginationHtml = '<div class="pagination">';

        for (let i = 1; i <= totalPages; i++) {
          paginationHtml += `<button onclick="displayResults(${i})" ${
            i === currentPage ? 'class="active"' : ""
          }>${i}</button>`;
        }

        paginationHtml += "</div>";
        return paginationHtml;
      }

      function applyFilters() {
        const searchTerm = document
          .getElementById("search-input")
          .value.toLowerCase();
        const selectedType = document.getElementById(
          "standard-type-select"
        ).value;

        filteredResults = allResults.filter((item) => {
          const matchesSearch =
            item.phrase.toLowerCase().includes(searchTerm) ||
            item.base_text.toLowerCase().includes(searchTerm) ||
            (item.after_text &&
              item.after_text.toLowerCase().includes(searchTerm)) ||
            (item.updated_phrase &&
              item.updated_phrase.toLowerCase().includes(searchTerm)) ||
            (item.matching_check_phrase &&
              item.matching_check_phrase.toLowerCase().includes(searchTerm)) ||
            (item.matching_result_3 &&
              item.matching_result_3.toLowerCase().includes(searchTerm)) ||
            (item.matching_result_2 &&
              item.matching_result_2.toLowerCase().includes(searchTerm)) ||
            (item.matching_result_1 &&
              item.matching_result_1.toLowerCase().includes(searchTerm));

          const matchesType =
            selectedType === "all" ||
            (selectedType === "Unknown" && !item.matching_check_phrase) ||
            (item.matching_check_phrase &&
              isLikeMatch(item.matching_check_phrase, selectedType));

          return matchesSearch && matchesType;
        });

        displayResults(1);
      }

      function isLikeMatch(value, pattern) {
        if (pattern === "all") return true;
        const regex = new RegExp(`^${pattern}`, "i");
        return regex.test(value);
      }

      function calculateStatistics(results) {
        const stats = {
          TCVN: 0,
          QCVN: 0,
          TCXD: 0,
          TCXDVN: 0,
          TCN: 0,
          ACI: 0,
          ASTM: 0,
          BHT: 0,
          IEC: 0,
          IEEE: 0,
          TCCS: 0,
          NFPA: 0,
          TC: 0,
          ITU: 0,
          Unknown: 0,
        };

        results.forEach((item) => {
          if (item.matching_check_phrase) {
            let matched = false;
            for (const prefix in stats) {
              if (isLikeMatch(item.matching_check_phrase, prefix)) {
                stats[prefix]++;
                matched = true;
                break;
              }
            }
            if (!matched) {
              stats.Unknown++;
            }
          } else {
            stats.Unknown++;
          }
        });

        return stats;
      }
    </script>
  </body>
</html>
```

5. Create file TCKT.xlsx

6. Create a `wsgi.py` file in the project root with the following content:
  ```
  from app import app

  if __name__ == "__main__":
      app.run(host='0.0.0.0', port=5001)
  ```

7. Create a `gunicorn_config.py` file in the project root with the following content:
  ```
  bind = "0.0.0.0:5001"
  workers = 4
  threads = 2
  timeout = 600
  max_requests = 1000
  keepalive = 5
  ```

8. Create a virtual environment:
  ```
  python -m venv venv
  ```

9. Activate the virtual environment:
  - On Windows:
    ```
    venv\Scripts\activate
    ```
  - On macOS and Linux:
    ```
    source venv/bin/activate
    ```

10. Install the required packages:
  ```
  pip install -r requirements.txt
  ```

11. Run the application using Gunicorn (UNIX/LINUX):
  ```
  gunicorn --config gunicorn_config.py wsgi:app
  ```

12. Deploy in Window:
  ```
  pip install waitress Paste
  ```

  Create new file `run_waitress.py`
  ```
  import logging
  import time
  from waitress import serve
  from app import app

  # Set up logging
  logging.basicConfig(
      filename='waitress.log',
      level=logging.INFO,
      format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
  )

  class LoggingMiddleware:
      def __init__(self, app):
          self.app = app

      def __call__(self, environ, start_response):
          request_time = time.time()
          response = self.app(environ, start_response)
          duration = time.time() - request_time

          logging.info(
              f"{environ['REMOTE_ADDR']} - - [{time.strftime('%d/%b/%Y %H:%M:%S')}] "
              f"\"{environ['REQUEST_METHOD']} {environ['PATH_INFO']} {environ['SERVER_PROTOCOL']}\" "
              f"- {duration:.6f}s"
          )

          return response

  if __name__ == '__main__':
      logged_app = LoggingMiddleware(app)
      serve(logged_app, host='0.0.0.0', port=5001, threads=4)
  ```

  ```
  python run_waitress.py
  ```