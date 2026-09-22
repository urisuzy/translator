# Translator

`POST /translate` with `text`, and optionally `source` (default `en`) and
`target` (default `id`). Form or JSON body, both work.

```
curl -X POST http://localhost:5000/translate -d 'text=hello world'
{"text":"hello world","translated":"halo dunia"}
```

Errors are always JSON: `400` (no text), `429` (every provider rate-limited),
`502` (anything else).

## Providers

Tried in order, first success wins:

1. **LLM** — any OpenAI-compatible `/chat/completions` endpoint. Best quality,
   no per-IP quota, no length limit. Skipped entirely when unconfigured.
2. **MyMemory** — free, but quota is counted per exit IP and it rejects text
   over 500 chars, so longer synopses are split and rejoined.
3. **Google** — free, and currently answers `429` to everything, including from
   clean datacenter IPs. Kept because it costs nothing if it ever comes back.

A provider that fails moves to the back of the queue for `PROVIDER_COOLDOWN`
seconds, so an outage costs one failed round trip, not one per text. Every
translation is cached, and outgoing calls are spaced out.

## Config

Lives in `.env` (see `.env.example`; never committed).

| Variable | Why |
| --- | --- |
| `LLM_BASE_URL` | e.g. `https://host/v1`. Empty disables the LLM provider. |
| `LLM_API_KEY` | Bearer token for that endpoint. |
| `LLM_MODEL` | Default `translate-flash`. |
| `LLM_TIMEOUT` | Seconds, default 60. |
| `TRANSLATE_PROXY` | `http://user:pass@host:port`, applied to the free providers only. Lifts MyMemory's per-IP quota. Does **not** unblock Google. |
| `MYMEMORY_EMAIL` | Raises MyMemory's quota from 5k to 50k chars/day. |
| `PROVIDER_COOLDOWN` | Seconds a failed provider is deprioritised, default 900. |
| `TRANSLATE_MIN_INTERVAL` | Seconds between outgoing calls, default 0.25. |

Run: `docker compose up -d`. Tests: `python test_app.py`.

Built with flask, docker, and https://github.com/nidhaloff/deep-translator
