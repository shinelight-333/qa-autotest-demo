# Карта покрытия и чек-лист

Основа проверок — [требования демо-магазина](requirements.md).
Каждая строка ниже — реализованный автоматизированный случай и пункт чек-листа.
Наличие строки означает «автоматизировано», а не «проверено и пройдено».
Статусы исторических прогонов вынесены в [results.md](results.md).

В наборе 33 функции тестов и **34 случая**: API-12 параметризован двумя операциями.
Маркер `defect("API-07")` или `defect("UI-03")` связывает тест с ID сценария.
Отдельный сценарий можно выбрать, например, через `-k api_07` или `-k ui_03`.

| Требования | Пункты чек-листа |
|---|---|
| Пользователи и изоляция данных | API-01/02/06, UI-01/02/03/14 |
| Каталог, поиск и навигация | API-07/08/10/16, UI-05/06/08/13/15/16 |
| Избранное и корзина | API-04/05/11, UI-04/07 |
| Оформление, доставка и промокоды | API-03/12/13, UI-09/10/12, SMOKE |
| Состояния и повтор заказа | API-09/14, UI-11, SMOKE |
| Отзывы после оплаты | API-15 |

Исходники: [API](../tests/api/test_api_defects.py),
[UI](../tests/ui/test_ui_defects.py), [smoke](../tests/ui/test_purchase_smoke.py).

## Все сценарии

| ID | Автотест | Ожидаемое поведение |
|---|---|---|
| API-01 | `test_api_01_foreign_order_is_not_readable` | Чужой заказ возвращает 404 |
| API-02 | `test_api_02_foreign_order_cannot_be_cancelled` | Чужая отмена отклонена, статус не изменён |
| API-03 | `test_api_03_client_price_is_rejected` | Подмена цены отклонена без изменения корзины, заказов и остатка |
| API-04 | `test_api_04_inactive_product_is_rejected` | Архивный товар не добавляется |
| API-05 | `test_api_05_cart_quantity_cannot_exceed_99` | Количество 100 отклонено, прежнее сохранено |
| API-06 | `test_api_06_invalid_profile_phone_is_rejected` | Телефон 123 отклонён, прежний сохранён |
| API-07 | `test_api_07_search_trims_surrounding_spaces` | Поиск с крайними пробелами эквивалентен обычному |
| API-08 | `test_api_08_reversed_price_range_is_rejected` | Перепутанные границы дают 400 |
| API-09 | `test_api_09_orders_are_filtered_by_status` | Фильтр paid возвращает только оплаченный заказ |
| API-10 | `test_api_10_catalog_pages_do_not_overlap` | Страницы 1 и 2 не пересекаются |
| API-11 | `test_api_11_repeated_add_increases_existing_quantity` | Повторный POST даёт 200 и количество 2 |
| API-12 / quote | `test_api_12_expired_promo_is_rejected[quote]` | OLD10 отклонён при расчёте заказа |
| API-12 / order | `test_api_12_expired_promo_is_rejected[order]` | OLD10 отклонён при создании заказа |
| API-13 | `test_api_13_cancellation_releases_promo` | После отмены HIKE10 доступен в новом заказе |
| API-14 | `test_api_14_cancellation_restores_last_unit` | Отмена возвращает последнюю единицу товара |
| API-15 | `test_api_15_review_requires_paid_purchase` | Неоплаченная покупка не даёт права на отзыв |
| API-16 | `test_api_16_price_sorting_is_numeric` | Численная сортировка цены и стабильный порядок по ID |
| UI-01 | `test_ui_01_registration_checks_password_confirmation` | Несовпадающие пароли блокируют регистрацию |
| UI-02 | `test_ui_02_profile_name_survives_reload` | Имя сохраняется через API и после reload |
| UI-03 | `test_ui_03_account_switch_clears_orders_cache` | Смена аккаунта очищает кеш списка заказов |
| UI-04 | `test_ui_04_catalog_favorite_survives_reload` | Избранное из каталога сохраняется |
| UI-05 | `test_ui_05_filter_resets_catalog_to_first_page` | Новый фильтр возвращает страницу 1 |
| UI-06 | `test_ui_06_reset_removes_price_from_url_and_results` | Сброс очищает URL и выдачу |
| UI-07 | `test_ui_07_decreasing_quantity_updates_cart_total` | Уменьшение количества обновляет итог |
| UI-08 | `test_ui_08_product_price_preserves_kopecks` | Цена 199,90 сохраняет копейки |
| UI-09 | `test_ui_09_checkout_sends_selected_address` | Снимок заказа содержит выбранный второй адрес |
| UI-10 | `test_ui_10_pickup_removes_courier_shipping` | Самовывоз убирает 300 ₽ из доставки и итога |
| UI-11 | `test_ui_11_repeat_order_adds_all_items` | Повтор добавляет обе позиции |
| UI-12 | `test_ui_12_pickup_does_not_require_address` | Самовывоз оформляется без адреса |
| UI-13 | `test_ui_13_long_product_fits_mobile_viewport` | При 375 px нет горизонтальной прокрутки, действия в пределах ширины |
| UI-14 | `test_ui_14_login_submits_with_enter` | Enter отправляет форму входа |
| UI-15 | `test_ui_15_browser_back_restores_catalog_state` | Назад восстанавливает URL, категорию и страницу |
| UI-16 | `test_ui_16_zero_stock_is_labelled_unavailable` | Нулевой остаток подписан «Нет в наличии» |
| SMOKE | `test_purchase_pickup_and_demo_payment` | Покупка с самовывозом, учебная оплата, пустая корзина |

## Границы покрытия

- Полное тестирование всех требований не заявлено: например, нет отдельных тестов
  повторной оплаты, конкурентного резервирования и повторного `Idempotency-Key`.
- Smoke проверяет покупку с самовывозом и учебной оплатой; браузерная часть использует
  подготовленные через API аккаунт и адрес. Это не проверка регистрации через UI.
- UI-01 проверяет сообщение формы и отсутствие успешного входа; не перехватывает
  серверный запрос регистрации и не проверяет напрямую отсутствие записи в БД.
- UI-13 проверяет геометрию при эмулированной ширине 375 px; физический телефон не используется.
- API-14 проверяет публичный остаток; внутренний журнал складских движений не читается.
- Тесты не обращаются к Django напрямую, не переключают учебные дефекты и не сбрасывают БД.
- Полные API-проверки требуют подготовленных данных; изоляция аккаунтов не изолирует остатки.
