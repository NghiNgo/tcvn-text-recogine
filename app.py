import os
from flask import Flask, request, jsonify, render_template
from PyPDF2 import PdfReader
import re
import pandas as pd
from openpyxl import load_workbook

app = Flask(__name__)

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n\n"
    return text

def process_pdf(pdf_file):
    text = extract_text_from_pdf(pdf_file)
    with open('text.txt', 'w', encoding='utf-8') as file:
        file.write(text)
    results = []
    patterns = [
        r"TCVN\s*\d+(?:[-:]\d+)?(?:[-:]\d+)?(?:\s*:\s*\d+(?:\s*\d+)?)?",
        r"QCVN(?:\s+\w+)?(?:[-:]\d+)?(?:\s*:\s*\d+)?"
    ]

    # Load the Excel file
    df = pd.read_excel('TCKT.xlsx')
    
    # Use the first and last three columns
    first_col = df.columns[1]
    last_col_3 = df.columns[-3]
    last_col_2 = df.columns[-2]
    last_col_1 = df.columns[-1]
    
    check_phrases = df[first_col].str.strip().tolist()
    results_dict = {
        'col_-3': dict(zip(df[first_col].str.strip(), df[last_col_3])),
        'col_-2': dict(zip(df[first_col].str.strip(), df[last_col_2])),
        'col_-1': dict(zip(df[first_col].str.strip(), df[last_col_1]))
    }

    def handle_nan(value):
        return None if pd.isna(value) else value
    
    pages = text.split('\n\n')
    for page_num, page_text in enumerate(pages, 1):
        for pattern in patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                phrase = match.group().strip()
                # Remove all spaces within the phrase
                phrase = re.sub(r'\s+', '', phrase)
                
                line_num = page_text[:match.start()].count('\n') + 1
                base_text = "TCVN" if phrase.startswith("TCVN") else "QCVN" if phrase.startswith("QCVN") else ""
                
                # Get 20 characters after "N" in "TCVN" or "QCVN"
                after_text = ""
                if base_text in ["TCVN", "QCVN"]:
                    index = page_text.find(base_text, match.start())
                    if index != -1:
                        n_index = index + 4  # Index of "N" in "TCVN" or "QCVN"
                        after_text = page_text[n_index:n_index+20].strip()
                
                # Create formatted_after_text with all spaces removed
                formatted_after_text = re.sub(r'\s+', '', after_text)
                
                # Create updated_phrase by combining base_text and formatted_after_text
                updated_phrase = f"{base_text} {formatted_after_text}" if base_text and formatted_after_text else ""
                
                # Find matching check_phrase and get the corresponding results
                matching_check_phrase = next((check_phrase for check_phrase in check_phrases if check_phrase in updated_phrase), None)
                matching_result_3 = handle_nan(results_dict['col_-3'].get(matching_check_phrase)) if matching_check_phrase else None
                matching_result_2 = handle_nan(results_dict['col_-2'].get(matching_check_phrase)) if matching_check_phrase else None
                matching_result_1 = handle_nan(results_dict['col_-1'].get(matching_check_phrase)) if matching_check_phrase else None

                results.append({
                    "phrase": phrase,
                    "page": page_num,
                    "line": line_num,
                    "base_text": base_text,
                    "after_text": after_text,
                    "updated_phrase": updated_phrase,
                    "matching_check_phrase": matching_check_phrase,
                    "matching_result_3": matching_result_3,
                    "matching_result_2": matching_result_2,
                    "matching_result_1": matching_result_1
                })

    return results

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
        return jsonify(results)
    else:
        return jsonify({"error": "Invalid file type"}), 400

# if __name__ == '__main__':
#     app.run(debug=True)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)