from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from datetime import datetime, timedelta
import csv
import io
from calendar import monthcalendar, month_name
from babel.dates import format_date
import locale
import os
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
import json
from hashlib import md5
import mimetypes
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1111@localhost/efficiency_control'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------ МОДЕЛИ ------------------
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
    email = db.Column(db.String(150), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    tokens = db.Column(db.Integer, default=0)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender_rel', lazy='dynamic', overlaps='sender_rel,sent_messages_backref')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver_rel', lazy='dynamic', overlaps='receiver_rel,received_messages_backref')

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('User', backref='owned_projects', lazy=True)
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    members = db.relationship('User', secondary='project_members', backref='projects')

project_members = db.Table('project_members',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class Reminder(db.Model):
    __tablename__ = 'reminders'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reminder_date = db.Column(db.DateTime, nullable=False)
    priority = db.Column(db.String(50), default='Низкий')
    repeat = db.Column(db.String(50), default='Нет')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='reminders')

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
    parent_message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages_backref', overlaps='sent_messages,sender_rel')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages_backref', lazy='joined', overlaps='received_messages,receiver_rel')
    parent_message = db.relationship('Message', remote_side=[id], backref='replies', lazy='joined')

# ---------------- КАНБАН МОДЕЛИ ----------------
class KanbanColumn(db.Model):
    __tablename__ = 'kanban_columns'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    wip_limit = db.Column(db.Integer, default=5)
    order = db.Column(db.Integer, default=0)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    project = db.relationship('Project', backref='kanban_columns')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'wip_limit': self.wip_limit, 'order': self.order}

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='To Do')
    difficulty = db.Column(db.String(50), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    parent_task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    parent_task = db.relationship('Task', remote_side=[id], backref='dependent_tasks')
    user = db.relationship('User', foreign_keys=[user_id], backref='tasks_created')
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='tasks_assigned')

    # Канбан поля
    position = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    review_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status_history = db.Column(db.JSON, default=list)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.strftime('%Y-%m-%d'),
            'assigned_to': self.assigned_to.username if self.assigned_to else None,
            'project': self.project.name if self.project else None,
            'subtasks': [st.to_dict() for st in self.subtasks],
            'parent_task': self.parent_task.title if self.parent_task else None,
            'dependent_tasks': [t.title for t in self.dependent_tasks]
        }

class SubTask(db.Model):
    __tablename__ = 'subtasks'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    task = db.relationship('Task', backref=db.backref('subtasks', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'title': self.title,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else "",
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else "",
        }

class TaskComments(db.Model):
    __tablename__ = 'task_comments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    task = db.relationship('Task', backref='task_comments')
    user = db.relationship('User', backref='user_comments')

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'comment': self.comment,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))

# ------------------ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_difficulty(value):
    """Преобразует числовую сложность в текст для отображения"""
    if value in (1, '1'):
        return 'Легкая'
    elif value in (2, '2'):
        return 'Средняя'
    elif value in (3, '3'):
        return 'Сложная'
    return str(value)

# ------------------ МАРШРУТЫ ------------------
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'email' in request.form:
            email = request.form['email']
            if email:
                current_user.email = email
                flash('Почта обновлена!', 'success')
            else:
                current_user.email = None
                flash('Почта удалена!', 'success')
        if 'phone' in request.form:
            phone = request.form['phone']
            if phone:
                current_user.phone = phone
                flash('Телефон обновлен!', 'success')
            else:
                current_user.phone = None
                flash('Телефон удален!', 'success')
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and allowed_file(avatar_file.filename):
                avatar_filename = secure_filename(avatar_file.filename)
                avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename)
                avatar_file.save(avatar_path)
                current_user.avatar = avatar_filename
                flash('Аватарка обновлена!', 'success')
        db.session.commit()
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/user/<int:user_id>')
@login_required
def view_user(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('user_profile.html', user=user)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('welcome.html')

# Чат
def mark_messages_as_read(sender_id, receiver_id):
    unread_messages = Message.query.filter_by(receiver_id=receiver_id, sender_id=sender_id, is_read=False).all()
    for msg in unread_messages:
        msg.is_read = True
        db.session.commit()

def get_last_message(user_id_1, user_id_2):
    return Message.query.filter(
        ((Message.sender_id == user_id_1) & (Message.receiver_id == user_id_2)) |
        ((Message.sender_id == user_id_2) & (Message.receiver_id == user_id_1))
    ).order_by(Message.created_at.desc()).first()

@app.route('/chat/<user_id>', methods=['GET', 'POST'])
@login_required
def chat(user_id):
    users = User.query.filter(User.id != current_user.id).all()
    last_messages = {}
    user_has_new_message = {}
    for user in users:
        last_message = get_last_message(current_user.id, user.id)
        last_messages[user.id] = last_message.content if last_message and last_message.content else (f'Файл: {last_message.filename}' if last_message else 'Нет сообщений')
        has_new_message = Message.query.filter_by(sender_id=user.id, receiver_id=current_user.id, is_read=False).count() > 0
        user_has_new_message[user.id] = has_new_message
    users_sorted = sorted(users, key=lambda user: (get_last_message(current_user.id, user.id).created_at if get_last_message(current_user.id, user.id) else datetime.min), reverse=True)
    if request.method == 'POST':
        content = request.form.get('content')
        file = request.files.get('file')
        parent_message_id = request.form.get('parent_message_id')
        if not content and not file:
            return jsonify({"status": "error", "message": "Сообщение не может быть пустым"})
        filename = None
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join('uploads', filename))
        new_message = Message(sender_id=current_user.id, receiver_id=user_id, content=content, filename=filename)
        if parent_message_id:
            new_message.parent_message_id = parent_message_id
        db.session.add(new_message)
        db.session.commit()
        return jsonify({"status": "success", "message": "Сообщение отправлено"})
    if user_id == 'group':
        messages = Message.query.filter_by(is_group=True).order_by(Message.created_at.asc()).all()
    else:
        messages = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
            ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.created_at.asc()).options(db.joinedload(Message.parent_message)).all()
    unread = Message.query.filter_by(receiver_id=current_user.id, sender_id=user_id, is_read=False).all()
    for msg in unread:
        msg.is_read = True
    db.session.commit()
    chat_with = "Общая группа" if user_id == 'group' else User.query.get(user_id).username
    return render_template('chat.html', messages=messages, users=users_sorted, chat_with=chat_with,
                           last_messages=last_messages, user_has_new_message=user_has_new_message)

