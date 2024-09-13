import os
from flask import Flask, request, jsonify, render_template
from PyPDF2 import PdfReader
import re
import pandas as pd
import numpy as np
import json
import concurrent.futures


app = Flask(__name__)

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n\n"
    return text

def process_pdf(pdf_file):
    text = extract_text_from_pdf(pdf_file)
    results = []
    patterns = [
        r"TCVN\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"QCVN(?:\s+\w+)?(?:[-:]\d+)?(?:\s*:\s*\d+)?"
    ]

    # Load the Excel file
    df = pd.read_excel('TCKT.xlsx')
    
    # Use the first and last three columns
    first_col = df.columns[1]
    last_cols = df.columns[-3:]
    
    check_phrases = df[first_col].str.strip().tolist()
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
        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phrase = re.sub(r'\s+', '', match.group().strip())
                
                line_num = page_text[:match.start()].count('\n') + 1
                base_text = "TCVN" if phrase.startswith("TCVN") else "QCVN" if phrase.startswith("QCVN") else ""
                
                after_text = ""
                if base_text:
                    index = page_text.find(base_text, match.start())
                    if index != -1:
                        after_text = re.sub(r'\s+', '', page_text[index+4:index+24].strip())
                
                updated_phrase = f"{base_text} {after_text}" if base_text and after_text else ""
                
                updated_phrase_normalized = re.sub(r'\s+', '', updated_phrase).strip()
                matching_check_phrase = next((cp for cp in check_phrases if re.sub(r'\s+', '', cp).strip() in updated_phrase_normalized), None)
                matching_results = [
                    handle_nan(results_dict[f'col_{i}'].get(matching_check_phrase))
                    for i in range(-3, 0)
                ] if matching_check_phrase else [None] * 3

                page_results.append({
                    "phrase": phrase,
                    "page": page_num,
                    "line": line_num,
                    "base_text": base_text,
                    "after_text": after_text,
                    "updated_phrase": updated_phrase,
                    "matching_check_phrase": matching_check_phrase,
                    "matching_result_3": matching_results[0],
                    "matching_result_2": matching_results[1],
                    "matching_result_1": matching_results[2],
                    "standard_type": "TCVN" if phrase.startswith("TCVN") else "QCVN" if phrase.startswith("QCVN") else "Unknown",
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

# if __name__ == '__main__':
#     app.run(debug=True)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)