from decimal import Decimal

import pytest

from support.api import expect_status

pytestmark = pytest.mark.api


@pytest.mark.defect("API-01")
def test_api_01_foreign_order_is_not_readable(api, account_factory, products):
    api.add(products["CAMP-MUG"])
    order = api.order()
    stranger = account_factory().api
    response = stranger.request("GET", f"/orders/{order['id']}/")
    expect_status(response, 404)
    assert "items" not in response.json()
    assert stranger.get("/orders/")["count"] == 0


@pytest.mark.defect("API-02")
def test_api_02_foreign_order_cannot_be_cancelled(api, account_factory, products):
    api.add(products["CAMP-MUG"])
    order = api.order()
    stranger = account_factory().api
    response = stranger.request("POST", f"/orders/{order['id']}/cancel/", json={})
    own_order = api.get(f"/orders/{order['id']}/")
    assert (response.status_code, own_order["status"]) == (404, "new"), (
        f"Отмена чужого заказа: HTTP {response.status_code}, статус владельца {own_order['status']}"
    )


@pytest.mark.defect("API-03")
def test_api_03_client_price_is_rejected(api, products):
    product = products["CAMP-PROMO"]
    api.add(product)
    cart_before = api.cart()
    stock_before = api.get(f"/products/{product['id']}/")["stock"]
    response = api.checkout(items=[{"product_id": product["id"], "unit_price": "1.00"}])
    expect_status(response, 400)
    assert "items" in response.json()["field_errors"]
    assert api.get("/orders/")["count"] == 0
    assert api.cart() == cart_before
    assert api.get(f"/products/{product['id']}/")["stock"] == stock_before
    order = api.order()
    assert order["items"][0]["unit_price"] == product["price"]
    assert order["total_amount"] == product["price"]


@pytest.mark.defect("API-04")
def test_api_04_inactive_product_is_rejected(api, hidden_product_id):
    expect_status(api.request("GET", f"/products/{hidden_product_id}/"), 404)
    response = api.request("POST", "/cart/items/", json={
        "product_id": hidden_product_id, "quantity": 1,
    })
    # Если ошибка включена, убеждаемся, что передан именно архивный товар из каталога.
    if response.status_code == 201:
        item = response.json()["items"][0]["product"]
        assert item["sku"] == "CAMP-HIDDEN" and not item["is_active"], "Неверный HIKE_HIDDEN_PRODUCT_ID"
    expect_status(response, 404)
    assert api.cart()["items"] == []


@pytest.mark.defect("API-05")
def test_api_05_cart_quantity_cannot_exceed_99(api, products):
    product = products["CAMP-BULK"]
    assert product["stock"] >= 100, "Предусловие: CAMP-BULK должен иметь остаток не меньше 100"
    item = api.add(product)["items"][0]
    response = api.request("PATCH", f"/cart/items/{item['id']}/", json={"quantity": 100})
    expect_status(response, 400)
    assert "quantity" in response.json()["field_errors"]
    assert api.cart()["items"][0]["quantity"] == 1


@pytest.mark.defect("API-06")
def test_api_06_invalid_profile_phone_is_rejected(api):
    before = api.get("/auth/me/")
    response = api.request("PATCH", "/auth/me/", json={"phone": "123"})
    expect_status(response, 400)
    assert "phone" in response.json()["field_errors"]
    assert api.get("/auth/me/")["phone"] == before["phone"]


@pytest.mark.defect("API-07")
def test_api_07_search_trims_surrounding_spaces(public_api):
    clean = public_api.get("/products/", search="палатка", page_size=50)
    padded = public_api.get("/products/", search=" палатка ", page_size=50)
    assert clean["count"] > 0, "Предусловие: в демо-каталоге должны быть палатки"
    assert padded["count"] == clean["count"]
    assert [p["id"] for p in padded["results"]] == [p["id"] for p in clean["results"]]


@pytest.mark.defect("API-08")
def test_api_08_reversed_price_range_is_rejected(public_api):
    response = public_api.request("GET", "/products/", params={"price_min": "5000", "price_max": "1000"})
    expect_status(response, 400)
    assert "price_max" in response.json()["field_errors"]


@pytest.mark.defect("API-09")
def test_api_09_orders_are_filtered_by_status(api, products):
    api.add(products["CAMP-MUG"])
    paid = api.pay(api.order()["id"])
    api.add(products["CAMP-MUG"])
    unpaid = api.order()
    all_ids = {o["id"] for o in api.get("/orders/")["results"]}
    assert all_ids == {paid["id"], unpaid["id"]}, "Предусловие: два собственных заказа разных статусов"
    orders = api.get("/orders/", status="paid")["results"]
    assert [(o["id"], o["status"]) for o in orders] == [(paid["id"], "paid")]


