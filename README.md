# ⚡ Efficiency Control – Система управления эффективностью

[![CI](https://github.com/aleksandrvolostnov/KPI/actions/workflows/ci-cd.yml/badge.svg?branch=main)](https://github.com/aleksandrvolostnov/KPI/actions/workflows/ci-cd.yml)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.3-black)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)

**Efficiency Control** – веб‑сервис для управления задачами, проектами, командной работой и аналитикой (канбан, Гант, чат, KPI).

## Возможности

- Управление задачами (дедлайны, приоритеты, сложность)
- Канбан‑доска с WIP‑лимитами
- Диаграмма Ганта
- Чат (личные сообщения, группа, файлы)
- Отчёты и KPI (Lead Time, Cycle Time, Throughput)
- Напоминания
- Проекты и роли (Admin / User)
- Загрузка аватаров и файлов
- Docker‑поддержка

## Технологии

- Flask, Flask‑SQLAlchemy, Flask‑Login
- PostgreSQL / SQLite
- openpyxl, pytest, GitHub Actions

## Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone https://github.com/aleksandrvolostnov/KPI.git
cd KPI
```

### 2. Создать виртуальное окружение
```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

### 3. Установить зависимости
```bash
pip install -r requirements.txt
```

### 4. Настроить базу данных PostgreSQL
Убедитесь, что PostgreSQL запущен.  
Создайте базу:
```sql
CREATE DATABASE efficiency_control;
```
Выполните SQL‑скрипт из раздела 🗄️ Схема базы данных (см. ниже).

### 5. Запустить приложение
```bash
python app.py
```
Откройте `http://127.0.0.1:5000`. Логины по умолчанию: admin / 1, admin1 / 1, user1 / user1, ...

## 🐳 Запуск через Docker

```bash
docker build -t efficiency-control .
docker run -p 5000:5000 --env DATABASE_URL=postgresql://user:pass@host/db efficiency-control
```

## 🗄️ Схема базы данных (SQL)

Выполните этот скрипт в вашей PostgreSQL:

```sql
-- ======================================================
-- 1. Таблица ролей
-- ======================================================
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL
);

-- ======================================================
-- 2. Таблица пользователей
-- ======================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(150) NOT NULL,
    role_id INTEGER REFERENCES roles(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    email VARCHAR(150) UNIQUE,
    phone VARCHAR(20),
    avatar VARCHAR(255),
    tokens INTEGER DEFAULT 0
);

-- ======================================================
-- 3. Таблица проектов
-- ======================================================
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner_id INTEGER NOT NULL REFERENCES users(id)
);

-- ======================================================
-- 4. Связь проектов и участников
-- ======================================================
CREATE TABLE project_members (
    project_id INTEGER REFERENCES projects(id),
    user_id INTEGER REFERENCES users(id),
    PRIMARY KEY (project_id, user_id)
);

-- ======================================================
-- 5. Канбан-колонки
-- ======================================================
CREATE TABLE kanban_columns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    wip_limit INTEGER DEFAULT 5,
    "order" INTEGER DEFAULT 0,
    project_id INTEGER REFERENCES projects(id)
);

-- ======================================================
-- 6. Задачи (tasks)
-- ======================================================
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'To Do',
    difficulty VARCHAR(50) NOT NULL,
    due_date TIMESTAMP NOT NULL,
    user_id INTEGER REFERENCES users(id),
    assigned_to_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    parent_task_id INTEGER REFERENCES tasks(id),
    position INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    review_at TIMESTAMP,
    completed_at TIMESTAMP,
    status_history JSONB DEFAULT '[]'::jsonb
);

-- ======================================================
-- 7. Подзадачи
-- ======================================================
CREATE TABLE subtasks (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    title VARCHAR(150) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL
);

-- ======================================================
-- 8. Комментарии к задачам
-- ======================================================
CREATE TABLE task_comments (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ======================================================
-- 9. Файлы
-- ======================================================
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    task_id INTEGER REFERENCES tasks(id)
);

-- ======================================================
-- 10. Напоминания
-- ======================================================
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    reminder_date TIMESTAMP NOT NULL,
    priority VARCHAR(50) DEFAULT 'Низкий',
    repeat VARCHAR(50) DEFAULT 'Нет',
    user_id INTEGER NOT NULL REFERENCES users(id)
);

-- ======================================================
-- 11. Сообщения (чат)
-- ======================================================
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER REFERENCES users(id),
    is_group BOOLEAN DEFAULT FALSE,
    content TEXT,
    filename VARCHAR(150),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    parent_message_id INTEGER REFERENCES messages(id)
);

-- ======================================================
-- Заполнение начальными данными
-- ======================================================

INSERT INTO roles (role_name) VALUES ('Admin'), ('User');

INSERT INTO users (username, password, role_id) VALUES
('admin', '1', (SELECT id FROM roles WHERE role_name = 'Admin')),
('admin1', '1', (SELECT id FROM roles WHERE role_name = 'Admin')),
('user1', 'user1', (SELECT id FROM roles WHERE role_name = 'User')),
('user2', 'user2', (SELECT id FROM roles WHERE role_name = 'User')),
('user3', 'user3', (SELECT id FROM roles WHERE role_name = 'User')),
('user4', 'user4', (SELECT id FROM roles WHERE role_name = 'User')),
('user5', 'user5', (SELECT id FROM roles WHERE role_name = 'User'));

INSERT INTO kanban_columns (name, wip_limit, "order", project_id) VALUES
('To Do', 5, 0, NULL),
('In Progress', 3, 1, NULL),
('Review', 2, 2, NULL),
('Done', 0, 3, NULL);
```

## 🔄 CI/CD пайплайн

GitHub Actions автоматически запускает тесты при пуше в `main`.  
Статус: [https://github.com/aleksandrvolostnov/KPI/actions/workflows/ci-cd.yml/badge.svg?branch=main](https://github.com/aleksandrvolostnov/KPI/actions/workflows/ci-cd.yml?branch=main)
```
