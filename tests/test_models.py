from datetime import datetime

from app import Project, Task


def test_task_to_dict(db, test_user):
    project = Project(name="Test Proj", owner_id=test_user.id)
    db.session.add(project)
    db.session.commit()

    task = Task(
        title="Test Task",
        description="Desc",
        priority="Высокий",
        status="To Do",
        difficulty="2",
        due_date=datetime(2025, 12, 31),
        user_id=test_user.id,
        assigned_to_id=test_user.id,
        project_id=project.id,
        position=0,
    )
    db.session.add(task)
    db.session.commit()

    d = task.to_dict()
    assert d["title"] == "Test Task"
    assert d["priority"] == "Высокий"
    assert d["due_date"] == "2025-12-31"
    assert d["assigned_to"] == test_user.username
    assert d["project"] == "Test Proj"
