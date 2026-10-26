import re
from decimal import Decimal
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


def money(text: str) -> Decimal:
    if "Бесплатно" in text:
        return Decimal("0.00")
    return Decimal(re.sub(r"[^0-9,.\-]", "", text).replace(",", "."))


class Page:
    def __init__(self, driver, settings):
        self.driver = driver
        self.settings = settings
        self.wait = WebDriverWait(driver, settings.timeout, ignored_exceptions=(StaleElementReferenceException,))

    def open(self, path):
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise ValueError("Разрешён только путь локального приложения")
        self.driver.get(self.settings.base_url + path)
        self.settled()
        return self

    def settled(self):
        # Два последовательных спокойных опроса: fetch завершён и React убрал Loading.
        quiet_since = None

        def ready(driver):
            nonlocal quiet_since
            quiet = driver.execute_script(
                "return document.readyState === 'complete' && window.__hikePending === 0"
            ) and not any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, ".loading"))
            if not quiet:
                quiet_since = None
                return False
            if quiet_since is None:
                quiet_since = monotonic()
            return monotonic() - quiet_since >= 0.25

        self.wait.until(ready, "Страница не завершила локальные HTTP-запросы/отрисовку")

    def element(self, css):
        return self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, css)))

    def click(self, css):
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css))).click()
        self.settled()

    def fill(self, css, value):
        element = self.element(css)
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)
        element.send_keys(str(value))

    def text(self, css):
        return self.element(css).text

    def route(self, path):
        self.wait.until(lambda d: urlsplit(d.current_url).path == path, f"Не открыт маршрут {path}")
        self.settled()

    def refresh(self):
        self.driver.refresh()
        self.settled()

    def query(self):
        return parse_qs(urlsplit(self.driver.current_url).query)

    def menu(self, path):
        self.click(f'header a[href="{path}"]')
        self.route(path)

    def toast(self, text):
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".toast"), text))


class AuthPage(Page):
    def credentials(self, account):
        self.fill('.auth-form input[type="email"]', account.email)
        self.fill('.auth-form input[type="password"]', account.password)

    def login(self, account, navigate=True):
        if navigate:
            self.open("/login")
        self.credentials(account)
        self.click(".auth-form button.button")
        self.route("/account")
        self.element("header .logout")

    def logout(self):
        self.click("header .logout")
        self.route("/login")


class CatalogPage(Page):
    def load(self, **params):
        self.open("/?" + urlencode(params) if params else "/")
        self.element(".filter-panel")

    def next_page(self, expected):
        self.click(".pagination button:last-child")
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".pagination span"), f"Страница {expected}"))

    def category(self, category_id):
        Select(self.element(".filter-panel select")).select_by_value(str(category_id))

    def apply(self):
        self.click(".filter-panel button.button")

    def reset(self):
        self.click(".filter-panel button.text-button")

    def product_ids(self):
        self.settled()
        return [int(urlsplit(e.get_attribute("href")).path.rsplit("/", 1)[-1])
                for e in self.driver.find_elements(By.CSS_SELECTOR, ".product-card .product-name")]

    def favorite(self, product_id):
        locator = (By.XPATH, f'//article[contains(@class,"product-card")][.//a[@href="/products/{product_id}"]]//button[contains(@class,"heart")]')
        self.wait.until(EC.element_to_be_clickable(locator)).click()
        self.settled()
        self.wait.until(lambda d: d.find_element(*locator).get_attribute("aria-pressed") == "true")


class ProductPage(Page):
    def load(self, product_id):
        self.open(f"/products/{product_id}")
        self.element(".product-detail")

    def add(self):
        self.click(".buy-row button")
        self.toast("Товар добавлен в корзину")

    def price(self):
        return money(self.text(".detail-price"))


class ProfilePage(Page):
    name_field = '.account-grid form input:not([readonly]):not([type="tel"])'

    def save_name(self, value):
        self.fill(self.name_field, value)
        self.click(".account-grid form button")
        self.toast("Профиль сохранён")

    def name(self):
        return self.element(self.name_field).get_attribute("value")


class CartPage(Page):
    def load(self):
        self.open("/cart")

    def quantity(self, delta, expected):
        label = "Увеличить количество" if delta > 0 else "Уменьшить количество"
        self.click(f'.quantity button[aria-label="{label}"]')
        self.wait.until(lambda _: self.element(".quantity input").get_attribute("value") == str(expected))

    def total(self):
        return money(self.text(".summary .grand-total strong:last-child"))

    def contents(self):
        result = {}
        for row in self.driver.find_elements(By.CSS_SELECTOR, ".cart-row"):
            href = row.find_element(By.CSS_SELECTOR, ".cart-item-info a").get_attribute("href")
            product_id = int(urlsplit(href).path.rsplit("/", 1)[-1])
            result[product_id] = int(row.find_element(By.CSS_SELECTOR, ".quantity input").get_attribute("value"))
        return result


class CheckoutPage(Page):
    def load(self):
        self.open("/checkout")
        self.element(".delivery-options")
        self.element(".summary .totals")

    def delivery(self, method):
        self.click(f'.delivery-options input[value="{method}"]')
        self.element(".summary .totals")

    def address(self, city):
        locator = (By.XPATH, f'//label[contains(@class,"address-option")][contains(.,"{city}")]//input')
        self.wait.until(EC.element_to_be_clickable(locator)).click()
        self.settled()
        assert self.driver.find_element(*locator).is_selected()

    def total(self):
        return money(self.text(".summary .grand-total strong:last-child"))

    def shipping(self):
        return money(self.text(".summary .totals > div:nth-child(3) > span:last-child"))

    def confirm(self):
        self.click(".summary > button.button")
        self.wait.until(lambda d: re.fullmatch(r"/orders/\d+", urlsplit(d.current_url).path))
        self.settled()
        return int(urlsplit(self.driver.current_url).path.rsplit("/", 1)[-1])


class OrdersPage(Page):
    def ids(self):
        self.settled()
        return {int(urlsplit(e.get_attribute("href")).path.rsplit("/", 1)[-1])
                for e in self.driver.find_elements(By.CSS_SELECTOR, ".order-number")}

    def repeat(self, order_id):
        self.open(f"/orders/{order_id}")
        self.click(".summary > button.button")
        self.route("/cart")

    def pay(self):
        self.click(".summary > button.button")
        self.toast("Учебная оплата завершена")
        self.element(".page-title .status.paid")