@pytest.mark.defect("API-10")
def test_api_10_catalog_pages_do_not_overlap(public_api):
    first = public_api.get("/products/", page=1, page_size=12, ordering="name")
    second = public_api.get("/products/", page=2, page_size=12, ordering="name")
    assert first["count"] >= 24 and second["count"] == first["count"], "Предусловие: неизменный демо-каталог"
    assert len(first["results"]) == len(second["results"]) == 12
    overlap = {p["id"] for p in first["results"]} & {p["id"] for p in second["results"]}
    assert not overlap, f"На соседних страницах повторяются ID: {overlap}"


@pytest.mark.defect("API-11")
def test_api_11_repeated_add_increases_existing_quantity(api, products):
    product = products["CAMP-MUG"]
    assert product["stock"] >= 2, "Предусловие: нужно не меньше двух кружек"
    first = api.add(product)["items"][0]
    response = api.request("POST", "/cart/items/", json={"product_id": product["id"], "quantity": 1})
    expect_status(response, 200)
    items = api.cart()["items"]
    assert len(items) == 1
    assert (items[0]["id"], items[0]["quantity"]) == (first["id"], 2)


@pytest.mark.defect("API-12")
@pytest.mark.parametrize("operation", ["quote", "order"])
def test_api_12_expired_promo_is_rejected(api, products, operation):
    product = products["CAMP-PROMO"]
    api.add(product)
    before = api.cart()
    stock = api.get(f"/products/{product['id']}/")["stock"]
    if operation == "quote":
        response = api.request("POST", "/checkout/quote/", json={"delivery_method": "pickup", "promo_code": "OLD10"})
    else:
        response = api.checkout(promo_code="OLD10")
    expect_status(response, 400)
    assert response.json()["code"] == "PROMO_INVALID"
    assert api.get("/orders/")["count"] == 0
    assert api.cart() == before
    assert api.get(f"/products/{product['id']}/")["stock"] == stock


@pytest.mark.defect("API-13")
def test_api_13_cancellation_releases_promo(api, products):
    product = products["CAMP-PROMO"]
    assert product["stock"] >= 2, "Предусловие: большой остаток изолирует проверку от API-14"
    api.add(product)
    first = api.order(promo_code="HIKE10")
    assert first["discount_amount"] == "300.00"
    assert api.cancel(first["id"])["status"] == "cancelled"
    api.add(product)
    second = api.order(promo_code="HIKE10")
    assert second["id"] != first["id"]
    assert second["discount_amount"] == "300.00"
    assert second["total_amount"] == "2700.00"


@pytest.mark.defect("API-14")
def test_api_14_cancellation_restores_last_unit(api, products):
    product = products["CAMP-LAST"]
    assert product["stock"] == 1, "Предусловие: CAMP-LAST должен иметь остаток 1; нужен ручной сброс демо"
    api.add(product)
    order = api.order()
    assert api.get(f"/products/{product['id']}/")["stock"] == 0
    assert api.cancel(order["id"])["status"] == "cancelled"
    assert api.get(f"/products/{product['id']}/")["stock"] == 1, "Отмена не вернула зарезервированную единицу"


@pytest.mark.defect("API-15")
def test_api_15_review_requires_paid_purchase(api, products):
    product = products["CAMP-MUG"]
    api.add(product)
    order = api.order()
    assert order["status"] == "new"
    path = f"/products/{product['id']}/reviews/"
    before = api.get(path)["count"]
    response = api.request("POST", path, json={"rating": 5, "text": "Отзыв автотеста до оплаты покупки."})
    expect_status(response, 403)
    assert response.json()["code"] == "PURCHASE_REQUIRED"
    assert api.get(path)["count"] == before


@pytest.mark.defect("API-16")
def test_api_16_price_sorting_is_numeric(public_api):
    page = public_api.get("/products/", page_size=50, ordering="price")
    assert 0 < page["count"] <= 50 and len(page["results"]) == page["count"]
    by_sku = {p["sku"] for p in page["results"]}
    assert {"CAMP-PRICE-99", "CAMP-PRICE-120", "CAMP-PRICE-1000"} <= by_sku
    actual = [(Decimal(p["price"]), p["id"]) for p in page["results"]]
    assert actual == sorted(actual), "Цена должна сортироваться численно, затем по ID"