@app.route('/chat/new_message', methods=['POST'])
@login_required
def new_message():
    content = request.form.get('content')
    receiver_id = request.form.get('receiver_id')
    parent_message_id = request.form.get('parent_message_id')
    if content and receiver_id:
        new_message = Message(sender_id=current_user.id, receiver_id=receiver_id, content=content)
        if parent_message_id:
            new_message.parent_message_id = parent_message_id
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Сообщение отправлено', 'new_message': {'sender': current_user.username, 'content': content}})
    return jsonify({'status': 'error', 'message': 'Невозможно отправить сообщение'})

@app.route('/forward', methods=['POST'])
@login_required
def forward_message():
    message_id = request.form.get('message_id')
    recipient_id = request.form.get('recipient_id')
    if not message_id or not recipient_id:
        return jsonify({'status': 'error', 'message': 'Неверные данные для пересылки'}), 400
    message = Message.query.get(message_id)
    if not message:
        return jsonify({'status': 'error', 'message': 'Сообщение не найдено'}), 404
    forwarded = Message(sender_id=current_user.id, receiver_id=recipient_id, content=f"Пересланное сообщение: {message.content}", filename=message.filename)
    db.session.add(forwarded)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Сообщение переслано'})

@app.route('/reply/<message_id>', methods=['POST'])
@login_required
def reply_to_message(message_id):
    content = request.form.get('reply_content')
    original = Message.query.get(message_id)
    if original and content:
        reply = Message(sender_id=current_user.id, receiver_id=original.sender_id, content=content, parent_message_id=original.id)
        db.session.add(reply)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Ответ отправлен', 'new_message': {'sender': current_user.username, 'content': content}})
    return jsonify({'status': 'error', 'message': 'Невозможно отправить ответ'})

@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']
        role_id = request.form['role_id']
        if password != confirm:
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ------------------ ДАШБОРД ------------------
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role.role_name == 'Admin':
        tasks = Task.query.all()
    else:
        tasks = Task.query.filter((Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)).all()
    tasks_sorted = sorted(tasks, key=lambda x: x.due_date)
    upcoming_tasks = tasks_sorted[:3]
    total_tasks = len(tasks)
    low_priority_count = Task.query.filter_by(priority='Низкий').count()
    medium_priority_count = Task.query.filter_by(priority='Средний').count()
    high_priority_count = Task.query.filter_by(priority='Высокий').count()
    easy_count = Task.query.filter_by(difficulty='1').count() + Task.query.filter_by(difficulty='Легко').count()
    medium_count = Task.query.filter_by(difficulty='2').count() + Task.query.filter_by(difficulty='Средне').count()
    hard_count = Task.query.filter_by(difficulty='3').count() + Task.query.filter_by(difficulty='Сложно').count()
    avg_difficulty = db.session.query(db.func.avg(db.cast(Task.difficulty, db.Float))).scalar()
    return render_template('dashboard.html', tasks=upcoming_tasks, total_tasks=total_tasks,
                           low_priority_count=low_priority_count, medium_priority_count=medium_priority_count,
                           high_priority_count=high_priority_count, average_difficulty=avg_difficulty,
                           easy_count=easy_count, medium_count=medium_count, hard_count=hard_count)

