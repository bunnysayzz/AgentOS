"""Firebase Firestore Service Layer for AgentOS Studio.

Provides unified CRUD operations across Cloud Firestore collections:
- users
- workspaces
- agents
- workflows
- tools
- prompts
- secrets
- artifacts
- telemetry_events
- audit_logs
- api_keys
- provider_configs
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from google.cloud import firestore
from app.core.firebase import get_firestore_db


class FirebaseDBService:
    def __init__(self):
        self.db: firestore.Client = get_firestore_db()

    # ─── Generic Helpers ─────────────────────────────────

    def set_document(self, collection_name: str, doc_id: str, data: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
        """Create or update a document in a collection."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "created_at" not in data:
            data["created_at"] = data["updated_at"]
        doc_ref = self.db.collection(collection_name).document(doc_id)
        doc_ref.set(data, merge=merge)
        return {"id": doc_id, **data}

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single document by ID."""
        doc = self.db.collection(collection_name).document(doc_id).get()
        if doc.exists:
            return {"id": doc.id, **doc.to_dict()}
        return None

    def delete_document(self, collection_name: str, doc_id: str) -> bool:
        """Soft or hard delete a document."""
        self.db.collection(collection_name).document(doc_id).delete()
        return True

    def query_collection(
        self,
        collection_name: str,
        filters: Optional[List[tuple]] = None,
        order_by: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query documents in a collection with filters."""
        ref = self.db.collection(collection_name)
        if filters:
            for field, op, value in filters:
                ref = ref.where(field, op, value)
        if order_by:
            ref = ref.order_by(order_by, direction=firestore.Query.DESCENDING)
        if limit:
            ref = ref.limit(limit)

        results = []
        for doc in ref.stream():
            results.append({"id": doc.id, **doc.to_dict()})
        return results

    # ─── Domain-Specific Helpers ─────────────────────────

    def save_user(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("users", user_id, user_data)

    def save_workspace(self, workspace_id: str, workspace_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("workspaces", workspace_id, workspace_data)

    def save_agent(self, agent_id: str, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("agents", agent_id, agent_data)

    def save_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("workflows", workflow_id, workflow_data)

    def save_tool(self, tool_id: str, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("tools", tool_id, tool_data)

    def save_prompt(self, prompt_id: str, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("prompts", prompt_id, prompt_data)

    def save_secret(self, secret_id: str, secret_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("secrets", secret_id, secret_data)

    def save_artifact(self, artifact_id: str, artifact_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("artifacts", artifact_id, artifact_data)

    def save_telemetry_event(self, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("telemetry_events", event_id, event_data)

    def save_audit_log(self, log_id: str, log_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.set_document("audit_logs", log_id, log_data)


firestore_db_service = FirebaseDBService()
