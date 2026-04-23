"""
Tests for Actions Queue API Routes
===================================

Tests for the AI action queue endpoints.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from ospra_os.database.action_models import Action, AIActionType, AIActionStatus


class TestGetActions:
    """Tests for GET /api/actions endpoint"""

    @pytest.fixture
    def sample_action(self, db_session, test_user):
        """Create a sample action for testing"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Deploy Test Product",
            description="Test product deployment",
            confidence=85.5,
            rationale="High demand detected",
            factors=[{"label": "Sales Velocity", "value": 0.8}],
            payload={"product_id": 123, "store_id": 1},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)
        return action

    def test_get_actions_empty(self, auth_client, db_session, test_user):
        """Test getting actions when none exist"""
        response = auth_client.get("/api/actions")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["total"] == 0

    def test_get_actions_with_data(self, auth_client, db_session, test_user, sample_action):
        """Test getting actions with data"""
        response = auth_client.get("/api/actions")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Deploy Test Product"
        assert data["total"] == 1

    def test_get_actions_pagination(self, auth_client, db_session, test_user):
        """Test actions pagination"""
        # Create 25 actions
        for i in range(25):
            action = Action(
                user_id=test_user.id,
                action_type=AIActionType.DEPLOY_PRODUCT,
                title=f"Action {i}",
                confidence=50.0,
                rationale="Test",
                payload={},
                status=AIActionStatus.PENDING,
            )
            db_session.add(action)
        db_session.commit()

        # Get first page
        response = auth_client.get("/api/actions?page=1&per_page=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10
        assert data["total"] == 25
        assert data["total_pages"] == 3
        assert data["has_next"] is True
        assert data["has_prev"] is False

        # Get second page
        response = auth_client.get("/api/actions?page=2&per_page=10")
        data = response.json()
        assert len(data["data"]) == 10
        assert data["has_next"] is True
        assert data["has_prev"] is True

    def test_filter_by_status(self, auth_client, db_session, test_user):
        """Test filtering actions by status"""
        # Create pending and executed actions
        pending = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Pending Action",
            confidence=50.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.PENDING,
        )
        executed = Action(
            user_id=test_user.id,
            action_type=AIActionType.ADJUST_PRICE,
            title="Executed Action",
            confidence=60.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.EXECUTED,
        )
        db_session.add_all([pending, executed])
        db_session.commit()

        # Filter by pending
        response = auth_client.get("/api/actions?status=pending")
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "Pending Action"

    def test_filter_by_min_confidence(self, auth_client, db_session, test_user):
        """Test filtering actions by minimum confidence"""
        low_confidence = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Low Confidence",
            confidence=40.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.PENDING,
        )
        high_confidence = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="High Confidence",
            confidence=90.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.PENDING,
        )
        db_session.add_all([low_confidence, high_confidence])
        db_session.commit()

        response = auth_client.get("/api/actions?min_confidence=80")
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["title"] == "High Confidence"


