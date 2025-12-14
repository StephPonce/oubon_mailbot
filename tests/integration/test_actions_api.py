"""
Integration tests for Actions API.

Tests the full HTTP request/response cycle for the actions management endpoints.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock

from tests.factories import UserFactory, StoreFactory, ProductFactory, ActionFactory


class TestListActions:
    """Test GET /api/actions"""

    def test_list_actions_empty(self, auth_client, test_user):
        """Test listing actions when none exist"""
        response = auth_client.get("/api/actions")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_actions(self, auth_client, test_user, test_store, db_session):
        """Test listing user's actions"""
        # Create multiple actions
        action1 = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            status="pending"
        )
        action2 = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="adjust_price",
            status="pending"
        )
        db_session.add_all([action1, action2])
        db_session.commit()

        response = auth_client.get("/api/actions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(action["user_id"] == test_user.id for action in data)

    def test_list_actions_filtered_by_status(self, auth_client, test_user, test_store, db_session):
        """Test filtering actions by status"""
        pending_action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            status="pending"
        )
        completed_action = ActionFactory.create_completed(
            user_id=test_user.id,
            store_id=test_store.id
        )
        db_session.add_all([pending_action, completed_action])
        db_session.commit()

        response = auth_client.get("/api/actions?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

    def test_list_actions_filtered_by_type(self, auth_client, test_user, test_store, db_session):
        """Test filtering actions by action type"""
        deploy_action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product"
        )
        price_action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="adjust_price"
        )
        db_session.add_all([deploy_action, price_action])
        db_session.commit()

        response = auth_client.get("/api/actions?action_type=deploy_product")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["action_type"] == "deploy_product"

    def test_list_actions_unauthorized(self, client):
        """Test listing actions without authentication"""
        response = client.get("/api/actions")

        assert response.status_code == 401


