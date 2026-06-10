# src/tts_service.py
"""Multi-provider TTS service — dispatches to local Kokoro, host voice-api,
OpenAI-compatible API, ElevenLabs, or browser."""

import io
import os
import wave
import logging
import hashlib
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _safe_speed(value, default: float = 1.0) -> float:
    """Parse the stored tts_speed defensively. The settings layer tolerates
    corrupt/agent-written config, so a non-numeric or empty value (e.g. an agent
    setting "speech speed" = "fast", or a hand-edited settings.json) must not
    crash synthesis or the stats endpoint with a ValueError."""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return default
    return speed if speed > 0 else default


class TTSService:
    """Multi-provider TTS service.

    Reads provider config from data/settings.json on each call.
    Providers:
      "disabled"        — no TTS
      "browser"         — client-side Web Speech API (no server synthesis)
      "local"           — Kokoro-82M on GPU
      "voice_api"       — host voice-api Kokoro at configurable URL
      "elevenlabs"      — ElevenLabs API (fallback)
      "endpoint:<id>"   — OpenAI-compatible /audio/speech via ModelEndpoint
    """

    def __init__(self, cache_dir: str = "data/tts_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._kokoro = None  # lazy-init

    # ── Settings ──

    def _load_settings(self) -> dict:
        from src.settings import load_settings
        saved = load_settings()
        return {
            "tts_enabled": saved.get("tts_enabled", True),
            "tts_provider": saved.get("tts_provider", "disabled"),
            "tts_model": saved.get("tts_model", "tts-1"),
            "tts_voice": saved.get("tts_voice", "alloy"),
            "tts_speed": saved.get("tts_speed", "1"),
            "tts_voice_api_url": saved.get("tts_voice_api_url", ""),
            "tts_voice_api_token": saved.get("tts_voice_api_token", ""),
            "tts_elevenlabs_api_key": saved.get("tts_elevenlabs_api_key", ""),
            "tts_elevenlabs_voice_id": saved.get("tts_elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM"),
            "tts_elevenlabs_model": saved.get("tts_elevenlabs_model", "eleven_multilingual_v2"),
            "tts_fallback_provider": saved.get("tts_fallback_provider", ""),
        }

    @property
    def available(self) -> bool:
        settings = self._load_settings()
        if settings.get("tts_enabled") is False:
            return False
        provider = settings["tts_provider"]
        if provider == "disabled":
            return False
        if provider == "browser":
            return True  # handled client-side
        if provider == "local":
            kokoro = self._get_kokoro()
            return kokoro is not None and kokoro.available
        if provider == "voice_api":
            return bool(settings.get("tts_voice_api_url"))
        if provider == "elevenlabs":
            return bool(settings.get("tts_elevenlabs_api_key"))
        if provider.startswith("endpoint:"):
            return True  # assume reachable; errors surface at synthesis time
        return False

    # ── Cache ──

    def _cache_key(self, text: str, provider: str, model: str, voice: str, speed: float = 1.0) -> str:
        raw = f"{provider}|{model}|{voice}|{speed}|{text}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[bytes]:
        for ext in (".mp3", ".wav"):
            path = self.cache_dir / f"{key}{ext}"
            if path.exists():
                return path.read_bytes()
        return None

    def _put_cache(self, key: str, data: bytes):
        ext = ".mp3" if (len(data) >= 3 and (data[:3] == b'ID3' or (data[0] == 0xff and (data[1] & 0xe0) == 0xe0))) else ".wav"
        (self.cache_dir / f"{key}{ext}").write_bytes(data)

    def clear_cache(self):
        count = 0
        for f in self.cache_dir.glob("*.*"):
            f.unlink()
            count += 1
        logger.info(f"Cleared {count} cached TTS files")

    # ── Kokoro (local) ──

    def _get_kokoro(self):
        if self._kokoro is None:
            self._kokoro = _KokoroPipeline()
        return self._kokoro

    # ── API endpoint (OpenAI-compatible) ──

    def _synthesize_api(self, text: str, endpoint_id: str, model: str, voice: str, speed: float = 1.0) -> Optional[bytes]:
        from src.database import SessionLocal, ModelEndpoint

        db = SessionLocal()
        try:
            ep = db.query(ModelEndpoint).filter(ModelEndpoint.id == endpoint_id).first()
            if not ep:
                logger.error(f"TTS endpoint {endpoint_id} not found")
                return None
            base_url = ep.base_url.rstrip("/")
            api_key = ep.api_key
        finally:
            db.close()

        url = base_url + "/audio/speech"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
            "speed": speed,
        }

        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            logger.info(f"API TTS: {len(r.content)} bytes from {base_url}")
            return r.content
        except Exception as e:
            logger.error(f"API TTS synthesis failed: {e}")
            return None

    # ── Host voice-api (Kokoro via Sovi voice-api service) ──

    def _synthesize_voice_api(self, text: str, settings: dict) -> Optional[bytes]:
        base_url = settings.get("tts_voice_api_url", "").rstrip("/")
        token = settings.get("tts_voice_api_token", "")
        if not base_url:
            logger.error("voice_api provider: tts_voice_api_url not configured")
            return None

        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            r = httpx.post(
                f"{base_url}/api/tts",
                json={"text": text},
                headers=headers,
                timeout=60,
            )
            r.raise_for_status()
            result = r.json()
            audio_url = result.get("audio_url", "")
            if not audio_url:
                logger.error("voice_api: no audio_url in response")
                return None

            # Fetch the audio file (no auth needed — capability URL)
            audio_r = httpx.get(f"{base_url}{audio_url}", timeout=30)
            audio_r.raise_for_status()
            logger.info(f"voice_api TTS: {len(audio_r.content)} bytes from {base_url}")
            return audio_r.content
        except Exception as e:
            logger.error(f"voice_api TTS synthesis failed: {e}")
            return None

    # ── ElevenLabs ──

    def _synthesize_elevenlabs(self, text: str, settings: dict) -> Optional[bytes]:
        api_key = settings.get("tts_elevenlabs_api_key", "")
        voice_id = settings.get("tts_elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
        model_id = settings.get("tts_elevenlabs_model", "eleven_multilingual_v2")
        if not api_key:
            logger.error("elevenlabs provider: tts_elevenlabs_api_key not configured")
            return None

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": api_key,
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }

        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=60)
            r.raise_for_status()
            logger.info(f"ElevenLabs TTS: {len(r.content)} bytes")
            return r.content
        except Exception as e:
            logger.error(f"ElevenLabs TTS synthesis failed: {e}")
            return None

    # ── Public interface ──

    def _do_synthesize(self, text: str, provider: str, settings: dict) -> Optional[bytes]:
        """Dispatch synthesis to the given provider. Returns audio bytes or None."""
        model = settings["tts_model"]
        voice = settings["tts_voice"]
        speed = _safe_speed(settings.get("tts_speed", "1"))

        if provider == "local":
            kokoro = self._get_kokoro()
            if kokoro and kokoro.available:
                return kokoro.synthesize_raw(text, voice)
            logger.warning("Kokoro TTS not available")
            return None
        elif provider == "voice_api":
            return self._synthesize_voice_api(text, settings)
        elif provider == "elevenlabs":
            return self._synthesize_elevenlabs(text, settings)
        elif provider.startswith("endpoint:"):
            endpoint_id = provider.split(":", 1)[1]
            return self._synthesize_api(text, endpoint_id, model, voice, speed)
        else:
            logger.error(f"Unknown TTS provider: {provider}")
            return None

    def synthesize(self, text: str, use_cache: bool = True) -> Optional[bytes]:
        settings = self._load_settings()
        if settings.get("tts_enabled") is False:
            return None
        provider = settings["tts_provider"]
        model = settings["tts_model"]
        voice = settings["tts_voice"]
        speed = _safe_speed(settings.get("tts_speed", "1"))

        if provider in ("disabled", "browser"):
            return None

        if len(text) > 5000:
            text = text[:5000]

        if use_cache:
            key = self._cache_key(text, provider, model, voice, speed)
            cached = self._get_cached(key)
            if cached:
                logger.info(f"TTS cache hit ({len(text)} chars)")
                return cached

        audio_data = self._do_synthesize(text, provider, settings)

        # Fallback: if primary failed and a fallback provider is configured, try it
        if audio_data is None:
            fallback = settings.get("tts_fallback_provider", "")
            if fallback and fallback != provider and fallback != "disabled":
                logger.info(f"TTS primary ({provider}) failed, trying fallback ({fallback})")
                audio_data = self._do_synthesize(text, fallback, settings)

        if audio_data and use_cache:
            key = self._cache_key(text, provider, model, voice, speed)
            self._put_cache(key, audio_data)

        return audio_data

    def synthesize_to_base64(self, text: str) -> Optional[str]:
        import base64
        audio = self.synthesize(text)
        if audio:
            return base64.b64encode(audio).decode("utf-8")
        return None

    def set_voice(self, voice: str):
        """Legacy no-op — voice is now managed via admin settings."""

    def get_stats(self) -> Dict[str, Any]:
        settings = self._load_settings()
        provider = settings["tts_provider"]
        tts_enabled = settings.get("tts_enabled", True)

        cache_files = list(self.cache_dir.glob("*.wav")) + list(self.cache_dir.glob("*.mp3"))
        cache_size = sum(f.stat().st_size for f in cache_files)

        is_available = self.available and tts_enabled
        stats = {
            "available": is_available,
            "ready": is_available,
            "provider": provider,
            "model": settings["tts_model"],
            "voice": settings["tts_voice"],
            "speed": _safe_speed(settings.get("tts_speed", "1")),
            "cache_entries": len(cache_files),
            "cache_size_mb": round(cache_size / (1024 * 1024), 2),
        }

        if provider == "local":
            kokoro = self._get_kokoro()
            stats["model"] = "Kokoro-82M (ONNX)" if (kokoro and kokoro.available) else "Kokoro (not loaded)"
        elif provider == "browser":
            stats["model"] = "Browser (Web Speech API)"
        elif provider == "voice_api":
            stats["model"] = "Kokoro (host voice-api)"
            stats["voice_api_url"] = settings.get("tts_voice_api_url", "")
        elif provider == "elevenlabs":
            stats["model"] = "ElevenLabs"
            stats["voice_id"] = settings.get("tts_elevenlabs_voice_id", "")
        elif provider.startswith("endpoint:"):
            stats["endpoint_id"] = provider.split(":", 1)[1]

        fallback = settings.get("tts_fallback_provider", "")
        if fallback:
            stats["fallback_provider"] = fallback

        return stats


