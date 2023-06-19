from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator
from operator import itemgetter

app = Flask(__name__)

@app.route("/")
def hello_world():
  return "Translator"

@app.post("/translate")
def translate():
  if 'text' not in request.form:
    return jsonify({"message": "text not found"})
  
  required = ['text', 'source', 'target']
  if any(req not in request.form for req in required):
    return jsonify({"message": "some not found"})
  
  text, source, target = itemgetter('text', 'source', 'target')(request.form)
  translated = GoogleTranslator(source, target).translate(text)  
  return jsonify({"text": text, "translated": translated})

if __name__ == "__main__":
    app.run(debug = True, host='0.0.0.0', port=5000)