from decimal import Decimal
from uuid import uuid4

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from support.pages import AuthPage, CartPage, CatalogPage, CheckoutPage, OrdersPage, ProductPage, ProfilePage

pytestmark = pytest.mark.ui


@pytest.fixture
def logged_in(driver, settings, account):
    AuthPage(driver, settings).login(account)
    return account


@pytest.mark.defect("UI-01")
def test_ui_01_registration_checks_password_confirmation(driver, settings):
    page = AuthPage(driver, settings)
    page.open("/register")
    page.fill('.auth-form input[autocomplete="name"]', "Новый Покупатель")
    page.fill('.auth-form input[type="email"]', f"autotest-ui01-{uuid4().hex}@example.test")
    passwords = driver.find_elements(By.CSS_SELECTOR, '.auth-form input[type="password"]')
    passwords[0].send_keys(f"Hike!{uuid4().hex}9")
    passwords[1].send_keys("Another-Password!2026")
    page.click(".auth-form button.button")
    assert driver.find_elements(By.CSS_SELECTOR, '.auth-form [role="alert"]'), (
        "Регистрация должна показать несовпадение паролей"
    )
    assert "Пароли не совпадают" in page.text('.auth-form [role="alert"]')
    page.route("/register")
    assert not driver.find_elements(By.CSS_SELECTOR, "header .logout")


@pytest.mark.defect("UI-02")
def test_ui_02_profile_name_survives_reload(driver, settings, logged_in):
    page = ProfilePage(driver, settings)
    name = "Сохранённое Имя"
    page.save_name(name)
    server_name = logged_in.api.get("/auth/me/")["full_name"]
    page.refresh()
    assert (page.name(), server_name) == (name, name), "Изменение имени должно сохраняться на сервере"


@pytest.mark.defect("UI-03")
def test_ui_03_account_switch_clears_orders_cache(driver, settings, account_factory, products):
    first, second = account_factory(), account_factory()
    for account in (first, second):
        account.api.add(products["CAMP-MUG"])
        account.api.order()
    auth = AuthPage(driver, settings)
    orders = OrdersPage(driver, settings)
    auth.login(first)
    orders.menu("/orders")
    first_ids = {o["id"] for o in first.api.get("/orders/")["results"]}
    assert orders.ids() == first_ids
    auth.logout()
    # Вся смена аккаунта идёт через SPA в той же вкладке: get/refresh сбросили бы дефектный кеш.
    auth.login(second, navigate=False)
    orders.menu("/orders")
    second_ids = {o["id"] for o in second.api.get("/orders/")["results"]}
    assert second_ids and first_ids.isdisjoint(second_ids)
    assert orders.ids() == second_ids, "После смены аккаунта показаны заказы другого покупателя"


@pytest.mark.defect("UI-04")
def test_ui_04_catalog_favorite_survives_reload(driver, settings, logged_in, products):
    product = products["CAMP-MUG"]
    api = logged_in.api
    assert api.get("/favorites/")["count"] == 0
    page = CatalogPage(driver, settings)
    page.load(search=product["name"])
    page.favorite(product["id"])
    page.refresh()
    page.menu("/favorites")
    visible = page.product_ids()
    stored = {p["id"] for p in api.get("/favorites/")["results"]}
    assert product["id"] in visible and product["id"] in stored, "Избранное из каталога не сохранилось"


@pytest.mark.defect("UI-05")
def test_ui_05_filter_resets_catalog_to_first_page(driver, settings, products):
    categories = {}
    for product in products.values():
        categories.setdefault(product["category"]["id"], []).append(product["id"])
    small = next((key for key, ids in categories.items() if 0 < len(ids) <= 12), None)
    assert small is not None and len(products) > 24, "Предусловие: 3 страницы и маленькая категория"
    page = CatalogPage(driver, settings)
    page.load()
    page.next_page(2)
    page.next_page(3)
    page.category(small)
    page.apply()
    assert page.query().get("page", ["1"]) == ["1"], "Новый фильтр должен сбросить номер страницы"
    assert set(page.product_ids()) == set(categories[small])


