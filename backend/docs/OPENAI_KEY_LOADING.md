# OPENAI_API_KEY loading (trace and fix)

## End-to-end trace

1. **backend/app/core/config.py**

   - `_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent` → always `backend/` regardless of CWD.
   - `_ENV_FILE = _BACKEND_DIR / ".env"` → `backend/.env`.
   - `load_dotenv(_ENV_FILE, override=False)` is **always** called (no `exists()` guard) so `backend/.env` is loaded into `os.environ` when present.
   - `Settings(BaseSettings)` with `env_file = str(_ENV_FILE)` so Pydantic also reads from `backend/.env`.
   - `settings.openai_api_key` is set from that file (or from `os.environ` after dotenv).

2. **backend/app/llm/provider.py**

   - `get_openai_api_key()` returns `settings.openai_api_key or os.getenv("OPENAI_API_KEY")`, then:
     - strip, take first line if `\n` present, take first token if space present;
     - return `None` only for empty, literal placeholders (`your-key-here`), or `sk-` with len < 30.
   - **No truncation**: valid keys of any length (e.g. 164 chars) are passed through.
   - `generate_llm_answer()` uses that key to construct `OpenAI(api_key=api_key)` and call the API.

3. **backend/app/main.py**
   - Startup logs: `env_file`, `exists`, `key_present`, `key_len`, `stub_reason`, and "Backend running in LLM mode" vs "stub mode".

## Root cause of regression

- **60-char truncation** in `get_openai_api_key()` was cutting valid keys (OpenAI keys can be 100+ chars). Truncated key → 401 → stub and "authentication failed".
- Truncation has been **removed**. Only normalization (first line, first token) is applied; length is not limited.

## Invariant

If `backend/.env` contains a valid `OPENAI_API_KEY`:

- Backend starts in **LLM mode** (startup log: "Backend running in LLM mode").
- `POST /verify` returns `llm_used: true`, `llm_fallback_reason: null`, and a numeric `generated_answer`.

Stub mode is used only when the key is missing, placeholder, or invalid (e.g. 401 from API).

## Diagnostics (no secrets)

- Startup: `OPENAI_API_KEY env_file=... exists=... key_present=... key_len=... stub_reason=...`
- Per request: `OPENAI_API_KEY set=... len=... stub_reason=...` and "OpenAI client constructed (LLM mode)" or "LLM stub selected: ..."

If you see `key_present=False` or `stub_reason=key_missing`: ensure `backend/.env` exists and contains a single line `OPENAI_API_KEY=sk-...` (no quotes, no trailing space). If you see 401 after "OpenAI client constructed", the key in `.env` is invalid or revoked; create a new key at https://platform.openai.com/api-keys.
