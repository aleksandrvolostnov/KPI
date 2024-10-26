from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from datetime import datetime, timedelta
import csv
import io
from calendar import monthcalendar, month_name
from babel.dates import format_date
import locale
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1111@localhost/efficiency_control'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Модели
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.relationship('Role', backref='users')

    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender_rel', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver_rel', lazy='dynamic')


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_group = db.Column(db.Boolean, default=False)
    content = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    parent_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)  # Поле для родительского сообщения

    # Взаимосвязи
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages_backref')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages_backref', lazy='joined')
    parent_message = db.relationship('Message', remote_side=[id], backref='replies', lazy='joined')  # Взаимосвязь для ответов

    # Обновление `updated_at` при каждом изменении
    def update_timestamp(self):
        self.updated_at = datetime.utcnow()


from datetime import datetime
from sqlalchemy.orm import relationship


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Создатель задачи
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # Ответственный
    difficulty = db.Column(db.Float, nullable=False, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Связь с таблицей файлов
    task_files = db.relationship('File', backref='task', cascade="all, delete-orphan")

    user = db.relationship('User', foreign_keys=[user_id], backref='tasks_created')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='tasks_assigned')


class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))  # Внешний ключ для привязки к задаче

# Логин менеджер
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Главная страница
@app.route('/')
def index():
    return render_template('welcome.html')


# Функция получения последнего сообщения, учитывая как текст, так и файл

# Основной маршрут для чата
# Основной маршрут для чата
# Функция для обработки прочитанных сообщений
def mark_messages_as_read(sender_id, receiver_id):
    unread_messages = Message.query.filter_by(receiver_id=receiver_id, sender_id=sender_id, is_read=False).all()
    for msg in unread_messages:
        msg.is_read = True
        db.session.commit()

# Получение последнего сообщения
# Функция для получения последнего сообщения
def get_last_message(user_id_1, user_id_2):
    last_message = Message.query.filter(
        ((Message.sender_id == user_id_1) & (Message.receiver_id == user_id_2)) |
        ((Message.sender_id == user_id_2) & (Message.receiver_id == user_id_1))
    ).order_by(Message.created_at.desc()).first()

    if last_message:
        return last_message
    return None

# Основной маршрут для чата
# Основной маршрут для чата
@app.route('/chat/<user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    users = User.query.filter(User.id != current_user.id).all()
    last_messages = {}
    user_has_new_message = {}

    for user in users:
        # Получаем последнее сообщение
        last_message = get_last_message(current_user.id, user.id)

        if last_message:
            last_messages[user.id] = last_message.content if last_message.content else f'Файл: {last_message.filename}'
        else:
            last_messages[user.id] = 'Нет сообщений'

        # Проверка на наличие новых сообщений
        has_new_message = Message.query.filter_by(sender_id=user.id, receiver_id=current_user.id).filter(
            Message.is_read == False
        ).count() > 0

        user_has_new_message[user.id] = has_new_message

    # Сортировка пользователей по времени последнего сообщения (если есть)
    users_sorted = sorted(users, key=lambda user: (
        get_last_message(current_user.id, user.id).created_at if get_last_message(current_user.id, user.id) else datetime.min
    ), reverse=True)

    # Обработка отправки нового сообщения
    if request.method == 'POST':
        content = request.form.get('content')
        file = request.files.get('file')
        parent_message_id = request.form.get('parent_message_id')

        if not content and not file:
            return jsonify({"status": "error", "message": "Сообщение не может быть пустым"})

        filename = None
        if file:
            filename = file.filename
            file.save(f'uploads/{filename}')

        new_message = Message(sender_id=current_user.id, receiver_id=user_id, content=content, filename=filename)

        if parent_message_id:
            new_message.parent_message_id = parent_message_id

        db.session.add(new_message)
        db.session.commit()

        return jsonify({"status": "success", "message": "Сообщение отправлено"})

    # Вот сюда вставляем код для загрузки сообщений
    if user_id == 'group':
        messages = Message.query.filter_by(is_group=True).order_by(Message.created_at.asc()).all()
    else:
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
            ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).options(db.joinedload(Message.parent_message)).all()  # Загрузить родительские сообщения

    # Отмечаем все непрочитанные сообщения как прочитанные
    unread_messages = Message.query.filter_by(receiver_id=current_user.id, sender_id=user_id, is_read=False).all()
    for msg in unread_messages:
        msg.is_read = True
    db.session.commit()

    chat_with = "Общая группа" if user_id == 'group' else User.query.get(user_id).username

    return render_template('chat.html', messages=messages, users=users_sorted, chat_with=chat_with,
                           last_messages=last_messages, user_has_new_message=user_has_new_message)

