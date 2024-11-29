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
Paste==3.8.0
PyMuPDF==1.23.26
PyPDF2==3.0.1
python-dateutil==2.9.0.post0
pytz==2024.1
six==1.12.0
typing_extensions==4.12.2
tzdata==2024.1
waitress==3.0.0
Werkzeug==3.0.3
zipp==3.20.0
python-docx==0.8.11
textract==1.6.3
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
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import send_from_directory
import uuid
from docx import Document
import textract
import tempfile

app = Flask(__name__)
os.makedirs(os.path.join(app.root_path, 'uploads', 'feedback'), exist_ok=True)

def extract_text_from_doc(file):
    if file.filename.endswith('.docx'):
        doc = Document(file)
        return '\n\n'.join([paragraph.text for paragraph in doc.paragraphs])
    elif file.filename.endswith('.doc'):
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.doc') as temp_file:
            file.save(temp_file.name)
            temp_file_path = temp_file.name

        try:
            # Process the temporary file
            text = textract.process(temp_file_path).decode('utf-8')
        finally:
            # Delete the temporary file
            os.unlink(temp_file_path)

        return text
    
def extract_page_text(page):
    return page.extract_text()

def extract_text_from_pdf(pdf_file):
    pdf_bytes = pdf_file.read()
    
    reader = PdfReader(io.BytesIO(pdf_bytes))
    
    with multiprocessing.Pool() as pool:
        texts = pool.map(extract_page_text, reader.pages)
    
    return "\n\n".join(texts)