# ------------------ НАСТРОЙКИ ЗАГРУЗКИ ФАЙЛОВ ------------------
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'xls', 'doc', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------ СОЗДАНИЕ И РЕДАКТИРОВАНИЕ ЗАДАЧ ------------------
@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def create_task():
    project_id = request.args.get('project_id')
    project = None
    if project_id:
        project = Project.query.get_or_404(project_id)
        if current_user.id != project.owner_id and current_user not in project.members:
            flash('У вас нет доступа для добавления задач.', 'error')
            return redirect(url_for('projects'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        difficulty = request.form['difficulty']
        priority = request.form['priority']
        status = request.form['status']
        assigned_to_id = request.form.get('assigned_to')
        new_task = Task(
            title=title, description=description, due_date=due_date, difficulty=difficulty,
            priority=priority, status=status, user_id=current_user.id,
            assigned_to_id=assigned_to_id, project_id=project.id if project else None, position=0
        )
        db.session.add(new_task)
        files = request.files.getlist('task_files[]')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                db.session.add(File(filename=filename, task_id=new_task.id))
        db.session.commit()
        if project:
            return redirect(url_for('project_detail', project_id=project.id))
        else:
            return redirect(url_for('dashboard'))
    if project:
        columns = KanbanColumn.query.filter((KanbanColumn.project_id == project.id) | (KanbanColumn.project_id.is_(None))).order_by(KanbanColumn.order).all()
    else:
        columns = KanbanColumn.query.filter_by(project_id=None).order_by(KanbanColumn.order).all()
    status_choices = [(col.name, col.name) for col in columns]
    users = project.members if project else User.query.all()
    return render_template('create_task.html', users=users, project=project, status_choices=status_choices)

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
    path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(file)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form['description']
        task.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
        task.difficulty = request.form['difficulty']
        task.priority = request.form['priority']
        task.status = request.form['status']
        task.assigned_to_id = request.form.get('assigned_to')
        files = request.files.getlist('task_files[]')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                db.session.add(File(filename=filename, task_id=task.id))
        db.session.commit()
        return redirect(url_for('dashboard'))
    files = File.query.filter_by(task_id=task_id).all()
    users = User.query.all()
    columns = KanbanColumn.query.filter((KanbanColumn.project_id == task.project_id) | (KanbanColumn.project_id.is_(None))).order_by(KanbanColumn.order).all()
    status_choices = [(col.name, col.name) for col in columns]
    return render_template('edit_task.html', task=task, users=users, files=files, status_choices=status_choices)

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    users = User.query.all()
    all_statuses = [col.name for col in KanbanColumn.query.all()]
    all_statuses = list(dict.fromkeys(all_statuses))
    if request.method == 'POST':
        query = Task.query
        if request.form.get('title'):
            query = query.filter(Task.title.ilike(f"%{request.form['title']}%"))
        if request.form.get('assigned_to'):
            query = query.filter(Task.assigned_to_id == int(request.form['assigned_to']))
        if request.form.get('priority'):
            query = query.filter(Task.priority == request.form['priority'])
        if request.form.get('due_date'):
            query = query.filter(Task.due_date == datetime.strptime(request.form['due_date'], '%Y-%m-%d'))
        if request.form.get('difficulty'):
            query = query.filter(Task.difficulty == request.form['difficulty'])
        if request.form.get('status'):
            query = query.filter(Task.status == request.form['status'])
        tasks = query.all()
    else:
        tasks = Task.query.all()
    return render_template('tasks.html', tasks=tasks, users=users, all_statuses=all_statuses)

# ------------------ КАЛЕНДАРЬ ------------------
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'ru_RU')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')

@app.route('/calendar', methods=['GET'])
@login_required
def calendar():
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1
    if current_user.role.role_name == 'Admin':
        tasks = Task.query.filter(db.extract('year', Task.due_date) == year, db.extract('month', Task.due_date) == month).all()
    else:
        tasks = Task.query.filter((Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id),
                                  db.extract('year', Task.due_date) == year, db.extract('month', Task.due_date) == month).all()
    weeks = monthcalendar(year, month)
    calendar_days = []
    for week in weeks:
        week_data = []
        for day in week:
            if day != 0:
                date = datetime(year, month, day)
                day_tasks = [t for t in tasks if t.due_date.date() == date.date()]
                week_data.append({'date': date, 'tasks': day_tasks})
            else:
                week_data.append({'date': None, 'tasks': []})
        calendar_days.append(week_data)
    prev_month = month - 1 if month > 1 else 12
    next_month = month + 1 if month < 12 else 1
    prev_year = year if month > 1 else year - 1
    next_year = year if month < 12 else year + 1
    easy = sum(1 for t in tasks if t.difficulty in ('1','Легко'))
    medium = sum(1 for t in tasks if t.difficulty in ('2','Средне'))
    hard = sum(1 for t in tasks if t.difficulty in ('3','Сложно'))
    low_p = sum(1 for t in tasks if t.priority == 'Низкий')
    med_p = sum(1 for t in tasks if t.priority == 'Средний')
    high_p = sum(1 for t in tasks if t.priority == 'Высокий')
    return render_template('calendar.html', calendar_days=calendar_days, current_month_name=month_name[month],
                           current_year=year, current_month=month, previous_month=prev_month, next_month=next_month,
                           previous_year=prev_year, next_year=next_year, easy_count=easy, medium_count=medium,
                           hard_count=hard, low_priority_count=low_p, medium_priority_count=med_p, high_priority_count=high_p)

@app.before_request
def check_deadlines():
    if current_user.is_authenticated:
        in_progress = Task.query.filter_by(status='In Progress').all()
        for task in in_progress:
            if task.due_date < datetime.utcnow():
                task.status = 'Overdue'
                db.session.commit()
        for task in Task.query.filter_by(user_id=current_user.id, status='In Progress').all():
            if task.due_date - datetime.utcnow() <= timedelta(days=2):
                flash(f'Задача "{task.title}" приближается к дедлайну!')

# ------------------ КАНБАН-ДОСКА ------------------
@app.route('/task_board')
@login_required
def task_board():
    mode = request.args.get('mode', 'status')
    project_id = request.args.get('project_id', type=int)
    if project_id:
        project = Project.query.get_or_404(project_id)
        if current_user not in project.members and current_user.id != project.owner_id and current_user.role.role_name != 'Admin':
            flash('Нет доступа к проекту', 'error')
            return redirect(url_for('projects'))
        tasks = Task.query.filter_by(project_id=project_id).all()
    else:
        tasks = Task.query.filter((Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)).all()
    if mode == 'status':
        columns = KanbanColumn.query.filter((KanbanColumn.project_id == project_id) | (KanbanColumn.project_id.is_(None))).order_by(KanbanColumn.order).all()
        tasks_by_column = {col.name: [] for col in columns}
        for task in tasks:
            col_name = task.status if task.status in tasks_by_column else (columns[0].name if columns else 'To Do')
            tasks_by_column[col_name].append(task)
        for col in tasks_by_column:
            tasks_by_column[col].sort(key=lambda t: t.position)
        column_counts = {col.name: len(tasks_by_column[col.name]) for col in columns}
    elif mode == 'priority':
        columns = [{'name': 'Низкий', 'wip_limit': 0}, {'name': 'Средний', 'wip_limit': 0}, {'name': 'Высокий', 'wip_limit': 0}]
        tasks_by_column = {'Низкий': [], 'Средний': [], 'Высокий': []}
        for task in tasks:
            tasks_by_column[task.priority].append(task)
        column_counts = {col['name']: len(tasks_by_column[col['name']]) for col in columns}
    else:
        columns = [{'name': 'Легкая', 'wip_limit': 0}, {'name': 'Средняя', 'wip_limit': 0}, {'name': 'Сложная', 'wip_limit': 0}]
        tasks_by_column = {'Легкая': [], 'Средняя': [], 'Сложная': []}
        for task in tasks:
            key = format_difficulty(task.difficulty)
            if key in tasks_by_column:
                tasks_by_column[key].append(task)
            else:
                tasks_by_column['Средняя'].append(task)
        column_counts = {col['name']: len(tasks_by_column[col['name']]) for col in columns}
    users = User.query.all()
    return render_template('task_board.html',
                           mode=mode,
                           columns=columns,
                           tasks_by_column=tasks_by_column,
                           column_counts=column_counts,
                           project_id=project_id,
                           users=users,
                           now=datetime.utcnow())

@app.route('/task_board/move', methods=['POST'])
@login_required
def task_board_move():
    data = request.get_json()
    task_id = data.get('task_id')
    new_value = data.get('new_value')
    mode = data.get('mode')
    new_position = data.get('new_position')
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id and task.assigned_to_id != current_user.id and current_user.role.role_name != 'Admin':
        return jsonify({'error': 'Нет прав'}), 403
    if mode == 'status':
        col = KanbanColumn.query.filter_by(name=new_value, project_id=task.project_id).first()
        if not col:
            col = KanbanColumn.query.filter_by(name=new_value, project_id=None).first()
        if col and col.wip_limit > 0:
            current_cnt = Task.query.filter(Task.status == new_value, Task.project_id == task.project_id).count()
            if current_cnt >= col.wip_limit:
                return jsonify({'error': f'WIP лимит {col.wip_limit} превышен в колонке "{new_value}"'}), 400
        now = datetime.utcnow()
        task.status = new_value
        if new_value == 'In Progress' and not task.started_at:
            task.started_at = now
        if new_value == 'Review' and not task.review_at:
            task.review_at = now
        if new_value == 'Done':
            if not task.completed_at:
                task.completed_at = now
        else:
            task.completed_at = None
        history = task.status_history or []
        history.append({'status': new_value, 'timestamp': now.isoformat()})
        task.status_history = history
    elif mode == 'priority':
        task.priority = new_value
    else:
        if new_value == 'Легкая':
            task.difficulty = '1'
        elif new_value == 'Средняя':
            task.difficulty = '2'
        elif new_value == 'Сложная':
            task.difficulty = '3'
        else:
            task.difficulty = new_value
    if new_position is not None and mode == 'status':
        task.position = new_position
    db.session.commit()
    return jsonify({'success': True})

@app.route('/task_board/reorder', methods=['POST'])
@login_required
def task_board_reorder():
    data = request.get_json()
    col_name = data.get('column_name')
    task_ids = data.get('task_ids')
    if not col_name or not task_ids:
        return jsonify({'error': 'Неверные данные'}), 400
    for idx, tid in enumerate(task_ids):
        t = Task.query.get(tid)
        if t and t.status == col_name:
            t.position = idx
    db.session.commit()
    return jsonify({'success': True})

# ------------------ ОТЧЁТЫ ------------------
def calculate_kanban_metrics(tasks):
    completed = [t for t in tasks if t.status == 'Done' and t.completed_at]
    if not completed:
        return {'lead_time_avg': 0, 'cycle_time_avg': 0, 'throughput': 0, 'total_completed': 0}
    lead_times = [(t.completed_at - t.created_at).total_seconds() / 86400 for t in completed if t.created_at]
    cycle_times = [(t.completed_at - t.started_at).total_seconds() / 86400 for t in completed if t.started_at]
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    last30 = [t for t in completed if t.completed_at >= thirty_ago]
    throughput = len(last30) / 30.0
    return {
        'lead_time_avg': round(sum(lead_times)/len(lead_times), 2) if lead_times else 0,
        'cycle_time_avg': round(sum(cycle_times)/len(cycle_times), 2) if cycle_times else 0,
        'throughput': round(throughput, 2),
        'total_completed': len(completed)
    }

def get_completion_percentage(user_id=None):
    if user_id:
        tasks = Task.query.filter((Task.user_id == user_id) | (Task.assigned_to_id == user_id)).all()
    else:
        tasks = Task.query.all()
    total = len(tasks)
    if total == 0:
        return 0.0
    completed = sum(1 for t in tasks if t.status == 'Done')
    return round((completed / total) * 100, 1)

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    users = []
    if current_user.role.role_name == 'Admin':
        users = User.query.all()
    if request.method == 'POST' and current_user.role.role_name == 'Admin' and request.form.get('user_id'):
        selected_user_id = int(request.form['user_id'])
        tasks = Task.query.filter((Task.user_id == selected_user_id) | (Task.assigned_to_id == selected_user_id)).all()
        user_kpi = get_completion_percentage(selected_user_id)
    else:
        tasks = Task.query.filter((Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)).all()
        user_kpi = get_completion_percentage(current_user.id)
    kanban_metrics = calculate_kanban_metrics(tasks)
    company_kpi = get_completion_percentage()
    burn_data = {}
    for i in range(14):
        day = datetime.utcnow().date() - timedelta(days=i)
        cnt = Task.query.filter(
            db.func.date(Task.completed_at) == day,
            (Task.user_id == current_user.id) | (Task.assigned_to_id == current_user.id)
        ).count()
        burn_data[day.isoformat()] = cnt
    return render_template('reports.html',
                           user_kpi=user_kpi,
                           company_kpi=company_kpi,
                           kanban_metrics=kanban_metrics,
                           burn_data=burn_data,
                           users=users)

@app.route('/download_report', methods=['POST'])
@login_required
def download_report():
    start = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
    end = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
    if current_user.role.role_name == 'Admin' and request.form.get('user_id'):
        uid = int(request.form['user_id'])
    else:
        uid = current_user.id
    tasks = Task.query.filter((Task.user_id == uid) | (Task.assigned_to_id == uid)).filter(Task.due_date.between(start, end)).all()
    metrics = calculate_kanban_metrics(tasks)
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчет"
    headers = ['Название', 'Описание', 'Приоритет', 'Статус', 'Крайняя дата', 'Сложность']
    ws.append(headers)
    for t in tasks:
        ws.append([t.title, t.description, t.priority, t.status, t.due_date.strftime('%Y-%m-%d'), t.difficulty])
    ws.append([])
    ws.append(['Lead Time (средний, дни):', metrics['lead_time_avg']])
    ws.append(['Cycle Time (средний, дни):', metrics['cycle_time_avg']])
    ws.append(['Throughput (задач/день):', metrics['throughput']])
    ws.append(['Всего завершено:', metrics['total_completed']])
    for i, _ in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 20
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'report_{start.strftime("%Y-%m-%d")}_to_{end.strftime("%Y-%m-%d")}.xlsx')

