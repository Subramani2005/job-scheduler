from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.services import job_service

jobs_bp = Blueprint("jobs", __name__, url_prefix="/api/queues/<queue_id>/jobs")


@jobs_bp.route("", methods=["POST"])
@jwt_required()
def create_job(queue_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    job_type = data.get("job_type")

    if not name or not job_type:
        return jsonify({"error": "name and job_type are required"}), 400

    job = job_service.create_job(
        queue_id=queue_id,
        name=name,
        job_type=job_type,
        payload=data.get("payload"),
        priority=data.get("priority", 0),
        run_at=data.get("run_at"),
        cron_expression=data.get("cron_expression"),
        retry_policy_id=data.get("retry_policy_id"),
        idempotency_key=data.get("idempotency_key"),
    )

    return jsonify({
        "id": job.id, "name": job.name, "status": job.status,
        "priority": job.priority, "created_at": job.created_at.isoformat()
    }), 201


@jobs_bp.route("", methods=["GET"])
@jwt_required()
def list_jobs(queue_id):
    status_filter = request.args.get("status")
    jobs = job_service.get_jobs_for_queue(queue_id, status_filter)
    return jsonify([
        {"id": j.id, "name": j.name, "status": j.status,
         "priority": j.priority, "attempt_count": j.attempt_count,
         "created_at": j.created_at.isoformat()}
        for j in jobs
    ]), 200


@jobs_bp.route("/<job_id>", methods=["GET"])
@jwt_required()
def get_job(queue_id, job_id):
    job = job_service.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify({
        "id": job.id, "name": job.name, "status": job.status,
        "payload": job.payload, "priority": job.priority,
        "attempt_count": job.attempt_count,
        "run_at": job.run_at.isoformat() if job.run_at else None,
        "cron_expression": job.cron_expression
    }), 200