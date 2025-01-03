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
import pythoncom
import win32com.client

app = Flask(__name__)
os.makedirs(os.path.join(app.root_path, 'uploads', 'feedback'), exist_ok=True)

def extract_text_from_doc(file):
    _, file_extension = os.path.splitext(file.filename.lower())
    
    temp_file_path = os.path.join(os.environ.get('TEMP', '/tmp'), file.filename)
    temp_pdf_path = os.path.join(os.environ.get('TEMP', '/tmp'), f"{os.path.splitext(file.filename)[0]}.pdf")
    file.save(temp_file_path)
    
    try:
        pythoncom.CoInitialize()
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.visible = False
            doc = word.Documents.Open(temp_file_path)
            doc.SaveAs(temp_pdf_path, FileFormat=17) 
            doc.Close()
            word.Quit()
        except Exception as e:
            return f"Error converting to PDF: {str(e)}"
        finally:
            pythoncom.CoUninitialize()

        with open(temp_pdf_path, 'rb') as pdf_file:
            return extract_text_from_pdf(pdf_file)
            
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        if os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
            except:
                pass
    
def extract_page_text(page):
    return page.extract_text()

def extract_text_from_pdf(pdf_file):
    try:
        pdf_bytes = pdf_file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        texts = []
        
        for page in reader.pages:
            try:
                text = page.extract_text()
                texts.append(text)
            except Exception as e:
                print(f"Error extracting text from page: {str(e)}")
                texts.append("")
                continue
                
        return "\n\n".join(texts)
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return ""

def process_file(file):
    if file.filename.endswith('.pdf'):
        text = extract_text_from_pdf(file)
    elif file.filename.endswith('.doc') or file.filename.endswith('.docx'):
        text = extract_text_from_doc(file)
    else:
        raise ValueError("Unsupported file type")
    
    with open('text.txt', 'w', encoding='utf-8') as f:
        f.write(text)
        
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
        r"QĐ\s*-[A-Z0-9gĐ\s\r\n-]+\b",
        r"NĐ\s*-[A-Z0-9gĐ\s\r\n-]+\b",
        r"TT\s*-[A-Z0-9gĐ\s\r\n-]+\b"
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
            matches = re.finditer(pattern, page_text)
            for match in matches:
                phrase = re.sub(r'\s+', '', match.group().strip())
                line_num = page_text[:match.start()].count('\n') + 1
                base_text = next((standard for standard in standards if phrase.startswith(standard)), "")
                
                after_text = ""
                matching_check_phrase = None
                before_text = ""

                if base_text:
                    index = match.start()
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
                
                    updated_phrase = re.sub(r'--', '-', updated_phrase)
                    updated_phrase_normalized = re.sub(r'\s+', ' ', updated_phrase).strip()
                    if base_text in ["QĐ-", "NĐ-", "TT-"]:
                        original_doc_match = re.search(r'(\d+/(?:\d+/)?(?:NĐ|QĐ|TT)-[A-Za-z]+)', page_text[max(0, index-20):index+100])
                        if original_doc_match:
                            doc_number = original_doc_match.group(1)
                        else:
                            doc_number_match = re.search(r'(\d+/(?:\d+/)?(?:NĐ|QĐ|TT)-[A-Za-z]+)', updated_phrase_normalized)
                            doc_number = doc_number_match.group(1) if doc_number_match else None
                        
                        if doc_number:
                            try:
                                matching_check_phrase = next(
                                    (cp for cp in check_phrases 
                                    if (re.sub(r'\s+', ' ', cp).strip() == doc_number) or  # Exact match
                                    (doc_number.replace('-', '') in re.sub(r'[-\s]', '', cp).strip() and  # Partial match
                                    doc_number.split('-')[1] == re.sub(r'[-\s]', '', cp).strip().split('-')[1])),  # Suffix must match exactly
                                    None
                                )
                            except Exception:
                                matching_check_phrase = None
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)