@app.route('/download_all_kpis', methods=['POST'])
@login_required
def download_all_kpis():
    if current_user.role.role_name != 'Admin':
        flash("Нет прав")
        return redirect(url_for('reports'))
    start = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
    end = datetime.strptime(request.form['end_date'], '%Y-%m-%d')
    users = User.query.all()
    data = []
    for u in users:
        tasks = Task.query.filter((Task.user_id == u.id) | (Task.assigned_to_id == u.id)).filter(Task.due_date.between(start, end)).all()
        m = calculate_kanban_metrics(tasks)
        data.append({'user': u.username, 'lead': m['lead_time_avg'], 'cycle': m['cycle_time_avg'], 'throughput': m['throughput']})
    wb = Workbook()
    ws = wb.active
    ws.title = "Общий KPI"
    ws.append(['Сотрудник', 'Lead Time (дни)', 'Cycle Time (дни)', 'Throughput (задач/день)'])
    for d in data:
        ws.append([d['user'], d['lead'], d['cycle'], d['throughput']])
    from openpyxl.chart import BarChart, Reference
    chart = BarChart()
    chart.title = "Lead Time сотрудников"
    chart.x_axis.title = "Сотрудники"
    chart.y_axis.title = "Дни"
    data_ref = Reference(ws, min_col=2, min_row=2, max_row=len(data)+1, max_col=2)
    cats = Reference(ws, min_col=1, min_row=2, max_row=len(data)+1)
    chart.add_data(data_ref, titles_from_data=False)
    chart.set_categories(cats)
    ws.add_chart(chart, "E4")
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, as_attachment=True, download_name=f'all_kpis_{start.strftime("%Y-%m-%d")}_to_{end.strftime("%Y-%m-%d")}.xlsx')