class _KokoroPipeline:
    """Encapsulates the Kokoro-82M ONNX pipeline (CPU, no CUDA required).

    Uses the kokoro-onnx package with model files bind-mounted from host
    at /app/kokoro-models/. Falls back to standard HuggingFace cache paths.
    """

    # Search paths for model + voices, in priority order
    _MODEL_SEARCH = [
        "/app/kokoro-models/kokoro-v0_19.onnx",
        "/app/kokoro-models/kokoro-v1.0.onnx",
        "/var/lib/kokoro/kokoro-v0_19.onnx",
    ]
    _VOICES_SEARCH = [
        "/app/kokoro-models/voices-v1.0.bin",
        "/var/lib/kokoro/voices-v1.0.bin",
    ]

    def __init__(self):
        self.kokoro = None
        self.available = False
        self._init()

    def _find_file(self, paths: list) -> Optional[str]:
        for p in paths:
            if Path(p).exists():
                return p
        return None

    def _init(self):
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            logger.warning("kokoro-onnx not installed. Install with: pip install kokoro-onnx")
            return

        model_path = self._find_file(self._MODEL_SEARCH)
        voices_path = self._find_file(self._VOICES_SEARCH)

        if not model_path or not voices_path:
            logger.warning(
                f"Kokoro model files not found. Searched: model={self._MODEL_SEARCH}, "
                f"voices={self._VOICES_SEARCH}"
            )
            return

        try:
            self.kokoro = Kokoro(model_path, voices_path)
            self.available = True
            logger.info(f"Kokoro-82M ONNX TTS loaded from {model_path}")
        except Exception as e:
            logger.error(f"Kokoro ONNX init failed: {e}", exc_info=True)

    def synthesize_raw(self, text: str, voice: str = "af_heart") -> Optional[bytes]:
        if not self.available or not self.kokoro:
            return None
        try:
            import soundfile as sf

            samples, sample_rate = self.kokoro.create(
                text, voice=voice, speed=1.0, lang="en-us"
            )
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
            logger.info(f"Kokoro ONNX: synthesized {len(text)} chars → {buf.tell()} bytes WAV")
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Kokoro ONNX synthesis failed: {e}", exc_info=True)
            return None


# Module-level singleton
_tts_service = None

def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
