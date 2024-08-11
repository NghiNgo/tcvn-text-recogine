import os
from flask import Flask, request, jsonify, render_template
from PyPDF2 import PdfReader
import re

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
                
                # Get 15 characters after "N" in "TCVN" or "QCVN"
                after_text = ""
                if base_text in ["TCVN", "QCVN"]:
                    index = page_text.find(base_text, match.start())
                    if index != -1:
                        n_index = index + 4  # Index of "N" in "TCVN" or "QCVN"
                        after_text = page_text[n_index:n_index+15].strip()
                
                # Create formatted_after_text with all spaces removed
                formatted_after_text = re.sub(r'\s+', '', after_text)
                
                # Create updated_phrase by combining base_text and formatted_after_text
                updated_phrase = f"{base_text} {formatted_after_text}" if base_text and formatted_after_text else ""
                
                results.append({
                    "phrase": phrase,
                    "page": page_num,
                    "line": line_num,
                    "base_text": base_text,
                    "after_text": after_text,
                    "updated_phrase": updated_phrase
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

if __name__ == '__main__':
    app.run(debug=True)