# Маршрут для отправки нового сообщения
@app.route('/chat/new_message', methods=['POST'])
@login_required
def new_message():
    content = request.form.get('content')
    receiver_id = request.form.get('receiver_id')
    parent_message_id = request.form.get('parent_message_id')  # Получаем ID родительского сообщения

    if content and receiver_id:
        new_message = Message(sender_id=current_user.id, receiver_id=receiver_id, content=content)

        if parent_message_id:
            new_message.parent_message_id = parent_message_id  # Связываем с родительским сообщением

        db.session.add(new_message)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Сообщение отправлено',
            'new_message': {
                'sender': current_user.username,
                'content': content
            }
        })

    return jsonify({'status': 'error', 'message': 'Невозможно отправить сообщение'})

# Маршрут для пересылки сообщения
@app.route('/forward', methods=['POST'])
@login_required
def forward_message():
    message_id = request.form.get('message_id')  # Получаем ID сообщения
    recipient_id = request.form.get('recipient_id')  # Получаем ID получателя

    if not message_id or not recipient_id:
        return jsonify({'status': 'error', 'message': 'Неверные данные для пересылки'}), 400

    # Получаем оригинальное сообщение
    message = Message.query.get(message_id)
    if not message:
        return jsonify({'status': 'error', 'message': 'Сообщение не найдено'}), 404

    # Создаем новое сообщение с тем же контентом и файлом для получателя
    forwarded_message = Message(
        sender_id=current_user.id,  # Отправитель — текущий пользователь
        receiver_id=recipient_id,  # Получатель — выбранный пользователь
        content=f"Пересланное сообщение: {message.content}",
        filename=message.filename  # Пересылаем файл, если он есть
    )

    db.session.add(forwarded_message)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Сообщение переслано'})


# Маршрут для ответа на сообщение
@app.route('/reply/<message_id>', methods=['POST'])
@login_required
def reply_to_message(message_id):
    content = request.form.get('reply_content')
    original_message = Message.query.get(message_id)

    if original_message and content:
        reply_message = Message(
            sender_id=current_user.id,
            receiver_id=original_message.sender_id,
            content=content,
            parent_message_id=original_message.id  # Связываем с оригинальным сообщением
        )
        db.session.add(reply_message)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Ответ отправлен',
            'new_message': {
                'sender': current_user.username,
                'content': content
            }
        })

    return jsonify({'status': 'error', 'message': 'Невозможно отправить ответ'})

import os

@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    uploads_dir = 'uploads'
    file_path = os.path.join(uploads_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "Файл не найден"}), 404

    return send_from_directory(uploads_dir, filename)

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role_id = request.form['role_id']

        if password != confirm_password:
            flash('Пароли не совпадают!', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password, role_id=role_id)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Логин
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль!')
    return render_template('login.html')


# Выход из системы
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# Дашборд с задачами
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role.role_name == 'Admin':
        tasks = Task.query.all()
    else:
        tasks = Task.query.filter((Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)).all()
    return render_template('dashboard.html', tasks=tasks)


import os
from werkzeug.utils import secure_filename

# Путь для сохранения загружаемых файлов
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'xls', 'doc', 'csv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Функция проверки допустимого расширения файла
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        # Получение данных из формы
        title = request.form['title']
        description = request.form['description']
        due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        difficulty = float(request.form['difficulty'])
        priority = request.form['priority']
        status = request.form['status']
        assigned_to_id = request.form.get('assigned_to')

        # Создание новой задачи
        new_task = Task(title=title, description=description, due_date=due_date, difficulty=difficulty,
                        priority=priority, status=status, user_id=current_user.id, assigned_to_id=assigned_to_id)

        db.session.add(new_task)
        db.session.commit()

        # Работа с файлами
        files = request.files.getlist('task_files[]')  # Получаем список файлов
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)  # Безопасное имя файла
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)  # Сохранение файла в папку uploads

                # Сохранение информации о файле в базе данных
                new_file = File(filename=filename, task_id=new_task.id)
                db.session.add(new_file)

        # Подтверждение транзакции
        db.session.commit()

        return redirect(url_for('dashboard'))

    # Получение списка пользователей для выбора исполнителя
    users = User.query.all()
    return render_template('create_task.html', users=users)


# Удаление задачи
@app.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user != current_user and current_user.role.role_name != 'Admin':

        return redirect(url_for('dashboard'))
    db.session.delete(task)
    db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)

    # Путь к файлу
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)

    try:
        # Удаляем файл из файловой системы, если он существует
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Файл {file.filename} успешно удалён.")
        else:
            print(f"Файл {file.filename} не найден в {file_path}. Возможно, он был удалён ранее.")

        # Удаляем запись о файле из базы данных
        db.session.delete(file)
        db.session.commit()

        return jsonify({"status": "success"})

    except Exception as e:
        # Логируем ошибку и возвращаем ответ с ошибкой
        print(f"Ошибка при удалении файла {file.filename}: {e}")
        return jsonify({"status": "error", "message": "Ошибка при удалении файла"}), 500


