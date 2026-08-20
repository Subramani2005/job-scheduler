from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services import queue_service

queues_bp = Blueprint("queues", __name__, url_prefix="/api/projects/<project_id>/queues")

@queues_bp.route("", methods=["POST"])
@jwt_required()
def create_queue(project_id):
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    max_concurrency = data.get("max_concurrency", 5)

    if not name:
        return jsonify({"error": "name is required"}), 400

    queue = queue_service.create_queue(project_id, user_id, name, max_concurrency)
    if not queue:
        return jsonify({"error": "project not found"}), 404

    return jsonify({
        "id": queue.id, "name": queue.name,
        "max_concurrency": queue.max_concurrency,
        "is_paused": queue.is_paused
    }), 201


@queues_bp.route("", methods=["GET"])
@jwt_required()
def list_queues(project_id):
    user_id = get_jwt_identity()
    queues = queue_service.get_queues_for_project(project_id, user_id)
    if queues is None:
        return jsonify({"error": "project not found"}), 404

    return jsonify([
        {"id": q.id, "name": q.name, "max_concurrency": q.max_concurrency,
         "is_paused": q.is_paused}
        for q in queues
    ]), 200


@queues_bp.route("/<queue_id>/pause", methods=["PATCH"])
@jwt_required()
def pause_queue(project_id, queue_id):
    queue = queue_service.set_paused(queue_id, True)
    if not queue:
        return jsonify({"error": "queue not found"}), 404
    return jsonify({"id": queue.id, "is_paused": queue.is_paused}), 200


@queues_bp.route("/<queue_id>/resume", methods=["PATCH"])
@jwt_required()
def resume_queue(project_id, queue_id):
    queue = queue_service.set_paused(queue_id, False)
    if not queue:
        return jsonify({"error": "queue not found"}), 404
    return jsonify({"id": queue.id, "is_paused": queue.is_paused}), 200