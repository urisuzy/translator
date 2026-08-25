import requests
from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator
from operator import itemgetter

# deep_translator sends no User-Agent, so requests defaults to "python-requests/x.x".
# Google's translate.google.com/m endpoint detects that as a bot and returns a
# disguised HTTP 200 "Error 500" page instead of a result, which deep_translator
# then reports as TranslationNotFound. A browser UA avoids the block.
requests.utils.default_user_agent = lambda name="python-requests": (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

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