@app.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    # Получаем задачу по ID или возвращаем 404, если не найдена
    task = Task.query.get_or_404(task_id)

    if request.method == 'POST':
        # Обновляем информацию о задаче
        task.title = request.form['title']
        task.description = request.form['description']
        task.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        task.difficulty = float(request.form['difficulty'])
        task.priority = request.form['priority']
        task.status = request.form['status']
        task.assigned_to_id = request.form.get('assigned_to')

        # Работа с файлами (новые загружаемые файлы)
        files = request.files.getlist('task_files[]')  # Проверяем правильность атрибута 'task_files[]'
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Сохраняем информацию о новом файле в базе данных
                new_file = File(filename=filename, task_id=task.id)
                db.session.add(new_file)

        # Сохраняем изменения в базе данных
        db.session.commit()

        return redirect(url_for('dashboard'))

    # Получаем существующие файлы, привязанные к задаче
    files = File.query.filter_by(task_id=task_id).all()

    # Получаем список всех пользователей для выбора исполнителя
    users = User.query.all()

    # Передаем задачу, пользователей и файлы в шаблон для отображения
    return render_template('edit_task.html', task=task, users=users, files=files)


@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    users = User.query.all()  # Load all users for the dropdown
    filters = {}

    if request.method == 'POST':
        if request.form.get('title'):
            filters['title'] = request.form['title']
        if request.form.get('assigned_to'):
            filters['assigned_to_id'] = int(request.form['assigned_to'])  # Get assigned user ID
        if request.form.get('priority'):
            filters['priority'] = request.form['priority']
        if request.form.get('due_date'):
            filters['due_date'] = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        if request.form.get('difficulty'):
            filters['difficulty'] = float(request.form['difficulty'])

        # Получение файлов из формы
        if 'task_files' in request.files:
            files = request.files.getlist('task_files')
            file_paths = []

            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)
                    file_paths.append(filepath)

        # Дополнительно, можно сохранить ссылки на файлы в базу данных или другой способ

        # Поиск задач
        tasks_query = Task.query

        if 'title' in filters:
            tasks_query = tasks_query.filter(Task.title.ilike(f"%{filters['title']}%"))
        if 'assigned_to_id' in filters:
            tasks_query = tasks_query.filter(Task.assigned_to_id == filters['assigned_to_id'])
        if 'priority' in filters:
            tasks_query = tasks_query.filter(Task.priority == filters['priority'])
        if 'due_date' in filters:
            tasks_query = tasks_query.filter(Task.due_date == filters['due_date'])
        if 'difficulty' in filters:
            tasks_query = tasks_query.filter(Task.difficulty == filters['difficulty'])

        tasks = tasks_query.all()

    else:
        # Show all tasks for everyone (admin & regular users)
        tasks = Task.query.all()

    return render_template('tasks.html', tasks=tasks, users=users)
  # Передаем список пользователей
import locale
from datetime import datetime
from calendar import monthcalendar, month_name
from flask import render_template, request
from flask_login import login_required, current_user
# Устанавливаем локаль для русского языка
locale.setlocale(locale.LC_TIME, 'Russian_Russia')
# Календарь задач
@app.route('/calendar', methods=['GET'])
@login_required
def calendar():
    current_year = request.args.get('year', datetime.now().year, type=int)
    current_month = request.args.get('month', datetime.now().month, type=int)

    if current_month > 12:
        current_month = 1
        current_year += 1
    elif current_month < 1:
        current_month = 12
        current_year -= 1

    if current_user.role.role_name == 'Admin':
            tasks = Task.query.all()
    else:
            tasks = Task.query.filter(
                (Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)).all()

    days_in_month = monthcalendar(current_year, current_month)
    calendar_days = []

    for week in days_in_month:
        week_data = []
        for day in week:
            if day != 0:
                date = datetime(current_year, current_month, day)
                tasks_for_day = [task for task in tasks if task.due_date.date() == date.date()]
                week_data.append({
                    'date': date,
                    'tasks': tasks_for_day
                })
            else:
                week_data.append({
                    'date': None,
                    'tasks': []
                })
        calendar_days.append(week_data)

    current_month_name = month_name[current_month]

    previous_month = current_month - 1 if current_month > 1 else 12
    next_month = current_month + 1 if current_month < 12 else 1
    previous_year = current_year if current_month > 1 else current_year - 1
    next_year = current_year if current_month < 12 else current_year + 1

    return render_template('calendar.html',
                           calendar_days=calendar_days,
                           current_month_name=current_month_name,
                           current_year=current_year,
                           current_month=current_month,
                           previous_month=previous_month,
                           next_month=next_month,
                           previous_year=previous_year,
                           next_year=next_year)



