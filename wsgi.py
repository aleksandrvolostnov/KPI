from app import app, init_database

# Инициализируем базу данных при старте WSGI (gunicorn/uWSGI)
init_database()

if __name__ == "__main__":
    app.run()