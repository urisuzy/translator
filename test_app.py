"""Self-check: python test_app.py (needs flask + deep_translator installed)."""

import json

from deep_translator.exceptions import TooManyRequests

import app as app_module


def client():
    app_module._translate.cache_clear()
    app_module._blocked_until.clear()
    app_module.MIN_INTERVAL = 0.0
    return app_module.app.test_client()


def fake_translator(result=None, error=None, counter=None, prefix=""):
    class Fake:
        def __init__(self, source=None, target=None, email=None, proxies=None):
            pass

        def translate(self, text):
            if counter is not None:
                counter.append(prefix + text)
            if error is not None:
                raise error
            return result

    return Fake


def stub(google=None, mymemory=None, llm=None):
    """Wire the providers. Anything not given fails, so order is observable."""
    app_module.GoogleTranslator = google or fake_translator(error=TooManyRequests())
    app_module.MyMemoryTranslator = mymemory or fake_translator(error=TooManyRequests())
    app_module.LLM_BASE_URL = "http://llm.test/v1" if llm else ""
    app_module.LLM_API_KEY = "test-key" if llm else ""
    if llm:
        app_module.requests.post = llm


def llm_response(content, status=200, counter=None, trailing="data: [DONE]"):
    class Response:
        status_code = status
        # The real gateway appends the SSE terminator to plain JSON responses.
        text = json.dumps({"choices": [{"message": {"content": content}}]}) + trailing

    def post(url, **kwargs):
        if counter is not None:
            counter.append(kwargs.get("json", {}).get("messages", [{}])[-1].get("content"))
        return Response()

    return post


def test_missing_text_is_a_400_not_a_200():
    res = client().post("/translate", data={"source": "en", "target": "id"})
    assert res.status_code == 400, res.status_code
    assert res.get_json()["message"] == "text not found"


def test_the_llm_is_preferred_over_the_free_providers():
    calls = []
    stub(
        llm=llm_response("halo dunia"),
        mymemory=fake_translator(result="from mymemory", counter=calls),
    )
    res = client().post("/translate", data={"text": "hello world"})
    assert res.get_json()["translated"] == "halo dunia", res.get_json()
    assert calls == [], "mymemory must not be called when the llm answers"


def test_the_trailing_sse_terminator_does_not_break_parsing():
    stub(llm=llm_response("halo dunia", trailing="data: [DONE]"))
    res = client().post("/translate", data={"text": "hello world"})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["translated"] == "halo dunia"


def test_it_falls_through_the_provider_chain():
    stub(mymemory=fake_translator(result="halo dunia"))  # llm off, google fails
    res = client().post("/translate", data={"text": "hello world"})
    assert res.get_json()["translated"] == "halo dunia", res.get_json()


def test_a_failed_provider_is_skipped_on_the_next_text():
    calls = []
    stub(
        llm=llm_response("", status=500, counter=calls),
        mymemory=fake_translator(result="halo"),
    )
    c = client()
    c.post("/translate", data={"text": "first"})
    c.post("/translate", data={"text": "second"})
    assert len(calls) == 1, calls


def test_json_body_works_like_a_form_body():
    stub(mymemory=fake_translator(result="halo dunia"))
    res = client().post("/translate", json={"text": "hello world"})
    assert res.status_code == 200, res.status_code
    assert res.get_json()["translated"] == "halo dunia"


def test_source_and_target_default_to_en_id():
    calls = []
    stub(llm=llm_response("halo", counter=calls))
    res = client().post("/translate", data={"text": "hello"})
    assert res.status_code == 200, res.get_json()
    assert app_module._language("id") == "Indonesian"


def test_identical_text_is_only_translated_once():
    calls = []
    stub(llm=llm_response("halo dunia", counter=calls))
    c = client()
    c.post("/translate", data={"text": "hello world"})
    c.post("/translate", data={"text": "hello world"})
    assert len(calls) == 1, calls


def test_every_provider_rate_limited_is_a_json_429():
    stub()
    res = client().post("/translate", data={"text": "hello world"})
    assert res.status_code == 429, res.status_code
    assert res.is_json, res.data[:80]


def test_a_failure_is_not_cached():
    calls = []
    stub(mymemory=fake_translator(error=TooManyRequests(), counter=calls, prefix="m:"))
    c = client()
    assert c.post("/translate", data={"text": "hello world"}).status_code == 429

    stub(mymemory=fake_translator(result="halo dunia", counter=calls, prefix="m:"))
    res = c.post("/translate", data={"text": "hello world"})
    assert res.status_code == 200, res.status_code
    assert calls == ["m:hello world", "m:hello world"], calls


def test_long_text_is_split_for_mymemorys_500_char_limit():
    calls = []
    stub(mymemory=fake_translator(result="potongan", counter=calls))
    res = client().post("/translate", data={"text": "word " * 400})
    assert res.status_code == 200, res.get_json()
    assert len(calls) > 1, "long text must be chunked"
    assert all(len(c) <= 500 for c in calls), [len(c) for c in calls]


def test_mymemory_padded_hyphens_are_rejoined():
    stub(mymemory=fake_translator(result="orang - orang dan Spider - Man"))
    res = client().post("/translate", data={"text": "people and Spider-Man"})
    assert res.get_json()["translated"] == "orang-orang dan Spider-Man", res.get_json()


def test_plain_language_codes_map_to_mymemory_locales():
    assert app_module._mymemory_code("id") == "id-ID"
    assert app_module._mymemory_code("en").startswith("en-")
    assert app_module._mymemory_code("en-GB") == "en-GB"


def test_the_proxy_is_handed_to_the_free_providers():
    seen = {}

    def spy(name):
        class Fake:
            def __init__(self, source=None, target=None, email=None, proxies=None):
                seen[name] = proxies

            def translate(self, text):
                if name == "google":
                    raise TooManyRequests()
                return "halo"

        return Fake

    app_module.PROXIES = {"http": "http://proxy:1", "https": "http://proxy:1"}
    stub(google=spy("google"), mymemory=spy("mymemory"))
    try:
        client().post("/translate", data={"text": "hello"})
        assert seen["mymemory"] == app_module.PROXIES, seen
    finally:
        app_module.PROXIES = None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all good")