@pytest.mark.defect("UI-06")
def test_ui_06_reset_removes_price_from_url_and_results(driver, settings, products):
    assert any(Decimal(p["price"]) > 1000 for p in products.values())
    page = CatalogPage(driver, settings)
    page.load()
    page.fill('input[aria-label="Максимальная цена"]', "1000")
    page.apply()
    assert page.query()["price_max"] == ["1000"]
    page.reset()
    assert page.element('input[aria-label="Максимальная цена"]').get_attribute("value") == ""
    assert not page.query(), "Сброс должен удалять все параметры каталога"
    assert page.text("#catalog > .page-title > .muted") == f"{len(products)} товаров"


@pytest.mark.defect("UI-07")
def test_ui_07_decreasing_quantity_updates_cart_total(driver, settings, logged_in, products):
    product = products["CAMP-MUG"]
    assert product["stock"] >= 2, "Предусловие: нужно не меньше двух кружек"
    logged_in.api.add(product)
    page = CartPage(driver, settings)
    page.load()
    page.quantity(1, 2)
    assert page.total() == Decimal(product["price"]) * 2
    page.quantity(-1, 1)
    stored = logged_in.api.cart()
    assert stored["items"][0]["quantity"] == 1
    assert Decimal(stored["total_amount"]) == Decimal(product["price"])
    assert page.total() == Decimal(stored["total_amount"]), "Итог UI остался от предыдущего количества"


@pytest.mark.defect("UI-08")
def test_ui_08_product_price_preserves_kopecks(driver, settings, products):
    product = products["CAMP-MUG"]
    assert product["price"] == "199.90", "Предусловие: товар с копейками из демо"
    page = ProductPage(driver, settings)
    page.load(product["id"])
    assert page.price() == Decimal(product["price"])


@pytest.mark.defect("UI-09")
def test_ui_09_checkout_sends_selected_address(driver, settings, logged_in, products):
    api = logged_in.api
    first = api.address(default=True)
    second = api.address(city="Тула", street="Походная")
    assert first["id"] != second["id"]
    api.add(products["CAMP-MUG"])
    page = CheckoutPage(driver, settings)
    page.load()
    page.delivery("courier")
    page.address("Тула")
    order_id = page.confirm()
    saved = api.get(f"/orders/{order_id}/")
    expected = {key: second[key] for key in (
        "recipient", "phone", "city", "street", "house", "apartment", "postal_code",
    )}
    assert saved["address"] == expected, "Заказ должен содержать выбранный второй адрес"
    assert "Тула, Походная" in page.text(".checkout-steps > section:nth-child(2)")


@pytest.mark.defect("UI-10")
def test_ui_10_pickup_removes_courier_shipping(driver, settings, logged_in, products):
    api = logged_in.api
    api.address()
    product = products["CAMP-MUG"]
    api.add(product)
    page = CheckoutPage(driver, settings)
    page.load()
    page.delivery("courier")
    assert page.shipping() == Decimal("300.00")
    assert page.total() == Decimal(product["price"]) + 300
    page.delivery("pickup")
    quote = api.post("/checkout/quote/", {"delivery_method": "pickup"}, status=200)
    assert quote["shipping_amount"] == "0.00"
    assert (page.shipping(), page.total()) == (Decimal("0.00"), Decimal(quote["total_amount"]))


@pytest.mark.defect("UI-11")
def test_ui_11_repeat_order_adds_all_items(driver, settings, logged_in, products):
    api = logged_in.api
    api.add(products["CAMP-MUG"], quantity=2)
    api.add(products["CAMP-PRICE-120"])
    original = api.pay(api.order()["id"])
    assert len(original["items"]) == 2 and not api.cart()["items"]
    for item in original["items"]:
        assert api.get(f"/products/{item['product_id']}/")["stock"] >= item["quantity"], "Недостаточный остаток для повтора"
    OrdersPage(driver, settings).repeat(original["id"])
    expected = {i["product_id"]: i["quantity"] for i in original["items"]}
    cart = api.cart()
    actual = {i["product"]["id"]: i["quantity"] for i in cart["items"]}
    assert actual == expected, "Повтор заказа должен переносить все доступные позиции"
    assert CartPage(driver, settings).contents() == expected


