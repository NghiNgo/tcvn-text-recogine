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