# ------------------ ДИАГРАММА ГАНТА, ПОДЗАДАЧИ, КОММЕНТАРИИ ------------------
@app.route('/gantt', methods=['GET', 'POST'])
@login_required
def gantt():
    if request.method == 'POST':
        new = Task(
            title=request.form['title'],
            description=request.form['description'],
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
            priority=request.form['priority'],
            status=request.form['status'],
            difficulty=request.form['difficulty'],
            user_id=current_user.id,
            assigned_to_id=request.form.get('assigned_to')
        )
        db.session.add(new)
        db.session.commit()
        return redirect(url_for('gantt'))
    tasks = Task.query.all()
    return render_template('gantt.html', tasks_data=[t.to_dict() for t in tasks], users=User.query.all())

@app.route('/add_subtask/<int:task_id>', methods=['POST'])
@login_required
def add_subtask(task_id):
    data = request.get_json()
    st = SubTask(task_id=task_id, title=data['title'],
                 start_date=datetime.strptime(data['start_date'], '%Y-%m-%d'),
                 end_date=datetime.strptime(data['end_date'], '%Y-%m-%d'))
    db.session.add(st)
    db.session.commit()
    return jsonify({'status': 'success', 'subtask': st.to_dict()})

@app.route('/delete_subtask/<int:subtask_id>', methods=['DELETE'])
@login_required
def delete_subtask(subtask_id):
    st = SubTask.query.get(subtask_id)
    if st:
        db.session.delete(st)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@app.route('/create_subtask', methods=['POST'])