@pytest.mark.defect("UI-12")
def test_ui_12_pickup_does_not_require_address(driver, settings, logged_in, products):
    api = logged_in.api
    assert api.get("/addresses/")["count"] == 0
    api.add(products["CAMP-MUG"])
    page = CheckoutPage(driver, settings)
    page.load()
    assert page.element('input[value="pickup"]').is_selected()
    assert page.element(".summary > button.button").is_enabled(), "Самовывоз не требует адреса"
    order_id = page.confirm()
    saved = api.get(f"/orders/{order_id}/")
    assert saved["status"] == "new" and saved["delivery_method"] == "pickup"
    assert saved["address"] is None


@pytest.mark.defect("UI-13")
def test_ui_13_long_product_fits_mobile_viewport(driver, settings, products):
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": 375, "height": 812, "deviceScaleFactor": 1, "mobile": True,
    })
    page = ProductPage(driver, settings)
    page.load(products["CAMP-LONG"]["id"])
    geometry = driver.execute_script("""
        const width = document.documentElement.clientWidth;
        const rect = selector => {
            const r = document.querySelector(selector).getBoundingClientRect();
            return {left: r.left, right: r.right};
        };
        return {width, scroll: document.documentElement.scrollWidth,
                price: rect('.detail-price'), buy: rect('.buy-row button')};
    """)
    assert geometry["width"] == 375, f"Предусловие: viewport должен быть 375 CSS px: {geometry}"
    assert geometry["scroll"] <= 376, f"Горизонтальная прокрутка при ширине 375 px: {geometry}"
    for name in ("price", "buy"):
        assert geometry[name]["left"] >= -1 and geometry[name]["right"] <= 376, f"{name} за краем: {geometry}"


@pytest.mark.defect("UI-14")
def test_ui_14_login_submits_with_enter(driver, settings, account):
    page = AuthPage(driver, settings)
    page.open("/login")
    page.credentials(account)
    page.element('.auth-form input[type="password"]').send_keys(Keys.ENTER)
    page.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "header .logout")),
                    "Нажатие Enter в пароле должно выполнить вход")
    page.route("/account")
    assert ProfilePage(driver, settings).name() == account.profile["full_name"]


@pytest.mark.defect("UI-15")
def test_ui_15_browser_back_restores_catalog_state(driver, settings, products):
    categories = {}
    for product in products.values():
        key = product["category"]["id"]
        categories[key] = categories.get(key, 0) + 1
    large = next((key for key, count in categories.items() if count > 12), None)
    assert large is not None, "Предусловие: нужна категория более чем с 12 товарами"
    page = CatalogPage(driver, settings)
    page.load(ordering="name")
    page.category(large)
    page.apply()
    page.next_page(2)
    before_query, before_ids = page.query(), page.product_ids()
    assert before_query["page"] == ["2"] and before_ids
    # Открываем ссылкой SPA: прямой get очистил бы память и замаскировал UI-15.
    page.click(".product-card .product-name")
    page.element(".product-detail")
    driver.back()
    page.route("/")
    assert page.query() == before_query, "Возврат должен восстановить параметры каталога"
    assert page.product_ids() == before_ids
    assert page.element(".filter-panel select").get_attribute("value") == str(large)
    assert page.element('select[aria-label="Сортировка"]').get_attribute("value") == "name"


@pytest.mark.defect("UI-16")
def test_ui_16_zero_stock_is_labelled_unavailable(driver, settings, products):
    product = products["CAMP-ZERO"]
    assert product["stock"] == 0, "Предусловие: используется исходный нулевой товар"
    page = ProductPage(driver, settings)
    page.load(product["id"])
    assert not page.element(".buy-row button").is_enabled()
    assert page.text(".availability") == "Нет в наличии"
