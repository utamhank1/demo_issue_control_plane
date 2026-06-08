from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    print("Received webhook payload!")
    print(json.dumps(payload, indent=2))
    return 'OK', 200

@app.route('/', methods=['GET'])
def health():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
