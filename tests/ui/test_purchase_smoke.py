from decimal import Decimal

import pytest

from support.pages import AuthPage, CartPage, CheckoutPage, OrdersPage, ProductPage


@pytest.mark.ui
@pytest.mark.smoke
def test_purchase_pickup_and_demo_payment(driver, settings, account, products):
    """Контрольный путь из каталога: доступен даже со всеми учебными дефектами."""
    account.api.address()  # Обходит UI-12; адрес не отправляется при самовывозе.
    product = products["CAMP-PRICE-120"]  # Целая цена исключает UI-08.
    AuthPage(driver, settings).login(account)
    page = ProductPage(driver, settings)
    page.load(product["id"])
    page.add()
    cart = CartPage(driver, settings)
    cart.menu("/cart")
    assert cart.contents() == {product["id"]: 1}
    assert cart.total() == Decimal(product["price"])
    cart.click('a[href="/checkout"]')
    checkout = CheckoutPage(driver, settings)
    checkout.route("/checkout")
    assert checkout.shipping() == Decimal("0.00")
    order_id = checkout.confirm()
    OrdersPage(driver, settings).pay()
    saved = account.api.get(f"/orders/{order_id}/")
    assert saved["status"] == "paid"
    assert saved["payment"]["amount"] == product["price"]
    assert saved["total_amount"] == product["price"]
    assert saved["delivery_method"] == "pickup" and saved["address"] is None
    assert [(i["product_id"], i["quantity"]) for i in saved["items"]] == [(product["id"], 1)]
    assert account.api.cart()["items"] == []
