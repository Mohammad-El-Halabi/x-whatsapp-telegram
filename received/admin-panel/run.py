import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.config.settings import DEBUG, HOST, PORT
from src.routes.admin import app

if __name__ == '__main__':
    app.run(debug=DEBUG, host=HOST, port=PORT)
