from app import db
from app.models import Queue
from app.services.project_service import get_project

def create_queue(project_id, user_id, name, max_concurrency=5):
    # ownership check happens through project, not duplicated on queue
    project = get_project(project_id, user_id)
    if not project:
        return None
    queue = Queue(project_id=project_id, name=name, max_concurrency=max_concurrency)
    db.session.add(queue)
    db.session.commit()
    return queue

def get_queues_for_project(project_id, user_id):
    project = get_project(project_id, user_id)
    if not project:
        return None
    return Queue.query.filter_by(project_id=project_id).all()

def get_queue(queue_id):
    return Queue.query.get(queue_id)

def set_paused(queue_id, is_paused):
    queue = Queue.query.get(queue_id)
    if not queue:
        return None
    queue.is_paused = is_paused
    db.session.commit()
    return queue