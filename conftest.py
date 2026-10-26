import hashlib
import shutil
from html import escape
from pathlib import Path

import pytest
import pytest_html
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService

from support.api import ApiClient, expect_status, new_account
from support.settings import Settings


@pytest.fixture(scope="session")
def settings():
    return Settings.from_env()


@pytest.fixture
def public_api(settings):
    api = ApiClient(settings)
    yield api
    api.close()


@pytest.fixture
def products(public_api):
    # Каталог демо содержит 32 активных товара. Одна страница исключает API-10.
    page = public_api.get("/products/", page_size=50, ordering="name")
    assert 0 < page["count"] <= 50, "Предусловие: требуется каталог hike-demo-v1 (не больше 50 товаров)"
    assert len(page["results"]) == page["count"], "Предусловие: каталог загружен не полностью"
    return {product["sku"]: product for product in page["results"]}


@pytest.fixture
def account_factory(settings):
    accounts = []

    def create():
        account = new_account(settings)
        accounts.append(account)
        return account

    yield create
    errors = []
    for account in reversed(accounts):
        try:
            # Только новые учётные записи этого теста. Демо-покупатели не меняются.
            orders = account.api.get("/orders/", page_size=50)["results"]
            for order in orders:
                if order["status"] == "new":
                    account.api.cancel(order["id"])
            for item in account.api.cart()["items"]:
                expect_status(account.api.request("DELETE", f"/cart/items/{item['id']}/"), 204)
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            account.api.close()
    if errors:
        pytest.fail("Не завершена очистка тестовых корзин/новых заказов: " + "; ".join(errors))


@pytest.fixture
def account(account_factory):
    return account_factory()


@pytest.fixture
def api(account):
    return account.api


@pytest.fixture
def hidden_product_id(settings):
    if settings.hidden_product_id is None:
        pytest.fail(
            "Предусловие API-04: задайте HIKE_HIDDEN_PRODUCT_ID из локальной БД "
            "для SKU CAMP-HIDDEN (инструкция в README). ID не угадывается."
        )
    return settings.hidden_product_id


# Наблюдаем только завершение fetch. Тела запросов/ответов и данные приложения не меняем.
FETCH_OBSERVER = """
(() => {
  const original = window.fetch;
  window.__hikePending = 0;
  window.fetch = async (...args) => {
    window.__hikePending++;
    try { return await original(...args); }
    finally { window.__hikePending--; }
  };
})();
"""


@pytest.fixture
def driver(settings, monkeypatch):
    binary_name = "chromedriver" if settings.browser == "chrome" else "msedgedriver"
    driver_path = settings.driver_path or shutil.which(binary_name)
    if not driver_path or not Path(driver_path).is_file():
        pytest.fail(
            f"Нужен локальный {binary_name}: задайте HIKE_DRIVER_PATH или добавьте его в PATH. "
            "Автоматическая загрузка драйвера и удалённый Grid отключены."
        )
    options = webdriver.ChromeOptions() if settings.browser == "chrome" else webdriver.EdgeOptions()
    # В том числе соединение Python -> локальный WebDriver не должно идти через прокси.
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1")
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    if not settings.headed:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--no-proxy-server")
    options.add_argument("--disable-background-networking")
    if settings.browser_binary:
        options.binary_location = settings.browser_binary
    service = ChromeService(driver_path) if settings.browser == "chrome" else EdgeService(driver_path)
    browser_class = webdriver.Chrome if settings.browser == "chrome" else webdriver.Edge
    browser = browser_class(service=service, options=options)
    try:
        browser.set_page_load_timeout(settings.timeout)
        browser.set_script_timeout(settings.timeout)
        browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": FETCH_OBSERVER})
        yield browser
    finally:
        browser.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    marker = item.get_closest_marker("defect")
    report.defect_id = marker.args[0] if marker else "SMOKE"
    report.user_properties.append(("defect", report.defect_id))
    if not report.failed or report.when not in {"setup", "call"}:
        return
    browser = item.funcargs.get("driver")
    if browser is None:
        return
    try:
        screenshot = browser.get_screenshot_as_base64()
        extras = getattr(report, "extras", [])
        extras.append(pytest_html.extras.png(screenshot, name="Экран при падении"))
        extras.append(pytest_html.extras.text(browser.current_url, name="Локальный URL"))
        report.extras = extras
        directory = Path(__file__).parent / "reports" / "screenshots"
        directory.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(item.nodeid.encode()).hexdigest()[:16]
        browser.save_screenshot(str(directory / f"{name}-{report.when}.png"))
    except (WebDriverException, OSError) as error:
        report.sections.append(("Screenshot", f"Не удалось сохранить: {type(error).__name__}"))


def pytest_html_report_title(report):
    report.title = "Поход — локальные API и UI автотесты"


def pytest_html_results_table_header(cells):
    cells.insert(1, "<th>Дефект</th>")


def pytest_html_results_table_row(report, cells):
    cells.insert(1, f"<td>{escape(getattr(report, 'defect_id', '—'))}</td>")
