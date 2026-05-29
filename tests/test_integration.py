import json
from datetime import datetime, timedelta
from app import Task, KanbanColumn, Project, User, Role

def test_register_and_login_flow(client, db):
    user_role = Role.query.filter_by(role_name='User').first()
    resp = client.post('/register', data={
        'username': 'newman',
        'password': '123',
        'confirm_password': '123',
        'role_id': str(user_role.id)
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Login' in resp.data or b'login' in resp.data.lower()

    resp2 = client.post('/login', data={
        'username': 'newman',
        'password': '123'
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert b'dashboard' in resp2.data.lower()

    user = User.query.filter_by(username='newman').first()
    assert user is not None

def test_create_task_api(client, login, db):
    col = KanbanColumn(name='To Do', wip_limit=5, order=0, project_id=None)
    db.session.add(col)
    project = Project(name='Test Project', owner_id=login.id)
    db.session.add(project)
    db.session.commit()

    resp = client.post(f'/task/new?project_id={project.id}', data={
        'title': 'API Task',
        'description': 'desc',
        'due_date': (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'),
        'difficulty': '2',
        'priority': 'Средний',
        'status': 'To Do',
        'assigned_to': str(login.id)
    }, follow_redirects=True)
    assert resp.status_code == 200
    task = Task.query.filter_by(title='API Task').first()
    assert task is not None
    assert task.description == 'desc'

def test_move_task_on_kanban(client, login, db):
    col_todo = KanbanColumn(name='To Do', wip_limit=5, order=0)
    col_done = KanbanColumn(name='Done', wip_limit=0, order=1)
    db.session.add_all([col_todo, col_done])
    project = Project(name='Kanban Project', owner_id=login.id)
    db.session.add(project)
    db.session.commit()

    task = Task(
        title='Move me',
        description='',
        priority='Низкий',
        status='To Do',
        difficulty='1',
        due_date=datetime.now() + timedelta(days=1),
        user_id=login.id,
        assigned_to_id=login.id,
        project_id=project.id,
        position=0
    )
    db.session.add(task)
    db.session.commit()

    response = client.post('/task_board/move',
                           data=json.dumps({
                               'task_id': task.id,
                               'new_value': 'Done',
                               'mode': 'status',
                               'new_position': 0
                           }),
                           content_type='application/json')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get('success') is True

    updated = Task.query.get(task.id)
    assert updated.status == 'Done'