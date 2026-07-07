import pytest
from pydantic import ValidationError
from config import Settings

def test_parse_watched_services():
    # Test comma-separated string
    s1 = Settings(watched_services="service1, service2,service3", api_token="dummy", dashboard_password="dummy", _env_file=None, telegram_owner_ids="1", telegram_bot_token="x")
    assert s1.watched_services == ["service1", "service2", "service3"]

    # Test JSON array format (as in .env.example)
    s2 = Settings(watched_services='["serviceA", "serviceB"]', api_token="dummy", dashboard_password="dummy", _env_file=None, telegram_owner_ids="1", telegram_bot_token="x")
    assert s2.watched_services == ["serviceA", "serviceB"]

    # Test actual list
    s3 = Settings(watched_services=["svc1", "svc2"], api_token="dummy", dashboard_password="dummy", _env_file=None, telegram_owner_ids="1", telegram_bot_token="x")
    assert s3.watched_services == ["svc1", "svc2"]

def test_parse_telegram_owner_ids():
    s1 = Settings(telegram_owner_ids="123, 456", api_token="dummy", dashboard_password="dummy", telegram_bot_token="dummy", _env_file=None)
    assert s1.telegram_owner_ids == [123, 456]

    s2 = Settings(telegram_owner_ids=789, api_token="dummy", dashboard_password="dummy", telegram_bot_token="dummy", _env_file=None)
    assert s2.telegram_owner_ids == [789]

    s3 = Settings(telegram_owner_ids=[101, 102], api_token="dummy", dashboard_password="dummy", telegram_bot_token="dummy", _env_file=None)
    assert s3.telegram_owner_ids == [101, 102]

def test_missing_api_token():
    with pytest.raises(ValidationError) as exc:
        Settings(telegram_owner_ids="123", telegram_bot_token="dummy", dashboard_password="dummy", _env_file=None)
    assert "api_token" in str(exc.value)

def test_missing_dashboard_password():
    with pytest.raises(ValidationError) as exc:
        Settings(telegram_owner_ids="123", telegram_bot_token="dummy", api_token="dummy", _env_file=None)
    assert "dashboard_password" in str(exc.value)
