"""Assignments CRUD via Flask; data stored in Firestore."""
from flask import Blueprint, current_app, jsonify, request
from datetime import datetime, timezone

from server.fb_admin import get_firestore, verify_id_token

import os
import firebase_admin
from firebase_admin import credentials, firestore

def get_firestore():
    try:
        # Initialize only once
        if not firebase_admin._apps:
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not cred_path:
                print("Missing GOOGLE_APPLICATION_CREDENTIALS")
                return None
            firebase_admin.initialize_app(credentials.Certificate(cred_path))

        return firestore.client()
    except Exception as e:
        print("Firestore init failed:", e)
        return None


bp = Blueprint("assignments", __name__, url_prefix="")
COLLECTION = "assignments"


def _uid_from_request():
    """Return (uid, None) on success, or (None, (response, status_code)) on error."""
    auth = request.headers.get("Authorization")
    token = (auth[7:].strip() if auth and auth.startswith("Bearer ") else None) or None
    if not token:
        return None, (jsonify({"error": "Missing Authorization header"}), 401)
    claims = verify_id_token(token)
    if not claims:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)
    return claims.get("uid"), None











# @bp.route("/by-github-id", methods=["GET"])
# def get_assignments_by_github_id():
#     identity = (request.args.get("identity") or "").strip().lower()
#     current_app.logger.info("[extension] identity=%r", identity)


#     #call the firebase api to get the assignments for the user with the given github id

#     if not identity:
#         return jsonify({"identity": "", "assignments": []}), 200

#     assignments_by_user = {"iainmac32": [{"name": "a1", "id": 932},{"name": "a2", "id": 12}]}

#     assignments = assignments_by_user.get(identity, ["test1assignment"])
#     return jsonify({"identity": identity, "assignments": assignments}), 200




@bp.route("/by-github-id", methods=["GET"])
def get_assignments_by_github_id():
    identity = (request.args.get("identity") or "").strip().lower()
    current_app.logger.info("[extension] identity=%r", identity)
    print("here!")

    if not identity:
        return jsonify({"identity": "", "assignments": []}), 200

    db = get_firestore()
    if db is None:
        print("no db!")
        return jsonify({"error": "Database not configured"}), 503

    try:
        print("db:", db)
        # Query the junction table based on your schema
        invites_ref = db.collection("assignmentInvites")
        docs = invites_ref.where("githubUsername", "==", identity).stream()

        assignments_list = []
        for doc in docs:
            data = doc.to_dict()
            assignments_list.append({
                "id": data.get("assignmentId"),
                "name": data.get("assignmentName")
            })


        print("here!")
        print(jsonify({
            "assignments": assignments_list,
            "identity": identity
        }))
        # Final response matches your requested format
        return jsonify({
            "assignments": assignments_list,
            "identity": identity
        }), 200

    except Exception as e:
        current_app.logger.error("Firestore query failed: %s", e)
        return jsonify({"error": str(e)}), 500







@bp.route("/push", methods=["POST"])
def push_line_event():
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object"}), 400

    required = ["AssignmentID", "GitHubName", "GitHubLink", "FilePath", "LineNumber", "LineContent"]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": "Missing fields", "missing": missing}), 400

    db = get_firestore()
    if db is None:
        return jsonify({"error": "Database not configured"}), 503

    try:
        event_doc = {
            "assignmentId": str(payload["AssignmentID"]),   # ✅ string
            "githubUsername": str(payload["GitHubName"]).strip().lower(),
            "githubLink": str(payload.get("GitHubLink", "")),
            "filePath": str(payload["FilePath"]),
            "lineNumber": int(payload["LineNumber"]),
            "lineContent": str(payload["LineContent"]),
            "updatedAt": str(payload.get("updatedAt", "")),
        }

        doc_ref = db.collection("lineEvents").document()
        doc_ref.set(event_doc)

        return jsonify({"ok": True, "id": doc_ref.id}), 200

    except Exception as e:
        current_app.logger.exception("Push failed")
        return jsonify({"error": str(e)}), 500


















