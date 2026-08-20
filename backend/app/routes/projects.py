from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services import project_service

projects_bp = Blueprint("projects", __name__, url_prefix="/api/projects")

@projects_bp.route("", methods=["POST"])
@jwt_required()
def create_project():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "name is required"}), 400

    project = project_service.create_project(user_id, name)
    return jsonify({
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at.isoformat()
    }), 201


@projects_bp.route("", methods=["GET"])
@jwt_required()
def list_projects():
    user_id = get_jwt_identity()
    projects = project_service.get_projects_for_user(user_id)
    return jsonify([
        {"id": p.id, "name": p.name, "created_at": p.created_at.isoformat()}
        for p in projects
    ]), 200


@projects_bp.route("/<project_id>", methods=["GET"])
@jwt_required()
def get_project(project_id):
    user_id = get_jwt_identity()
    project = project_service.get_project(project_id, user_id)
    if not project:
        return jsonify({"error": "project not found"}), 404
    return jsonify({
        "id": project.id, "name": project.name,
        "created_at": project.created_at.isoformat()
    }), 200


@projects_bp.route("/<project_id>", methods=["DELETE"])
@jwt_required()
def delete_project(project_id):
    user_id = get_jwt_identity()
    deleted = project_service.delete_project(project_id, user_id)
    if not deleted:
        return jsonify({"error": "project not found"}), 404
    return jsonify({"message": "deleted"}), 200