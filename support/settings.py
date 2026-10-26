import os
from dataclasses import dataclass
from urllib.parse import urlsplit


def local_url(value: str) -> str:
    """Разрешаем только HTTP на IPv4 loopback этого компьютера."""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.username or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query or parsed.fragment
    ):
        raise ValueError("HIKE_BASE_URL: нужен http://localhost:порт или http://127.0.0.1:порт")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Некорректный порт HIKE_BASE_URL")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    base_url: str
    timeout: float
    browser: str
    headed: bool
    driver_path: str | None
    browser_binary: str | None
    hidden_product_id: int | None

    @classmethod
    def from_env(cls):
        timeout = float(os.getenv("HIKE_TIMEOUT", "15"))
        if not 0 < timeout <= 120:
            raise ValueError("HIKE_TIMEOUT должен быть от 0 до 120 секунд (не включая 0)")
        browser = os.getenv("HIKE_BROWSER", "chrome").lower()
        if browser not in {"chrome", "edge"}:
            raise ValueError("HIKE_BROWSER: chrome или edge; браузер запускается локально")
        hidden = os.getenv("HIKE_HIDDEN_PRODUCT_ID")
        hidden_id = int(hidden) if hidden else None
        if hidden_id is not None and hidden_id < 1:
            raise ValueError("HIKE_HIDDEN_PRODUCT_ID должен быть положительным ID CAMP-HIDDEN")
        return cls(
            local_url(os.getenv("HIKE_BASE_URL", "http://127.0.0.1:18080")),
            timeout, browser, os.getenv("HIKE_HEADED", "0") == "1",
            os.getenv("HIKE_DRIVER_PATH"), os.getenv("HIKE_BROWSER_BINARY"), hidden_id,
        )