def process_file(file):
    if file.filename.endswith('.pdf'):
        text = extract_text_from_pdf(file)
    elif file.filename.endswith('.doc') or file.filename.endswith('.docx'):
        text = extract_text_from_doc(file)
    else:
        raise ValueError("Unsupported file type")
    results = []
    het_hieu_luc_counter = [0]
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
        r"ITU(?:-[TR])?\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        # r"QĐ-[A-Za-z0-9Đ-]+",
        # r"NĐ-[A-Za-z0-9Đ-]+", 
        # r"TT-[A-Za-z0-9Đ-]+"
    ]

    # Load the Excel file
    df = pd.read_excel('TCKT.xlsx')
    
    # Use the first and last three columns
    first_col = df.columns[1]
    last_cols = df.columns[-5:]

    if isinstance(df, pd.DataFrame):
        check_phrases = df[first_col].str.strip().tolist()
    else:
        check_phrases = [str(item).strip() for item in df]

    results_dict = {
        f'col_{i}': dict(zip(df[first_col].str.strip(), df[col]))
        for i, col in enumerate(last_cols, start=-5)
    }

    def handle_nan(value):
        if pd.isna(value) or (isinstance(value, float) and np.isnan(value)):
            return None
        return value

    def process_page(page_data):
        page_num, page_text = page_data
        page_results = []
        standards = ["TCVN", "QCVN", "TCXD", "TCXDVN", "TCN", "ACI", "ASTM", "BHT", "IEC", "IEEE", "TCCS", "NFPA", "TC", "ITU", "QĐ-", "NĐ-", "TT-"]
        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phrase = re.sub(r'\s+', '', match.group().strip())
                line_num = page_text[:match.start()].count('\n') + 1
                base_text = next((standard for standard in standards if phrase.startswith(standard)), "")
                
                after_text = ""
                matching_check_phrase = None
                before_text = ""

                if base_text:
                    index = page_text.find(base_text, match.start())
                    if index != -1:
                        if base_text == "QĐ-" or base_text == "NĐ-" or base_text == "TT-":
                            before_text = page_text[index-20:index].strip()
                            after_text = page_text[index+len(base_text):index+len(base_text)+50].strip()
                            for standard in standards:
                                if standard in after_text:
                                    after_text = re.sub(r'\s+', ' ', after_text[:after_text.index(standard) + len(standard)])
                                    break
                            else:
                                after_text = re.sub(r'\s+', ' ', after_text[:24])
                            updated_phrase = f"{before_text}{base_text}{after_text}".strip() if base_text else ""
                        else:
                            after_text = page_text[index+len(base_text):index+len(base_text)+50].strip()
                            for standard in standards:
                                if standard in after_text:
                                    after_text = re.sub(r'\s+', ' ', after_text[:after_text.index(standard) + len(standard)])
                                    break
                            else:
                                after_text = re.sub(r'\s+', ' ', after_text[:24])

                            updated_phrase = f"{base_text} {after_text}".strip() if base_text else ""
                    else:
                        updated_phrase = f"{base_text} {after_text}".strip() if base_text else ""
                
                    updated_phrase_normalized = re.sub(r'\s+', '', updated_phrase).strip()
                    if base_text in ["QĐ-", "NĐ-", "TT-"]:
                        original_doc_match = re.search(r'(\d+/(?:\d+/)?(?:NĐ|QĐ|TT)-[A-Za-z]+)', page_text[max(0, index-20):index+100])
                        if original_doc_match:
                            doc_number = original_doc_match.group(1)
                        else:
                            doc_number_match = re.search(r'(\d+/(?:\d+/)?(?:NĐ|QĐ|TT)-[A-Za-z]+)', updated_phrase_normalized)
                            doc_number = doc_number_match.group(1) if doc_number_match else None
                        
                        if doc_number:
                            matching_check_phrase = next(
                                (cp for cp in check_phrases 
                                if (re.sub(r'\s+', '', cp).strip() == doc_number) or  # Exact match
                                (doc_number.replace('-', '') in re.sub(r'[-\s]', '', cp).strip() and  # Partial match
                                doc_number.split('-')[1] == re.sub(r'[-\s]', '', cp).strip().split('-')[1])),  # Suffix must match exactly
                                None
                            )
                        else:
                            matching_check_phrase = None
                    else:
                        matching_check_phrase = next(
                            (cp for cp in check_phrases 
                            if re.sub(r'\s+', '', cp).strip() == updated_phrase_normalized),
                            None
                        )
                    matching_results = [
                            handle_nan(results_dict[f'col_{i}'].get(matching_check_phrase))
                        for i in range(-5, 0)
                    ] if matching_check_phrase else [None] * 5

                    if matching_results[0] and 'Hết hiệu lực' in matching_results[0]:
                        het_hieu_luc_counter[0] += 1

                    first_col_value = df[first_col].loc[df[first_col].str.strip() == matching_check_phrase].values[0] if matching_check_phrase else None

                    if first_col_value is None and ("TCVN" in phrase or "QCVN" in phrase):
                        custom_phrase = updated_phrase.replace("-", ":")
                        if custom_phrase.startswith("TCVN") or custom_phrase.startswith("QCVN"):
                            base_text = "TCVN" if custom_phrase.startswith("TCVN") else "QCVN"
                            after_text = custom_phrase[4:].strip() if base_text == "TCVN" else custom_phrase[4:].strip()
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
                            for i in range(-5, 0)
                        ] if matching_check_phrase else [None] * 5

                        if matching_results[0] and 'Hết hiệu lực' in matching_results[0]:
                            het_hieu_luc_counter[0] += 1

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
                        "matching_result_3": matching_results[1],
                        "matching_result_2": matching_results[2],
                        "matching_result_1": matching_results[4],
                        "standard_type": base_text if base_text else "Unknown",
                        "numeric_part": re.search(r'\d+', phrase).group() if re.search(r'\d+', phrase) else "",
                        "full_reference": f"{base_text} {after_text}".strip(),
                        "is_het_hieu_luc": matching_results[1] and 'Hết hiệu lực' in matching_results[1],
                        "name_col_value": matching_results[0]
                    })

        return page_results

    pages = list(enumerate(text.split('\n\n'), 1))
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(process_page, pages))
    
    flattened_results = [item for sublist in results for item in sublist]
    
    return {
        'results': flattened_results,
        'het_hieu_luc_count': het_hieu_luc_counter[0]
    }

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
    if file and file.filename.lower().endswith(('.pdf', '.doc', '.docx')):
        processed_data = process_file(file)
        return json.dumps({
            'results': processed_data['results'],
            'het_hieu_luc_count': processed_data['het_hieu_luc_count']
        }, ensure_ascii=False, default=str)
    else:
        return jsonify({"error": "Invalid file type"}), 400
    