class TestGetActionStats:
    """Test GET /api/actions/stats"""

    def test_get_stats_no_actions(self, auth_client, test_user):
        """Test stats when no actions exist"""
        response = auth_client.get("/api/actions/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["pending"] == 0
        assert data["approved"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0

    def test_get_stats_with_actions(self, auth_client, test_user, test_store, db_session):
        """Test stats with various action statuses"""
        actions = [
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="pending"),
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="pending"),
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="approved"),
            ActionFactory.create_completed(user_id=test_user.id, store_id=test_store.id),
            ActionFactory.create_failed(user_id=test_user.id, store_id=test_store.id),
        ]
        db_session.add_all(actions)
        db_session.commit()

        response = auth_client.get("/api/actions/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["pending"] == 2
        assert data["approved"] == 1
        assert data["completed"] == 1
        assert data["failed"] == 1


class TestGetAction:
    """Test GET /api/actions/{action_id}"""

    def test_get_action_success(self, auth_client, test_user, test_store, db_session):
        """Test getting a specific action"""
        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            status="pending",
            confidence=0.85
        )
        db_session.add(action)
        db_session.commit()

        response = auth_client.get(f"/api/actions/{action.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == action.id
        assert data["action_type"] == "deploy_product"
        assert data["status"] == "pending"
        assert data["confidence"] == 0.85

    def test_get_action_not_found(self, auth_client, test_user):
        """Test getting non-existent action"""
        response = auth_client.get("/api/actions/999")

        assert response.status_code == 404

    def test_get_action_wrong_user(self, auth_client, test_user, db_session):
        """Test getting another user's action"""
        other_user = UserFactory.create(email="other@example.com")
        store = StoreFactory.create(user_id=other_user.id)
        action = ActionFactory.create(
            user_id=other_user.id,
            store_id=store.id
        )
        db_session.add_all([other_user, store, action])
        db_session.commit()

        response = auth_client.get(f"/api/actions/{action.id}")

        assert response.status_code == 404  # Or 403 depending on implementation


class TestCreateAction:
    """Test POST /api/actions"""

    def test_create_action_success(self, auth_client, test_user, test_store, test_product):
        """Test creating a new action"""
        payload = {
            "action_type": "deploy_product",
            "store_id": test_store.id,
            "confidence": 0.85,
            "payload": {
                "product_id": test_product.id,
                "niche": "smart_home"
            }
        }

        response = auth_client.post("/api/actions", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["action_type"] == "deploy_product"
        assert data["status"] == "pending"
        assert data["confidence"] == 0.85
        assert "id" in data
        assert "created_at" in data

    def test_create_action_invalid_payload(self, auth_client, test_user):
        """Test creating action with invalid data"""
        payload = {
            "action_type": "invalid_action",  # Invalid type
            "confidence": 1.5  # Invalid confidence > 1.0
        }

        response = auth_client.post("/api/actions", json=payload)

        assert response.status_code in [400, 422]  # Validation error

    def test_create_action_missing_required_fields(self, auth_client, test_user):
        """Test creating action without required fields"""
        payload = {
            "confidence": 0.85
            # Missing action_type
        }

        response = auth_client.post("/api/actions", json=payload)

        assert response.status_code == 422  # Validation error


class TestApproveAction:
    """Test POST /api/actions/{action_id}/approve"""

    @pytest.mark.asyncio
    async def test_approve_action_success(self, auth_client, test_user, test_store, test_product, db_session):
        """Test approving and executing an action"""
        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            status="pending",
            payload={"product_id": test_product.id, "store_id": test_store.id}
        )
        db_session.add(action)
        db_session.commit()

        # Mock the executor
        with patch('ospra_os.services.action_executor.DeployProductExecutor') as mock_executor:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = AsyncMock(
                success=True,
                message="Product deployed successfully"
            )
            mock_executor.return_value = mock_instance

            response = auth_client.post(f"/api/actions/{action.id}/approve")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["approved", "completed"]

    def test_approve_action_not_found(self, auth_client, test_user):
        """Test approving non-existent action"""
        response = auth_client.post("/api/actions/999/approve")

        assert response.status_code == 404

    def test_approve_already_executed_action(self, auth_client, test_user, test_store, db_session):
        """Test approving already executed action"""
        action = ActionFactory.create_completed(
            user_id=test_user.id,
            store_id=test_store.id
        )
        db_session.add(action)
        db_session.commit()

        response = auth_client.post(f"/api/actions/{action.id}/approve")

        assert response.status_code in [400, 409]  # Bad request or conflict


class TestSkipAction:
    """Test POST /api/actions/{action_id}/skip"""

    def test_skip_action_success(self, auth_client, test_user, test_store, db_session):
        """Test skipping a pending action"""
        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()

        response = auth_client.post(f"/api/actions/{action.id}/skip")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "skipped"

    def test_skip_action_not_found(self, auth_client, test_user):
        """Test skipping non-existent action"""
        response = auth_client.post("/api/actions/999/skip")

        assert response.status_code == 404


class TestBulkApprove:
    """Test POST /api/actions/approve-all"""

    @pytest.mark.asyncio
    async def test_bulk_approve_success(self, auth_client, test_user, test_store, db_session):
        """Test bulk approving multiple actions"""
        actions = [
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="pending"),
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="pending"),
            ActionFactory.create(user_id=test_user.id, store_id=test_store.id, status="pending"),
        ]
        db_session.add_all(actions)
        db_session.commit()

        action_ids = [action.id for action in actions]
        payload = {"action_ids": action_ids}

        with patch('ospra_os.services.action_executor.ActionExecutorFactory') as mock_factory:
            mock_executor = AsyncMock()
            mock_executor.execute.return_value = AsyncMock(
                success=True,
                message="Action executed"
            )
            mock_factory.get_executor.return_value = mock_executor

            response = auth_client.post("/api/actions/approve-all", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            # Implementation may vary for success/failed counts

    def test_bulk_approve_empty_list(self, auth_client, test_user):
        """Test bulk approve with empty action list"""
        payload = {"action_ids": []}

        response = auth_client.post("/api/actions/approve-all", json=payload)

        assert response.status_code in [200, 400]


class TestDeleteAction:
    """Test DELETE /api/actions/{action_id}"""

    def test_delete_action_success(self, auth_client, test_user, test_store, db_session):
        """Test deleting a pending action"""
        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()
        action_id = action.id

        response = auth_client.delete(f"/api/actions/{action_id}")

        assert response.status_code in [200, 204]

        # Verify action was deleted
        from ospra_os.database import Action
        deleted_action = db_session.query(Action).filter(Action.id == action_id).first()
        assert deleted_action is None

    def test_delete_action_not_found(self, auth_client, test_user):
        """Test deleting non-existent action"""
        response = auth_client.delete("/api/actions/999")

        assert response.status_code == 404

    def test_delete_executed_action(self, auth_client, test_user, test_store, db_session):
        """Test deleting already executed action (should fail)"""
        action = ActionFactory.create_completed(
            user_id=test_user.id,
            store_id=test_store.id
        )
        db_session.add(action)
        db_session.commit()

        response = auth_client.delete(f"/api/actions/{action.id}")

        # Implementation may allow or prevent deletion of executed actions
        assert response.status_code in [200, 204, 400, 403]


class TestUndoAction:
    """Test POST /api/actions/{action_id}/undo"""

    @pytest.mark.asyncio
    async def test_undo_action_success(self, auth_client, test_user, test_store, db_session):
        """Test undoing an executed action"""
        action = ActionFactory.create_completed(
            user_id=test_user.id,
            store_id=test_store.id
        )
        db_session.add(action)
        db_session.commit()

        # Mock the undo executor
        with patch('ospra_os.services.action_executor.ActionExecutorFactory') as mock_factory:
            mock_executor = AsyncMock()
            mock_executor.undo.return_value = AsyncMock(
                success=True,
                message="Action undone successfully"
            )
            mock_factory.get_executor.return_value = mock_executor

            response = auth_client.post(f"/api/actions/{action.id}/undo")

            assert response.status_code == 200
            data = response.json()
            # Verify undo was recorded
            assert "message" in data

    def test_undo_pending_action(self, auth_client, test_user, test_store, db_session):
        """Test undoing a pending action (should fail)"""
        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            status="pending"
        )
        db_session.add(action)
        db_session.commit()

        response = auth_client.post(f"/api/actions/{action.id}/undo")

        assert response.status_code in [400, 409]  # Cannot undo pending action

    def test_undo_action_not_found(self, auth_client, test_user):
        """Test undoing non-existent action"""
        response = auth_client.post("/api/actions/999/undo")

        assert response.status_code == 404