@bp.route("", methods=["GET"])
def list_assignments():
    """List assignments for the authenticated user."""
    uid, err = _uid_from_request()
    if err is not None:
        return err[0], err[1]
    db = get_firestore()
    if not db:
        return jsonify({"error": "Database not configured"}), 503
    try:
        refs = db.collection(COLLECTION).where("userId", "==", uid).stream()
        items = []
        for ref in refs:
            d = ref.to_dict()
            items.append({
                "id": ref.id,
                "name": d.get("name", ""),
                "description": d.get("description", ""),
                "createdAt": d.get("createdAt", ""),
                "dueDate": d.get("dueDate", ""),
                "isGroup": d.get("isGroup", False),
                "maxGroupSize": d.get("maxGroupSize"),
                "groups": d.get("groups", []),
            })
        items.sort(key=lambda x: x.get("dueDate", ""), reverse=True)
        current_app.logger.info("[assignments] GET fetched count=%s data=%s", len(items), items)
        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("", methods=["POST"])
def create_assignment():
    """Create an assignment."""
    uid, err = _uid_from_request()
    if err is not None:
        return err[0], err[1]
    db = get_firestore()
    if not db:
        return jsonify({"error": "Database not configured"}), 503
    body = request.get_json() or {}
    name = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()
    created_at = (body.get("createdAt") or "").strip()
    due_date = (body.get("dueDate") or "").strip()
    is_group = bool(body.get("isGroup"))
    max_group_size = body.get("maxGroupSize")
    groups = body.get("groups") or []
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not due_date:
        return jsonify({"error": "dueDate is required"}), 400
    try:
        doc_ref, _ = db.collection(COLLECTION).add({
            "userId": uid,
            "name": name,
            "description": description,
            "createdAt": created_at,
            "dueDate": due_date,
            "isGroup": is_group,
            "maxGroupSize": max_group_size if is_group else None,
            "groups": groups,
        })
        return jsonify({
            "id": doc_ref.id,
            "name": name,
            "description": description,
            "createdAt": created_at,
            "dueDate": due_date,
            "isGroup": is_group,
            "maxGroupSize": max_group_size,
            "groups": groups,
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/<assignment_id>", methods=["GET"])
def get_assignment(assignment_id):
    """Get one assignment by id (must belong to user)."""
    uid, err = _uid_from_request()
    if err is not None:
        return err[0], err[1]
    db = get_firestore()
    if not db:
        return jsonify({"error": "Database not configured"}), 503
    try:
        ref = db.collection(COLLECTION).document(assignment_id).get()
        if not ref.exists:
            return jsonify({"error": "Not found"}), 404
        d = ref.to_dict()
        if d.get("userId") != uid:
            return jsonify({"error": "Forbidden"}), 403
        return jsonify({
            "id": ref.id,
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "createdAt": d.get("createdAt", ""),
            "dueDate": d.get("dueDate", ""),
            "isGroup": d.get("isGroup", False),
            "maxGroupSize": d.get("maxGroupSize"),
            "groups": d.get("groups", []),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/<assignment_id>", methods=["PATCH"])
def update_assignment(assignment_id):
    """Update an assignment (partial)."""
    uid, err = _uid_from_request()
    if err is not None:
        return err[0], err[1]
    db = get_firestore()
    if not db:
        return jsonify({"error": "Database not configured"}), 503
    doc_ref = db.collection(COLLECTION).document(assignment_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"error": "Not found"}), 404
    if doc.to_dict().get("userId") != uid:
        return jsonify({"error": "Forbidden"}), 403
    body = request.get_json() or {}
    updates = {}
    if "name" in body:
        updates["name"] = str(body["name"]).strip()
    if "description" in body:
        updates["description"] = str(body["description"]).strip()
    if "dueDate" in body:
        updates["dueDate"] = str(body["dueDate"]).strip()
    if "groups" in body:
        updates["groups"] = body["groups"]
    if not updates:
        d = doc.to_dict()
        return jsonify({
            "id": doc.id,
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "createdAt": d.get("createdAt", ""),
            "dueDate": d.get("dueDate", ""),
            "isGroup": d.get("isGroup", False),
            "maxGroupSize": d.get("maxGroupSize"),
            "groups": d.get("groups", []),
        }), 200
    try:
        doc_ref.update(updates)
        doc = doc_ref.get()
        d = doc.to_dict()
        return jsonify({
            "id": doc.id,
            "name": d.get("name", ""),
            "description": d.get("description", ""),
            "createdAt": d.get("createdAt", ""),
            "dueDate": d.get("dueDate", ""),
            "isGroup": d.get("isGroup", False),
            "maxGroupSize": d.get("maxGroupSize"),
            "groups": d.get("groups", []),
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