class TestGetActionStats:
    """Tests for GET /api/actions/stats endpoint"""

    def test_stats_empty(self, auth_client, db_session, test_user):
        """Test stats when no actions exist"""
        response = auth_client.get("/api/actions/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 0
        assert data["executed"] == 0
        assert data["avg_confidence"] == 0.0

    def test_stats_with_data(self, auth_client, db_session, test_user):
        """Test stats with various action statuses"""
        # Create actions with different statuses
        for status in [AIActionStatus.PENDING, AIActionStatus.PENDING, AIActionStatus.EXECUTED]:
            action = Action(
                user_id=test_user.id,
                action_type=AIActionType.DEPLOY_PRODUCT,
                title="Test Action",
                confidence=75.0,
                rationale="Test",
                payload={},
                status=status,
            )
            db_session.add(action)
        db_session.commit()

        response = auth_client.get("/api/actions/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] == 2
        assert data["executed"] == 1
        assert data["avg_confidence"] == 75.0


class TestGetSingleAction:
    """Tests for GET /api/actions/{id} endpoint"""

    def test_get_existing_action(self, auth_client, db_session, test_user):
        """Test getting an existing action"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Test Action",
            confidence=85.0,
            rationale="Test rationale",
            payload={"key": "value"},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)

        response = auth_client.get(f"/api/actions/{action.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Action"
        assert data["confidence"] == 85.0

    def test_get_nonexistent_action(self, auth_client, db_session, test_user):
        """Test getting a non-existent action"""
        response = auth_client.get("/api/actions/99999")

        assert response.status_code == 404


class TestCreateAction:
    """Tests for POST /api/actions endpoint"""

    def test_create_action(self, auth_client, db_session, test_user):
        """Test creating a new action"""
        action_data = {
            "action_type": "deploy_product",
            "title": "Deploy New Product",
            "description": "Deploy trending product to store",
            "confidence": 92.5,
            "rationale": "High search volume and low competition",
            "factors": [
                {"label": "Search Volume", "value": 0.9},
                {"label": "Competition", "value": -0.2}
            ],
            "payload": {
                "product_name": "Test Product",
                "aliexpress_url": "https://aliexpress.com/item/123"
            },
            "estimated_impact": "+$500 revenue/week"
        }

        response = auth_client.post("/api/actions", json=action_data)

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Deploy New Product"
        assert data["confidence"] == 92.5
        assert data["status"] == "pending"

    def test_create_action_validation(self, auth_client, db_session, test_user):
        """Test validation when creating action"""
        # Missing required fields
        response = auth_client.post("/api/actions", json={
            "action_type": "deploy_product"
        })

        assert response.status_code == 422  # Validation error


class TestApproveAction:
    """Tests for POST /api/actions/{id}/approve endpoint"""

    @pytest.fixture
    def pending_action(self, db_session, test_user):
        """Create a pending action"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Pending Action",
            confidence=85.0,
            rationale="Test",
            payload={"product_name": "Test"},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)
        return action

    @patch('ospra_os.api.actions_routes.execute_action')
    async def test_approve_action(self, mock_execute, auth_client, db_session, test_user, pending_action):
        """Test approving an action"""
        mock_execute.return_value = {"success": True, "message": "Deployed"}

        response = auth_client.post(f"/api/actions/{pending_action.id}/approve")

        assert response.status_code == 200
        data = response.json()
        assert "approved" in data["message"].lower() or "executed" in data["message"].lower()

    def test_approve_nonexistent_action(self, auth_client, db_session, test_user):
        """Test approving a non-existent action"""
        response = auth_client.post("/api/actions/99999/approve")

        assert response.status_code == 404


class TestSkipAction:
    """Tests for POST /api/actions/{id}/skip endpoint"""

    def test_skip_action(self, auth_client, db_session, test_user):
        """Test skipping an action"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Action to Skip",
            confidence=50.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)

        response = auth_client.post(f"/api/actions/{action.id}/skip?reason=Not interested")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Action skipped"

        # Verify status changed
        db_session.refresh(action)
        assert action.status == AIActionStatus.SKIPPED


class TestUpdateAction:
    """Tests for PUT /api/actions/{id} endpoint"""

    def test_update_action_payload(self, auth_client, db_session, test_user):
        """Test updating action payload"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.ADJUST_PRICE,
            title="Adjust Price",
            confidence=80.0,
            rationale="Test",
            payload={"price": 29.99},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)

        response = auth_client.put(
            f"/api/actions/{action.id}",
            json={"payload": {"price": 24.99}, "title": "Updated Title"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["payload"]["price"] == 24.99
        assert data["title"] == "Updated Title"

    def test_cannot_update_executed_action(self, auth_client, db_session, test_user):
        """Test that executed actions cannot be updated"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Executed Action",
            confidence=90.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.EXECUTED,
        )
        db_session.add(action)
        db_session.commit()
        db_session.refresh(action)

        response = auth_client.put(
            f"/api/actions/{action.id}",
            json={"payload": {"new": "data"}}
        )

        assert response.status_code == 400


class TestDeleteAction:
    """Tests for DELETE /api/actions/{id} endpoint"""

    def test_delete_action(self, auth_client, db_session, test_user):
        """Test deleting an action"""
        action = Action(
            user_id=test_user.id,
            action_type=AIActionType.DEPLOY_PRODUCT,
            title="Action to Delete",
            confidence=50.0,
            rationale="Test",
            payload={},
            status=AIActionStatus.PENDING,
        )
        db_session.add(action)
        db_session.commit()
        action_id = action.id

        response = auth_client.delete(f"/api/actions/{action_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Action deleted"

        # Verify action is deleted
        deleted = db_session.query(Action).filter(Action.id == action_id).first()
        assert deleted is None


class TestBulkApprove:
    """Tests for POST /api/actions/approve-all endpoint"""

    @patch('ospra_os.api.actions_routes.execute_action')
    async def test_bulk_approve_high_confidence(self, mock_execute, auth_client, db_session, test_user):
        """Test bulk approving high confidence actions"""
        mock_execute.return_value = {"success": True}

        # Create actions with varying confidence
        for confidence in [95.0, 90.0, 70.0, 50.0]:
            action = Action(
                user_id=test_user.id,
                action_type=AIActionType.DEPLOY_PRODUCT,
                title=f"Action {confidence}",
                confidence=confidence,
                rationale="Test",
                payload={},
                status=AIActionStatus.PENDING,
            )
            db_session.add(action)
        db_session.commit()

        # Approve all with confidence >= 85
        response = auth_client.post("/api/actions/approve-all?confidence_threshold=85")

        assert response.status_code == 200
        data = response.json()
        assert data["approved_count"] == 2  # 95.0 and 90.0
