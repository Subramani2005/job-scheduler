from app import db
from app.models import Project

def create_project(user_id, name):
    project = Project(user_id=user_id, name=name)
    db.session.add(project)
    db.session.commit()
    return project

def get_projects_for_user(user_id):
    return Project.query.filter_by(user_id=user_id).all()

def get_project(project_id, user_id):
    return Project.query.filter_by(id=project_id, user_id=user_id).first()

def delete_project(project_id, user_id):
    project = get_project(project_id, user_id)
    if not project:
        return False
    db.session.delete(project)
    db.session.commit()
    return True