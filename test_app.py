import unittest
import io
from app import app, extract_text_from_pdf, process_pdf
from unittest.mock import patch, MagicMock

class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    @patch('app.PdfReader')
    @patch('app.multiprocessing.Pool')
    def test_extract_text_from_pdf(self, mock_pool, mock_pdf_reader):
        # Mock the PdfReader and multiprocessing.Pool
        mock_pdf_reader.return_value.pages = [MagicMock(), MagicMock()]
        mock_pool.return_value.__enter__.return_value.map.return_value = ['Page 1 text', 'Page 2 text']

        # Create a mock PDF file
        mock_pdf_file = io.BytesIO(b'Mock PDF content')

        result = extract_text_from_pdf(mock_pdf_file)
        self.assertEqual(result, 'Page 1 text\n\nPage 2 text')

    @patch('app.extract_text_from_pdf')
    @patch('app.pd.read_excel')
    def test_process_pdf(self, mock_read_excel, mock_extract_text):
        # Mock the extract_text_from_pdf function
        mock_extract_text.return_value = "TCVN 1234:2020 Some text\nQCVN 56:2019 Other text"

        # Mock the pandas DataFrame
        mock_df = MagicMock()
        mock_df.columns = ['Col1', 'Col2', 'Col3', 'Col4', 'Col5']
        mock_df['Col2'].str.strip.return_value = ['TCVN 1234:2020', 'QCVN 56:2019']
        mock_read_excel.return_value = mock_df

        # Create a mock PDF file
        mock_pdf_file = io.BytesIO(b'Mock PDF content')

        results = process_pdf(mock_pdf_file)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['phrase'], 'TCVN 1234:2020')
        self.assertEqual(results[1]['phrase'], 'QCVN 56:2019')

    def test_upload_file_no_file(self):
        response = self.app.post('/upload')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error": "No file part"', response.data)

    def test_upload_file_no_filename(self):
        response = self.app.post('/upload', data={'file': (io.BytesIO(b''), '')})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error": "No selected file"', response.data)

    def test_upload_file_invalid_type(self):
        response = self.app.post('/upload', data={'file': (io.BytesIO(b'test content'), 'test.txt')})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error": "Invalid file type"', response.data)

    @patch('app.process_pdf')
    def test_upload_file_valid_pdf(self, mock_process_pdf):
        mock_process_pdf.return_value = [{'phrase': 'TCVN 1234:2020'}]
        response = self.app.post('/upload', data={'file': (io.BytesIO(b'pdf content'), 'test.pdf')})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"phrase": "TCVN 1234:2020"', response.data)

if __name__ == '__main__':
    unittest.main()