UPLOAD_FOLDER = 'uploads/feedback'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    data = request.form.to_dict()
    data['feedback_id'] = str(uuid.uuid4())
    data['timestamp'] = datetime.now().isoformat()
    data['status'] = 'pending'
    data['ip_address'] = request.remote_addr
    data['user_agent'] = request.user_agent.string
    data['resolve_time'] = None
    data['resolved_by'] = None

    if 'attachment' in request.files:
        file = request.files['attachment']
        if file.filename != '':
            filename = secure_filename(f"{data['timestamp']}_{file.filename}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            data['attachment'] = filename

    feedback_file = 'feedback.json'
    
    # if not os.path.exists(feedback_file):
    #     with open(feedback_file, 'w') as f:
    #         json.dump([], f)

    try:
        with open(feedback_file, 'r', encoding='utf-8') as f:
            content = f.read()
            feedback_data = json.loads(content) if content else []
    except UnicodeDecodeError:
        try:
            with open(feedback_file, 'r', encoding='latin-1') as f:
                content = f.read()
                feedback_data = json.loads(content) if content else []
        except json.JSONDecodeError:
            feedback_data = []
    except json.JSONDecodeError:
        feedback_data = []

    feedback_data.append(data)

    with open('feedback.json', 'w') as f:
        json.dump(feedback_data, f, indent=2, ensure_ascii=False)

    return jsonify({"message": "Feedback submitted successfully"}), 200

@app.route('/uploads/feedback/<filename>')
def serve_feedback_attachment(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/manage-feedback')
def manage_feedback():
    try:
        with open('feedback.json', 'r', encoding='utf-8') as f:
            feedback_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        feedback_data = []
    
    return render_template('manage_feedback.html', feedback=feedback_data)

@app.route('/update-feedback-status', methods=['POST'])
def update_feedback_status():
    feedback_id = request.form.get('feedback_id')
    new_status = request.form.get('status')
    resolved_by = request.form.get('resolved_by')

    try:
        with open('feedback.json', 'r', encoding='utf-8') as f:
            feedback_data = json.load(f)
        
        for item in feedback_data:
            if item['feedback_id'] == feedback_id:
                item['status'] = new_status
                item['resolved_by'] = resolved_by
                if new_status == 'resolved':
                    item['resolve_time'] = datetime.now().isoformat()
        
        with open('feedback.json', 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"message": "Feedback status updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.template_filter('parse_timestamp')
def parse_timestamp(timestamp_str, format_str):
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%f')
        return dt.strftime(format_str)
    except ValueError:
        return timestamp_str 

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=5001)

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
      .pagination .ellipsis {
        padding: 8px 12px;
        color: #2c3e50;
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

      #feedback-text {
        width: 96%;
        padding: 10px;
        margin-bottom: 10px;
        border: 2px solid #ddd;
        border-radius: 4px;
        resize: vertical;
        font-family: "Open Sans", sans-serif;
      }

      #feedback-form button {
        display: block;
        width: 100%;
        padding: 10px;
        background-color: #ffc107 !important;
        color: #212529 !important;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        font-weight: 700;
      }

      .right-buttons {
        display: flex;
        gap: 10px;
      }

      #feedback {
        display: block;
        margin: 20px auto;
        padding: 10px 20px;
        background-color: #ffc107;
        color: #212529;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        margin-left: auto;
      }

      #feedback:hover {
        background-color: #e0a800;
        color: #212529;
      }

      #feedback-form input[type="text"],
      #feedback-form input[type="tel"],
      #feedback-form textarea {
        width: 96%;
        padding: 10px;
        margin-bottom: 10px;
        border: 2px solid #ddd;
        border-radius: 4px;
        font-family: "Open Sans", sans-serif;
      }

      #feedback-form input[type="file"] {
        width: 96%;
        margin-bottom: 10px;
      }

      #feedback-form button {
        display: block;
        width: 100%;
        padding: 10px;
        background-color: #ffc107;
        color: #212529;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.3s;
        font-weight: 700;
      }

      #feedback-form button:hover {
        background-color: #e0a800;
        color: #212529;
      }

      .button-group {
        display: flex;
        justify-content: space-between;
        gap: 10px;
      }

      .button-group button {
        flex: 1;
      }

      #feedback-form #cancel-feedback {
        background-color: #e74c3c !important;
      }

      #feedback-form #cancel-feedback:hover {
        background-color: #c0392b !important;
      }

      .stat-item.het-hieu-luc {
        background-color: #e74c3c;
        color: white;
      }

      .stat-item.het-hieu-luc h3,
      .stat-item.het-hieu-luc .stat-count {
        color: white;
      }

      .stat-item.het-hieu-luc:hover {
        background-color: #c0392b;
      }

      #author-info {
        background-color: #34495e;
        color: #ecf0f1;
        text-align: center;
        padding: 15px 0;
        margin-top: 30px;
        border-radius: 8px;
        font-size: 0.9rem;
      }

      #author-info p {
        margin: 5px 0;
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
        <input type="file" id="pdf-file" accept=".pdf,.doc,.docx" required />
        <label for="pdf-file">Chọn file</label>
      </div>
      <div class="button-row">
        <div class="left-buttons">
          <button type="submit">Tải lên và xử lý</button>
          <a id="download-xlsx" href="#" class="button" style="display: none">
            Tải xuống XLSX
          </a>
        </div>
        <div class="right-buttons">
          <a id="feedback" href="#" class="button">Góp ý & báo lỗi</a>
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
        <!-- <div class="stat-item" onclick="filterByType('TCVN')">
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
        <div class="stat-item" onclick="filterByType('QĐ-')">
          <h3>Quyết định</h3>
          <span id="qd-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('NĐ-')">
          <h3>Nghị định</h3>
          <span id="nd-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('TT-')">
          <h3>Thông tư</h3>
          <span id="tt-count" class="stat-count">0</span>
        </div> -->
        <div
          class="stat-item con-hieu-luc"
          onclick="filterByType('HienHanh')"
        >
          <h3>Còn hiệu lực</h3>
          <span id="con-hieu-luc-count" class="stat-count">0</span>
        </div>
        <div
          class="stat-item het-hieu-luc"
          onclick="filterByType('HetHieuLuc')"
        >
          <h3>Hết hiệu lực</h3>
          <span id="het-hieu-luc-count" class="stat-count">0</span>
        </div>
        <div class="stat-item" onclick="filterByType('Unknown')">
          <h3>Chưa xác định</h3>
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
      <select
        id="standard-type-select"
        onchange="applyFilters()"
        style="display: none"
      >
        <!-- <option value="all">Tất cả</option>
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
        <option value="QĐ-">QĐ</option>
        <option value="NĐ-">NĐ</option>
        <option value="TT-">TT</option> -->
        <option value="HienHanh">Còn hiệu lực</option>
        <option value="HetHieuLuc">Hết hiệu lực</option>
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

    <div id="feedback-modal" class="modal">
      <div class="modal-content">
        <span class="close">&times;</span>
        <h2 class="modal-title">Góp ý & Báo lỗi</h2>
        <form id="feedback-form">
          <input
            type="text"
            id="feedback-name"
            placeholder="Họ và tên"
            required
          />
          <input
            type="tel"
            id="feedback-phone"
            placeholder="Số điện thoại"
            required
          />
          <input
            type="text"
            id="feedback-department"
            placeholder="Phòng ban"
            required
          />
          <textarea
            id="feedback-content"
            rows="5"
            placeholder="Nội dung góp ý hoặc báo lỗi..."
            required
          ></textarea>
          <input type="file" id="feedback-attachment" accept="image/*" />
          <div class="button-group">
            <button type="submit">Gửi</button>
            <button type="button" id="cancel-feedback">Huỷ</button>
          </div>
        </form>
      </div>
    </div>
    <footer id="author-info">
      <p>Developed by: IT P8 - PECC4</p>
      <p>Contact: it@pecc4.vn</p>
    </footer>
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
          document.getElementById("statistics-container").style.display = "none";
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
              allResults = data.results;
              console.log(allResults);
              filteredResults = allResults;
              const stats = calculateStatistics(allResults);
              const totalCountElement = document.getElementById("total-count");

              if (totalCountElement) {
                totalCountElement.textContent =
                  Object.entries(stats).reduce((total, [key, value]) => {
                    return total + value;
                  }, 0);

                const parentDiv = totalCountElement.closest(".stat-item");
                if (parentDiv) {
                  parentDiv.classList.add("active");
                }
              }

              const statItems = {
                // tcvn: "TCVN",
                // qcvn: "QCVN",
                // tcxd: "TCXD",
                // tcxdvn: "TCXDVN",
                // tcn: "TCN",
                // aci: "ACI",
                // astm: "ASTM",
                // bht: "BHT",
                // iec: "IEC",
                // ieee: "IEEE",
                // tccs: "TCCS",
                // nfpa: "NFPA",
                // tc: "TC",
                // itu: "ITU",
                // qd: "QĐ-",
                // nd: "NĐ-",
                // tt: "TT-",
                "con-hieu-luc": "HienHanh",
                unknown: "Unknown",
                "het-hieu-luc": "HetHieuLuc",
              };

              for (const [id, type] of Object.entries(statItems)) {
                // const count =
                //   type === "HetHieuLuc" ? data.het_hieu_luc_count : stats[type];
                const count = stats[type];
                const element = document.getElementById(`${id}-count`);
                if (element) {
                  element.textContent = count;
                  element.closest(".stat-item").style.display =
                    count > 0 ? "block" : "none";
                }
              }

              displayResults(1);
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
        document.querySelectorAll(".stat-item").forEach((item) => {
          item.classList.remove("active");
        });

        const clickedItem = document.querySelector(
          `.stat-item[onclick="filterByType('${type}')"]`
        );
        
        if (clickedItem) {
          clickedItem.classList.add("active");
        }

        document.getElementById("standard-type-select").value = type;
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
                ${
                  item.matching_check_phrase
                    ? `<strong>Số hiệu:</strong> ${item.first_col_value}<br>`
                    : `<strong>Số hiệu:</strong> <span style="color: brown;">Không tìm thấy</span><br>`
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
                ${
                  item.matching_result_1
                    ? `<strong>Văn bản sửa đổi bổ sung:</strong> <span style="color: red;">${item.matching_result_1}</span><br>`
                    : ""
                }
                <strong>Trang:</strong> ${item.page}, <strong>Dòng:</strong> ${
                  item.line
                }<br>
                <strong>Tìm theo: </strong> ${item.phrase}
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
        const exportData = filteredResults
        .filter((item) => item.matching_check_phrase)
        .map((item) => ({
          "Số hiệu": item.matching_check_phrase || "Không tìm thấy",
          "Tên văn bản": item.name_col_value || "",
          "Tình trạng": item.matching_result_3 || "Không tìm thấy",
          "Văn bản thay thế": item.matching_result_2 || "",
          "Văn bản sửa đổi bổ sung": item.matching_result_1 || "",
          // "Tìm theo": item.phrase,
          Trang: item.page,
          Dòng: item.line,
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
          version: "1.4",
          date: "2024-10-28",
          changes: ["Áp dụng thêm cho định dạng .doc, .docx", "Thêm các thống kê QĐ, TT, NĐ"],
        },
        {
          version: "1.3",
          date: "2024-09-25",
          changes: ["Thêm phần góp ý & báo lỗi", "Thêm thống kê Hết hiệu lực"],
        },
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
        },
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

        const maxVisiblePages = 5;
        const ellipsis = '<span class="ellipsis">...</span>';

        if (totalPages <= maxVisiblePages) {
          // If total pages are less than or equal to maxVisiblePages, show all pages
          for (let i = 1; i <= totalPages; i++) {
            paginationHtml += generatePageButton(i);
          }
        } else {
          // Always show first page
          paginationHtml += generatePageButton(1);

          if (currentPage > 3) {
            paginationHtml += ellipsis;
          }

          // Calculate start and end of visible page range
          let start = Math.max(2, currentPage - 1);
          let end = Math.min(currentPage + 1, totalPages - 1);

          // Adjust range if at the start or end
          if (currentPage <= 3) {
            end = Math.min(maxVisiblePages - 1, totalPages - 1);
          } else if (currentPage >= totalPages - 2) {
            start = Math.max(2, totalPages - maxVisiblePages + 2);
          }

          // Generate buttons for visible pages
          for (let i = start; i <= end; i++) {
            paginationHtml += generatePageButton(i);
          }

          if (currentPage < totalPages - 2) {
            paginationHtml += ellipsis;
          }

          // Always show last page
          paginationHtml += generatePageButton(totalPages);
        }

        paginationHtml += "</div>";
        return paginationHtml;
      }

      function generatePageButton(pageNumber) {
        return `<button onclick="displayResults(${pageNumber})" ${
          pageNumber === currentPage ? 'class="active"' : ""
        }>${pageNumber}</button>`;
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
            selectedType === "all"||
            (selectedType === "Unknown" && !item.matching_check_phrase) ||
            (selectedType === "HetHieuLuc" &&
              item.matching_result_3 &&
              item.matching_result_3.includes("Hết hiệu lực")) ||
            (selectedType === "HienHanh" &&
              item.matching_result_3 &&
              item.matching_result_3.includes("Hiện hành")) ||
            isLikeMatch(item.matching_check_phrase, selectedType);

          return matchesSearch && matchesType;
        });

        displayResults(1);
      }

      function isLikeMatch(value, pattern) {
        if (pattern === "all") return true;
        const regex = new RegExp(pattern, "i");
        return regex.test(value);
      }

      function calculateStatistics(results) {
        const stats = {
          // TCVN: 0,
          // QCVN: 0,
          // TCXD: 0,
          // TCXDVN: 0,
          // TCN: 0,
          // ACI: 0,
          // ASTM: 0,
          // BHT: 0,
          // IEC: 0,
          // IEEE: 0,
          // TCCS: 0,
          // NFPA: 0,
          // TC: 0,
          // ITU: 0,
          // "QĐ-": 0,
          // "NĐ-": 0,
          // "TT-": 0,
          HienHanh: 0,
          Unknown: 0,
          HetHieuLuc: 0,
        };

        results.forEach((item) => {
          if (
            item.matching_result_3 &&
            item.matching_result_3.includes("Hết hiệu lực")
          ) {
            stats.HetHieuLuc++;
          }
          if (
            item.matching_result_3 &&
            item.matching_result_3.includes("Hiện hành")
          ) {
            stats.HienHanh++;
          }
          if (item.matching_check_phrase) {
            let matched = false;
            for (const prefix in stats) {
              if (isLikeMatch(item.matching_check_phrase, prefix)) {
                stats[prefix]++;
                matched = true;
                break;
              }
            }
          } else {
            stats.Unknown++;
          }
        });
        return stats;
      }

      const feedbackModal = document.getElementById("feedback-modal");
      const feedbackBtn = document.getElementById("feedback");
      const feedbackClose = feedbackModal.getElementsByClassName("close")[0];

      feedbackBtn.onclick = function (e) {
        e.preventDefault();
        feedbackModal.style.display = "block";
      };

      feedbackClose.onclick = function () {
        feedbackModal.style.display = "none";
      };

      document.getElementById("feedback-form").onsubmit = function (e) {
        e.preventDefault();
        const formData = new FormData();
        formData.append("name", document.getElementById("feedback-name").value);
        formData.append(
          "phone",
          document.getElementById("feedback-phone").value
        );
        formData.append(
          "department",
          document.getElementById("feedback-department").value
        );
        formData.append(
          "content",
          document.getElementById("feedback-content").value
        );

        const attachment = document.getElementById("feedback-attachment")
          .files[0];
        if (attachment) {
          formData.append("attachment", attachment);
        }

        fetch("/submit-feedback", {
          method: "POST",
          body: formData,
        })
          .then((response) => response.json())
          .then((data) => {
            alert("Cảm ơn bạn đã gửi góp ý!");
            feedbackModal.style.display = "none";
            document.getElementById("feedback-form").reset();
          })
          .catch((error) => {
            console.error("Error:", error);
            alert("Có lỗi xảy ra khi gửi góp ý. Vui lòng thử lại sau.");
          });
      };

      window.onclick = function (event) {
        if (event.target == modal) {
          modal.style.display = "none";
        }
        if (event.target == feedbackModal) {
          feedbackModal.style.display = "none";
        }
      };

      document.getElementById("cancel-feedback").onclick = function () {
        feedbackModal.style.display = "none";
        document.getElementById("feedback-form").reset();
      };
    </script>
  </body>