@app.before_request
def check_deadlines():
    if current_user.is_authenticated:
        # Обновляем статус задач на "Просрочено", если срок истек
        tasks_in_progress = Task.query.filter_by(status='In Progress').all()
        for task in tasks_in_progress:
            if task.due_date < datetime.utcnow():
                task.status = 'Просрочено'
                db.session.commit()

        # Уведомление за 2 дня до дедлайна
        tasks = Task.query.filter_by(user_id=current_user.id, status='In Progress').all()
        for task in tasks:
            if task.due_date - datetime.utcnow() <= timedelta(days=2):
                flash(f'Задача "{task.title}" приближается к дедлайну!')


# Отчеты (KPI)


@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    users = []
    if current_user.role.role_name == 'Admin':
        users = User.query.all()

    # Логика для выбора задач: личный KPI или KPI выбранного пользователя
    if current_user.role.role_name == 'Admin' and request.method == 'POST':
        user_id = request.form.get('user_id')
        tasks = Task.query.filter(
            (Task.user_id == user_id) | (Task.assigned_to_id == user_id)
        ).all()
    else:
        tasks = Task.query.filter(
            (Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)
        ).all()

    # Логика расчета личного KPI
    user_kpi = calculate_kpi(tasks)

    # Логика расчета общего KPI предприятия
    all_tasks = Task.query.all()
    company_kpi = calculate_kpi(all_tasks)

    return render_template('reports.html', user_kpi=user_kpi, company_kpi=company_kpi, users=users)


def calculate_kpi(tasks):
    """Функция для расчета KPI на основе списка задач"""
    difficulty_mapping = {'Легко': 1, 'Средне': 2, 'Сложно': 3}
    priority_mapping = {'Низкий': 0.5, 'Средний': 1, 'Высокий': 1.5}
    overdue_penalty = 0.5

    total_weighted_value = 0
    completed_weighted_value = 0

    for task in tasks:
        task_difficulty = difficulty_mapping.get(task.difficulty, 1)
        task_priority = priority_mapping.get(task.priority, 1)
        weighted_value = task_difficulty * task_priority

        total_weighted_value += weighted_value

        if task.status == 'Completed':
            completed_weighted_value += weighted_value
        elif task.status == 'Просрочено':
            completed_weighted_value += weighted_value * overdue_penalty

    if total_weighted_value > 0:
        kpi_score = (completed_weighted_value / total_weighted_value) * 100
    else:
        kpi_score = 0

    return kpi_score


from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
import io

@app.route('/download_report', methods=['POST'])
@login_required
def download_report():
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    selected_user_id = request.form.get('user_id')

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    # Если админ, выбирает пользователя, иначе — текущий пользователь
    if current_user.role.role_name == 'Admin' and selected_user_id:
        user_id = int(selected_user_id)
    else:
        user_id = current_user.id

    tasks = Task.query.filter(
        (Task.user_id == user_id) | (Task.assigned_to_id == user_id)
    ).filter(Task.due_date.between(start_date, end_date)).all()

    difficulty_mapping = {'Легко': 1, 'Средне': 2, 'Сложно': 3}
    priority_mapping = {'Низкий': 0.5, 'Средний': 1, 'Высокий': 1.5}
    overdue_penalty = 0.5

    total_weighted_value = 0
    completed_weighted_value = 0

    for task in tasks:
        task_difficulty = difficulty_mapping.get(task.difficulty, 1)
        task_priority = priority_mapping.get(task.priority, 1)
        weighted_value = task_difficulty * task_priority

        total_weighted_value += weighted_value

        if task.status == 'Completed':
            completed_weighted_value += weighted_value
        elif task.status == 'Просрочено':
            completed_weighted_value += weighted_value * overdue_penalty

    if total_weighted_value > 0:
        kpi_score = (completed_weighted_value / total_weighted_value) * 100
    else:
        kpi_score = 0

    # Создаем Excel файл
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Отчет"

    headers = ['Название', 'Описание', 'Приоритет', 'Статус', 'Крайняя дата выполнения', 'Сложность']
    sheet.append(headers)

    for task in tasks:
        sheet.append([task.title, task.description, task.priority, task.status, task.due_date.strftime('%Y-%m-%d'), task.difficulty])

    sheet.append([])
    sheet.append(['KPI за выбранный период:', round(kpi_score, 2)])

    for col_num, col_title in enumerate(headers, 1):
        column_letter = get_column_letter(col_num)
        sheet.column_dimensions[column_letter].width = 20

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'report_{start_date_str}_to_{end_date_str}.xlsx'
    )



# Запуск приложения
if __name__ == '__main__':
    app.run(debug=True)
