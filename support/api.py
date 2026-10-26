from dataclasses import dataclass
from secrets import choice
from uuid import uuid4

import requests

from support.settings import Settings


def expect_status(response: requests.Response, expected: int):
    # Не включаем тела запросов, cookie и пароли в диагностику.
    detail = ""
    if response.status_code != expected:
        try:
            error = response.json()
            detail = f" code={error.get('code')} fields={error.get('field_errors')}"
        except (ValueError, AttributeError):
            detail = " (ответ не является JSON-объектом ошибки)"
    assert response.status_code == expected, (
        f"{response.request.method} {response.request.path_url}: "
        f"ожидался HTTP {expected}, получен {response.status_code};"
        f" request_id={response.headers.get('X-Request-ID', '')}{detail}"
    )
    return response


class ApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.trust_env = False  # Не передавать localhost через прокси окружения.

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise ValueError("API принимает только относительный путь текущего локального стенда")
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            csrf = expect_status(self.request("GET", "/auth/csrf/"), 200).json()
            headers["X-CSRFToken"] = csrf["csrf_token"]
            headers["Origin"] = self.settings.base_url
        return self.session.request(
            method, self.settings.base_url + "/api/v1" + path,
            headers=headers, timeout=self.settings.timeout, allow_redirects=False, **kwargs,
        )

    def get(self, path: str, **params):
        return expect_status(self.request("GET", path, params=params), 200).json()

    def post(self, path: str, data: dict, status: int = 201):
        return expect_status(self.request("POST", path, json=data), status).json()

    def cart(self):
        return self.get("/cart/")

    def add(self, product: dict, quantity: int = 1):
        current = self.get(f"/products/{product['id']}/")
        assert current["stock"] >= quantity, f"Предусловие: недостаточно остатка {product['sku']}"
        return self.post("/cart/items/", {"product_id": product["id"], "quantity": quantity})

    def checkout(self, **overrides):
        return self.request(
            "POST", "/orders/", json={"delivery_method": "pickup", "promo_code": "", **overrides},
            headers={"Idempotency-Key": str(uuid4())},
        )

    def order(self, **overrides):
        return expect_status(self.checkout(**overrides), 201).json()

    def cancel(self, order_id: int):
        return self.post(f"/orders/{order_id}/cancel/", {}, status=200)

    def pay(self, order_id: int):
        return self.post(f"/orders/{order_id}/pay-demo/", {}, status=200)

    def address(self, city="Москва", street="Тестовая", default=False):
        return self.post("/addresses/", {
            "recipient": "Покупатель Автотест", "phone": "+79990000003",
            "city": city, "street": street, "house": "12", "apartment": "5",
            "postal_code": "123456", "is_default": default,
        })

    def close(self):
        self.session.close()


@dataclass
class Account:
    api: ApiClient
    email: str
    password: str
    profile: dict


def new_account(settings: Settings) -> Account:
    api = ApiClient(settings)
    email = f"autotest-{uuid4().hex}@example.test"
    # Буквы вне hex-алфавита исключают сходство со случайной частью email.
    password = "Hike!" + "".join(choice("ghijklmnopqrstuvwxyz") for _ in range(32)) + "9"
    try:
        profile = api.post("/auth/register/", {
            "email": email, "password": password, "full_name": "Покупатель Автотест",
        })
    except BaseException:
        api.close()
        raise
    return Account(api, email, password, profile)