</html>
```

5. Create file `manage_feedback.html`
```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quản Lý Phản Hồi</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300..800;1,300..800&display=swap" rel="stylesheet">
    <link
      rel="icon"
      href="{{ url_for('static', filename='evn.png') }}"
      type="image/png"
    />
    <style>
        body {
            font-family: "Open Sans", sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f0f4f8;
            color: #333;
        }
        .container {
            max-width: 1000px;
            margin: auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1, h2 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            font-weight: 700;
        }
        .feedback-item {
            background-color: #f9f9f9;
            border: 1px solid #ddd;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        .feedback-item:hover {
            transform: translateY(-2px);
        }
        .feedback-item h3 {
            margin-top: 0;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .status-pending {
            color: #ffa500;
        }
        .status-resolved {
            color: #2ecc71;
        }
        select, input[type="text"] {
            padding: 10px;
            margin: 5px 0;
            border: 2px solid #ddd;
            border-radius: 4px;
            font-family: "Open Sans", sans-serif;
            transition: border-color 0.3s;
        }
        select:focus, input[type="text"]:focus {
            outline: none;
            border-color: #3498db;
        }
        button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 12px 20px;
            margin: 5px 0;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.3s;
            font-weight: 700;
        }
        button:hover {
            background-color: #2980b9;
        }
        a {
            color: #3498db;
            text-decoration: none;
            transition: color 0.3s;
        }
        a:hover {
            color: #2980b9;
        }
        .tabs {
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border: 1px solid #ddd;
            background-color: #f9f9f9;
            transition: background-color 0.3s, color 0.3s;
            margin: 0 5px;
            border-radius: 4px;
        }
        .tab:hover {
            background-color: #e0e0e0;
        }
        .tab.active {
            color: white;
            font-weight: bold;
        }
        .tab.all.active {
            background-color: #3498db;
        }
        .tab.pending.active {
            background-color: #ffa500;
        }
        .tab.resolved.active {
            background-color: #2ecc71;
        }
        .status-pending {
            color: #ffa500;
        }
        .status-resolved {
            color: #2ecc71;
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
        #page-info {
            margin: 0 10px;
            align-self: center;
            font-weight: bold;
            color: #2c3e50;
        }
        .statistics {
        display: flex;
        justify-content: space-around;
        margin-bottom: 20px;
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        .stat-item {
            text-align: center;
            padding: 10px;
            border-radius: 4px;
            transition: transform 0.2s;
        }
        .stat-item:hover {
            transform: translateY(-2px);
        }
        .stat-item .count {
            font-size: 24px;
            font-weight: bold;
        }
        .stat-item .label {
            font-size: 14px;
            margin-top: 5px;
        }
        .stat-pending {
            color: #ffa500;
            background-color: rgba(255, 165, 0, 0.1);
        }
        .stat-resolved {
            color: #2ecc71;
            background-color: rgba(46, 204, 113, 0.1);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Quản Lý Phản Hồi</h1>
        
        <div class="statistics">
            <div class="stat-item stat-pending">
                <div class="count" id="pending-count">0</div>
                <div class="label">Đang Chờ</div>
            </div>
            <div class="stat-item stat-resolved">
                <div class="count" id="resolved-count">0</div>
                <div class="label">Đã Giải Quyết</div>
            </div>
        </div>

        <div class="tabs">
            <div class="tab all active" onclick="showTab('all')">Tất Cả</div>
            <div class="tab pending" onclick="showTab('pending')">Đang Chờ</div>
            <div class="tab resolved" onclick="showTab('resolved')">Đã Giải Quyết</div>
        </div>

        <div id="feedback-list">
            {% for item in feedback %}
                <div class="feedback-item" data-status="{{ item.status }}">
                    <h3>Phản Hồi #{{ item.feedback_id[:8] }}</h3>
                    <p><strong>Tên:</strong> {{ item.name }}</p>
                    <p><strong>Phòng Ban:</strong> {{ item.department }}</p>
                    <p><strong>Nội Dung:</strong> {{ item.content }}</p>
                    <p><strong>Đã Gửi:</strong> {{ item.timestamp|parse_timestamp('%Y-%m-%d %H:%M:%S') }}</p>
                    <p><strong>Trạng Thái:</strong> <span class="status-{{ item.status }}">{{ item.status }}</span></p>
                    {% if item.pending_timestamp %}
                        <p><strong>Đang Chờ Từ:</strong> {{ item.pending_timestamp|parse_timestamp('%Y-%m-%d %H:%M:%S') }}</p>
                    {% endif %}
                    {% if item.resolve_time %}
                        <p><strong>Đã Giải Quyết Vào:</strong> {{ item.resolve_time|parse_timestamp('%Y-%m-%d %H:%M:%S') }}</p>
                    {% endif %}
                    {% if item.attachment %}
                        <p><strong>Tệp Đính Kèm:</strong> <a href="{{ url_for('serve_feedback_attachment', filename=item.attachment) }}" target="_blank">Xem Tệp Đính Kèm</a></p>
                    {% endif %}
                    <select id="status-{{ item.feedback_id }}">
                        <option value="pending" {% if item.status == 'pending' %}selected{% endif %}>Đang Chờ</option>
                        <option value="resolved" {% if item.status == 'resolved' %}selected{% endif %}>Đã Giải Quyết</option>
                    </select>
                    <input type="text" id="resolved-by-{{ item.feedback_id }}" placeholder="Người Giải Quyết" value="{{ item.resolved_by or '' }}">
                    <button onclick="updateStatus('{{ item.feedback_id }}')">Cập Nhật Trạng Thái</button>
                </div>
            {% endfor %}
        </div>

        <div class="pagination">
            <button onclick="changePage(-1)">Trước</button>
            <span id="page-info">Trang 1 / 1</span>
            <button onclick="changePage(1)">Sau</button>
        </div>
    </div>

    <script>
        let currentPage = 1;
        const itemsPerPage = 10;
        let currentTab = 'all';

        function updateStatus(feedbackId) {
            const status = document.getElementById(`status-${feedbackId}`).value;
            const resolvedBy = document.getElementById(`resolved-by-${feedbackId}`).value;
            
            fetch('/update-feedback-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `feedback_id=${feedbackId}&status=${status}&resolved_by=${resolvedBy}`
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                location.reload();
            })
            .catch((error) => {
                console.error('Error:', error);
                alert('An error occurred while updating the status.');
            });
        }

        function showTab(status) {
            currentTab = status;
            currentPage = 1;
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            updateDisplay();
        }

        function updateDisplay() {
            const items = document.querySelectorAll('.feedback-item');
            let visibleItems = 0;
            items.forEach((item, index) => {
                const itemStatus = item.dataset.status;
                const isVisible = (currentTab === 'all' || itemStatus === currentTab) &&
                                  (index >= (currentPage - 1) * itemsPerPage && index < currentPage * itemsPerPage);
                item.style.display = isVisible ? 'block' : 'none';
                if (isVisible) visibleItems++;
            });

            updatePagination(items.length);
            updateStatistics();
        }

        function updatePagination(totalItems) {
            const pageCount = Math.ceil(totalItems / itemsPerPage);
            const prevButton = document.querySelector('.pagination button:first-child');
            const nextButton = document.querySelector('.pagination button:last-child');
            
            document.getElementById('page-info').textContent = `Page ${currentPage} of ${pageCount}`;
            
            prevButton.disabled = currentPage === 1;
            nextButton.disabled = currentPage === pageCount;
            
            prevButton.classList.toggle('active', currentPage !== 1);
            nextButton.classList.toggle('active', currentPage !== pageCount);
        }

        function changePage(direction) {
            const items = document.querySelectorAll('.feedback-item');
            const pageCount = Math.ceil(items.length / itemsPerPage);
            currentPage += direction;
            if (currentPage < 1) currentPage = 1;
            if (currentPage > pageCount) currentPage = pageCount;
            updateDisplay();
        }

        function updateStatistics() {
            const items = document.querySelectorAll('.feedback-item');
            let counts = {pending: 0, in_progress: 0, resolved: 0};
            items.forEach(item => {
                const status = item.dataset.status;
                counts[status]++;
            });
            document.getElementById('pending-count').textContent = counts.pending;
            document.getElementById('resolved-count').textContent = counts.resolved;
        }

        // Initial display update
        updateDisplay();
    </script>
</body>
</html>
```

6. Create file TCKT.xlsx

7. Create a `wsgi.py` file in the project root with the following content:
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