@login_required
def create_subtask():
    data = request.get_json()
    st = SubTask(task_id=data['task_id'], title=data['title'],
                 start_date=datetime.strptime(data['start_date'], '%Y-%m-%d'),
                 end_date=datetime.strptime(data['end_date'], '%Y-%m-%d'))
    db.session.add(st)
    db.session.commit()
    return jsonify({'status': 'success', 'subtask': st.to_dict()})

@app.route('/update_subtask', methods=['POST'])
@login_required
def update_subtask():
    data = request.get_json()
    st = SubTask.query.get(data['id'])
    if st:
        st.title = data['title']
        st.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
        st.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        db.session.commit()
        return jsonify({'status': 'success', 'subtask': st.to_dict()})
    return jsonify({'status': 'error'}), 404

@app.route('/task/<int:task_id>/add_comment', methods=['POST'])
@login_required
def add_comment(task_id):
    data = request.get_json()
    if not data.get('comment', '').strip():
        return jsonify({'status': 'error', 'message': 'Пустой комментарий'}), 400
    comm = TaskComments(task_id=task_id, user_id=current_user.id, comment=data['comment'])
    db.session.add(comm)
    db.session.commit()
    return jsonify({'status': 'success', 'comment': comm.to_dict()})

@app.route('/task/<int:task_id>/edit_comment/<int:comment_id>', methods=['PUT'])
@login_required
def edit_comment(task_id, comment_id):
    data = request.get_json()
    comm = TaskComments.query.filter_by(id=comment_id, task_id=task_id).first()
    if not comm:
        return jsonify({'status': 'error'}), 404
    if comm.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403
    comm.comment = data['comment']
    db.session.commit()
    return jsonify({'status': 'success', 'comment': comm.to_dict()})

