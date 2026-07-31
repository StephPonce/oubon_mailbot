"""AliExpress DS recommend-feed envelope parsing.

Regression guard for the bug that made the feed report "empty/dead" on every
niche for months: AE uses TWO envelopes across DS methods, and `resp_result` is
a WRAPPER (resp_code/resp_msg/result) — not an alternative name for `result`.
The old code did `resp.get("result") or resp.get("resp_result")`, landed on the
wrapper, read wrapper["products"] -> None, and returned [] silently.
"""

import asyncio

from ospra_os.aliexpress.ds_client import AliExpressDSClient


def _client() -> AliExpressDSClient:
    client = AliExpressDSClient.__new__(AliExpressDSClient)
    client.is_available = lambda: True  # type: ignore[method-assign]
    return client


def _stub_response(client, body):
    async def _fake_request(method, params):
        return body
    client._request = _fake_request  # type: ignore[method-assign]


PRODUCT_ROW = {
    "product_id": 1005001,
    "product_title": "Smart Plug WiFi",
    "target_sale_price": "9.99",
    "product_main_image_url": "https://example.test/a.jpg",
}


def test_parses_nested_resp_result_envelope():
    """The shape recommend.feed.get actually returns — previously dropped."""
    client = _client()
    _stub_response(client, {
        "aliexpress_ds_recommend_feed_get_response": {
            "resp_result": {
                "resp_code": 200,
                "resp_msg": "success",
                "result": {
                    "total_record_count": 1,
                    "products": {"product": [PRODUCT_ROW]},
                },
            }
        }
    })
    products = asyncio.run(client.get_hot_products())
    assert len(products) == 1, "nested resp_result envelope must parse"


def test_parses_flat_result_envelope():
    """The shape ds.product.get uses — must keep working."""
    client = _client()
    _stub_response(client, {
        "aliexpress_ds_recommend_feed_get_response": {
            "result": {
                "total_record_count": 1,
                "products": {"product": [PRODUCT_ROW]},
            }
        }
    })
    assert len(asyncio.run(client.get_hot_products())) == 1


def test_parses_traffic_product_dto_key():
    """AE sometimes names the row list traffic_product_d_t_o."""
    client = _client()
    _stub_response(client, {
        "aliexpress_ds_recommend_feed_get_response": {
            "resp_result": {
                "resp_code": 200,
                "result": {"products": {"traffic_product_d_t_o": [PRODUCT_ROW]}},
            }
        }
    })
    assert len(asyncio.run(client.get_hot_products())) == 1


def test_business_error_inside_resp_result_is_surfaced(caplog):
    """AE returns business errors with HTTP 200 inside resp_result, so
    _request's top-level error check never sees them. They must be logged,
    not silently swallowed as 'feed empty'."""
    client = _client()
    _stub_response(client, {
        "aliexpress_ds_recommend_feed_get_response": {
            "resp_result": {
                "resp_code": 4001,
                "resp_msg": "feed name is invalid",
                "result": {},
            }
        }
    })
    with caplog.at_level("WARNING"):
        assert asyncio.run(client.get_hot_products(feed_name="bogus_feed")) == []
    assert "business error" in caplog.text
    assert "4001" in caplog.text
