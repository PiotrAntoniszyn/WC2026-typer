import os

os.environ["FLASK_ENV"] = "testing"

import pytest

from config import TestingSettings, get_config


@pytest.fixture(scope="session")
def app():
    get_config.cache_clear()
    cfg = TestingSettings()

    from app import create_app

    application = create_app(config=cfg)

    with application.app_context():
        from app.models import db

        db.create_all()
        yield application
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