@app.route('/task/<int:task_id>/delete_comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(task_id, comment_id):
    comm = TaskComments.query.filter_by(id=comment_id, task_id=task_id).first()
    if not comm:
        return jsonify({'status': 'error'}), 404
    if comm.user_id != current_user.id:
        return jsonify({'status': 'error'}), 403
    db.session.delete(comm)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/task/<int:task_id>')
@login_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify({'id': task.id, 'title': task.title, 'comments': [c.to_dict() for c in task.task_comments]})

# ------------------ РЕДАКТОР ДОКУМЕНТОВ ------------------
@app.route('/editor')
def editor_page():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    return render_template('editor.html', files=files)

@app.route('/edit/<filename>')
def edit_document(filename):
    key = md5(f"{filename}_{current_user.id}_{datetime.utcnow()}".encode()).hexdigest()
    config = {
        "document": {
            "fileType": filename.split('.')[-1].lower(),
            "key": key,
            "title": filename,
            "url": f"http://127.0.0.1:5000/uploads/{filename}",
            "permissions": {"edit": True}
        },
        "editorConfig": {
            "callbackUrl": "http://127.0.0.1:5000/callback",
            "mode": "edit",
            "lang": "ru",
            "user": {"id": current_user.id, "name": current_user.username}
        }
    }
    return render_template('editor_frame.html', document_config=config)

@app.route('/upload/<task_id>', methods=['POST'])
def upload_file_for_task(task_id):
    if 'file' not in request.files:
        return "No file", 400
    f = request.files['file']
    if f.filename == '':
        return "No file selected", 400
    if not allowed_file(f.filename):
        return "Недопустимый формат", 400
    f.save(os.path.join(UPLOAD_FOLDER, secure_filename(f.filename)))
    db.session.add(File(filename=f.filename, task_id=task_id))
    db.session.commit()
    return redirect(url_for('editor_page'))

@app.route('/callback', methods=['POST'])
def callback():
    app.logger.info(f"Callback: {request.json}")
    return jsonify({"error": 0})

# ------------------ НАПОМИНАНИЯ ------------------
@app.route('/reminders')
@login_required
def view_reminders():
    rems = Reminder.query.filter_by(user_id=current_user.id).order_by(Reminder.reminder_date).all()
    return render_template('reminders.html', reminders=rems)

@app.route('/reminder/new', methods=['GET', 'POST'])
@login_required
def create_reminder():
    if request.method == 'POST':
        r = Reminder(
            title=request.form['title'],
            description=request.form.get('description', ''),
            reminder_date=datetime.strptime(request.form['reminder_date'], '%Y-%m-%dT%H:%M'),
            priority=request.form['priority'],
            repeat=request.form['repeat'],
            user_id=current_user.id
        )
        db.session.add(r)
        db.session.commit()
        flash('Напоминание создано!', 'success')
        return redirect(url_for('view_reminders'))
    return render_template('create_reminder.html')

@app.route('/reminder/edit/<int:reminder_id>', methods=['GET', 'POST'])
@login_required
def edit_reminder(reminder_id):
    r = Reminder.query.filter_by(id=reminder_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        r.title = request.form['title']
        r.description = request.form.get('description', '')
        r.reminder_date = datetime.strptime(request.form['reminder_date'], '%Y-%m-%dT%H:%M')
        r.priority = request.form['priority']
        r.repeat = request.form['repeat']
        db.session.commit()
        flash('Обновлено!', 'success')
        return redirect(url_for('view_reminders'))
    return render_template('edit_reminder.html', reminder=r)

@app.route('/reminder/delete/<int:reminder_id>', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    r = Reminder.query.filter_by(id=reminder_id, user_id=current_user.id).first_or_404()
    db.session.delete(r)
    db.session.commit()
    flash('Удалено!', 'success')
    return redirect(url_for('view_reminders'))

# ------------------ ПРОЕКТЫ ------------------
@app.route('/projects')
@login_required
def projects():
    projs = Project.query.filter((Project.owner_id == current_user.id) | (Project.members.any(id=current_user.id))).all()
    return render_template('projects.html', projects=projs)

@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        p = Project(name=request.form['name'], description=request.form.get('description', ''), owner_id=current_user.id)
        db.session.add(p)
        db.session.commit()
        flash('Проект создан!', 'success')
        return redirect(url_for('projects'))
    return render_template('create_project.html')

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template('project_detail.html', project=project, all_users=User.query.all())

@app.route('/project/<int:project_id>/add_member', methods=['POST'])
def add_project_member(project_id):
    p = Project.query.get_or_404(project_id)
    if p.owner_id != current_user.id:
        flash('Только владелец может добавлять участников', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    user = User.query.get(request.form['user_id'])
    if user:
        p.members.append(user)
        db.session.commit()
        flash('Участник добавлен', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/project/<int:project_id>/task/new', methods=['GET', 'POST'])
@login_required
def create_task_in_project(project_id):
    p = Project.query.get_or_404(project_id)
    if current_user.id != p.owner_id and current_user not in p.members:
        flash('Нет доступа', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if request.method == 'POST':
        new = Task(
            title=request.form['title'], description=request.form['description'],
            priority=request.form['priority'], status=request.form['status'],
            difficulty=request.form['difficulty'],
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
            project_id=project_id, user_id=current_user.id,
            assigned_to_id=request.form.get('assigned_to'), position=0
        )
        db.session.add(new)
        db.session.commit()
        flash('Задача добавлена!', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    columns = KanbanColumn.query.filter((KanbanColumn.project_id == project_id) | (KanbanColumn.project_id.is_(None))).order_by(KanbanColumn.order).all()
    status_choices = [(c.name, c.name) for c in columns]
    return render_template('create_task.html', project=p, users=p.members, status_choices=status_choices)

def project_access_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        p = Project.query.get_or_404(kwargs['project_id'])
        if current_user.id != p.owner_id and current_user not in p.members:
            flash('Нет доступа', 'error')
            return redirect(url_for('projects'))
        return func(*args, **kwargs)
    return wrapper

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    p = Project.query.get_or_404(project_id)
    if p.owner_id != current_user.id:
        flash('Только владелец может удалить проект', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    db.session.delete(p)
    db.session.commit()
    flash('Проект удалён', 'success')
    return redirect(url_for('projects'))

@app.route('/project/<int:project_id>/remove_member', methods=['POST'])
@login_required
def remove_project_member(project_id):
    p = Project.query.get_or_404(project_id)
    if p.owner_id != current_user.id:
        flash('Только владелец может удалять участников', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    user = User.query.get(request.form['user_id'])
    if user and user in p.members:
        p.members.remove(user)
        db.session.commit()
        flash('Участник удалён', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    p = Project.query.get_or_404(project_id)
    if p.owner_id != current_user.id:
        flash('Только владелец может редактировать', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    if request.method == 'POST':
        p.name = request.form['name']
        p.description = request.form.get('description', '')
        db.session.commit()
        flash('Проект обновлён', 'success')
        return redirect(url_for('project_detail', project_id=project_id))
    return render_template('edit_project.html', project=p)

@app.route('/project_tasks/<int:project_id>')
@login_required
def project_tasks(project_id):
    return redirect(url_for('task_board', project_id=project_id))

@app.route('/project_tasks_priority/<int:project_id>')
@login_required
def project_tasks_priority(project_id):
    return redirect(url_for('task_board', project_id=project_id, mode='priority'))

@app.route('/project_tasks_difficulty/<int:project_id>')
@login_required
def project_tasks_difficulty(project_id):
    return redirect(url_for('task_board', project_id=project_id, mode='difficulty'))

@app.route('/update_project_task_category', methods=['POST'])
@login_required
def update_project_task_category():
    data = request.json
    task = Task.query.get(data.get('task_id'))
    if task:
        status_map = {'В работе': 'In Progress', 'Выполненные': 'Done', 'Просроченные': 'Overdue'}
        new_status = status_map.get(data.get('new_category'), data.get('new_category'))
        task.status = new_status
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Задача не найдена'}), 404

# ------------------ АДМИНИСТРИРОВАНИЕ ПОЛЬЗОВАТЕЛЕЙ ------------------
@app.route('/admin/users')
@login_required
def manage_users():
    if current_user.role.role_name != 'Admin':
        flash('Нет прав', 'error')
        return redirect(url_for('dashboard'))
    return render_template('admin_users.html', users=User.query.all(), roles=Role.query.all())

@app.route('/admin_user/<int:user_id>/update_role', methods=['POST'])
@login_required
def update_user_role(user_id):
    if current_user.role.role_name != 'Admin':
        return jsonify({'status': 'error'}), 403
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    user.role_id = data.get('role_id')
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role.role_name != 'Admin':
        flash('Нет прав', 'error')
        return redirect(url_for('manage_users'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Нельзя удалить себя', 'error')
        return redirect(url_for('manage_users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {user.username} удалён', 'success')
    return redirect(url_for('manage_users'))

@app.route('/admin_user/<int:user_id>/update_password', methods=['POST'])
@login_required
def update_password(user_id):
    data = request.json
    user = User.query.get(user_id)
    if user:
        user.password = data.get('password')
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'}), 404

@app.route('/admin_user/<int:user_id>/update_name', methods=['POST'])
@login_required
def update_username(user_id):
    if current_user.role.role_name != 'Admin':
        return jsonify({'status': 'error'}), 403
    data = request.get_json()
    user = User.query.get_or_404(user_id)
    user.username = data.get('username')
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
def create_user_admin():
    if current_user.role.role_name != 'Admin':
        flash('Нет прав', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('Имя уже существует', 'error')
            return redirect(url_for('create_user_admin'))
        new = User(username=username, password=request.form['password'],
                   role_id=request.form['role_id'], email=request.form.get('email'))
        db.session.add(new)
        db.session.commit()
        flash('Пользователь создан', 'success')
        return redirect(url_for('manage_users'))
    return render_template('admin_create_user.html', roles=Role.query.all())

# ------------------ ИНИЦИАЛИЗАЦИЯ КОЛОНОК КАНБАН ------------------
def init_kanban_columns():
    default = [
        {'name': 'To Do', 'wip_limit': 5, 'order': 0},
        {'name': 'In Progress', 'wip_limit': 3, 'order': 1},
        {'name': 'Review', 'wip_limit': 2, 'order': 2},
        {'name': 'Done', 'wip_limit': 0, 'order': 3}
    ]
    for col in default:
        if not KanbanColumn.query.filter_by(name=col['name'], project_id=None).first():
            db.session.add(KanbanColumn(name=col['name'], wip_limit=col['wip_limit'], order=col['order'], project_id=None))
    db.session.commit()

def init_database():
    """Создаёт таблицы и инициализирует колонки канбана. Вызывать при старте приложения."""
    with app.app_context():
        db.create_all()
        init_kanban_columns()

# ------------------ ЗАПУСК ЛОКАЛЬНОГО СЕРВЕРА ------------------
if __name__ == '__main__':
    init_database()
    app.run(debug=True)