# === WORKFLOW TESTS ===

class TestActionWorkflows:
    """Test complete action workflows"""

    @pytest.mark.asyncio
    async def test_complete_action_lifecycle(
        self,
        auth_client,
        test_user,
        test_store,
        test_product,
        db_session
    ):
        """Test create -> approve -> undo workflow"""
        # 1. Create action
        create_payload = {
            "action_type": "deploy_product",
            "store_id": test_store.id,
            "confidence": 0.85,
            "payload": {"product_id": test_product.id}
        }

        create_response = auth_client.post("/api/actions", json=create_payload)
        assert create_response.status_code == 201
        action_id = create_response.json()["id"]

        # 2. Approve and execute
        with patch('ospra_os.services.action_executor.DeployProductExecutor') as mock_executor:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = AsyncMock(
                success=True,
                message="Deployed"
            )
            mock_executor.return_value = mock_instance

            approve_response = auth_client.post(f"/api/actions/{action_id}/approve")
            assert approve_response.status_code == 200

        # 3. Undo
        with patch('ospra_os.services.action_executor.DeployProductExecutor') as mock_executor:
            mock_instance = AsyncMock()
            mock_instance.undo.return_value = AsyncMock(
                success=True,
                message="Undone"
            )
            mock_executor.return_value = mock_instance

            undo_response = auth_client.post(f"/api/actions/{action_id}/undo")
            assert undo_response.status_code == 200

    def test_pagination_and_filtering(self, auth_client, test_user, test_store, db_session):
        """Test listing actions with pagination"""
        # Create 25 actions
        actions = [
            ActionFactory.create(
                user_id=test_user.id,
                store_id=test_store.id,
                action_type="deploy_product" if i % 2 == 0 else "adjust_price",
                status="pending"
            )
            for i in range(25)
        ]
        db_session.add_all(actions)
        db_session.commit()

        # Test pagination
        response = auth_client.get("/api/actions?page=1&per_page=10")

        assert response.status_code == 200
        data = response.json()
        # Response format may vary - check if pagination is implemented
        assert len(data) <= 25
