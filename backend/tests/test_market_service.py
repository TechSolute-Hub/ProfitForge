from app.services.market import get_market_service


def test_market_service_is_process_shared():
    first = get_market_service()
    second = get_market_service()

    assert first is second
