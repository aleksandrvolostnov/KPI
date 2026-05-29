import sys
import os
import tempfile
import pytest

# --- 1. Устанавливаем DATABASE_URL до импорта app ---
TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')
if TEST_DATABASE_URL:
    os.environ['DATABASE_URL'] = TEST_DATABASE_URL
else:
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

# --- 2. Теперь импортируем app (он прочитает DATABASE_URL) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app as flask_app, db as _db

# --- 3. Дополнительные тестовые настройки ---
flask_app.config.update({
    'TESTING': True,
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'WTF_CSRF_ENABLED': False,
    'UPLOAD_FOLDER': tempfile.mkdtemp(),
    'SECRET_KEY': 'test-secret',
})

# Удаляем старый движок, который мог создаться при импорте
if hasattr(_db, '_engine'):
    del _db._engine
if hasattr(_db, '_engines'):
    _db._engines.clear()

# --- Фикстуры ---
@pytest.fixture(scope='session')
def app():
    yield flask_app

@pytest.fixture(scope='function')
def db(app):
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.create_all()
        from app import Role
        if Role.query.count() == 0:
            _db.session.add_all([Role(role_name='Admin'), Role(role_name='User')])
            _db.session.commit()
        yield _db

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_user(db):
    from app import User, Role
    user_role = Role.query.filter_by(role_name='User').first()
    user = User(
        username='testuser',
        password='testpass',
        role_id=user_role.id
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def login(client, test_user):
    with client.session_transaction() as sess:
        from flask_login import login_user
        login_user(test_user)
        sess['_user_id'] = str(test_user.id)
    return test_user