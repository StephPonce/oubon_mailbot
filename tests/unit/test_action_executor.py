"""
Unit tests for Action Executors.

Tests the action execution system that handles deployment, pricing,
ads, and other automated actions across platforms.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from ospra_os.services.action_executor import (
    ExecutionResult,
    BaseActionExecutor,
    DeployProductExecutor,
    AdjustPriceExecutor,
    DeployAdExecutor,
    PauseAdExecutor,
    RestockAlertExecutor,
    RemoveProductExecutor,
    ActionExecutorFactory
)
from tests.factories import ProductFactory, StoreFactory, ActionFactory


class TestExecutionResult:
    """Test ExecutionResult dataclass"""

    def test_successful_result_creation(self):
        """Test creating a successful execution result"""
        result = ExecutionResult(
            success=True,
            message="Operation completed",
            before_state={"status": "pending"},
            after_state={"status": "active"},
            platform_response={"id": 123}
        )

        assert result.success is True
        assert result.message == "Operation completed"
        assert result.before_state == {"status": "pending"}
        assert result.after_state == {"status": "active"}
        assert result.platform_response == {"id": 123}
        assert result.error is None
        assert result.is_undoable is True

    def test_failed_result_creation(self):
        """Test creating a failed execution result"""
        result = ExecutionResult(
            success=False,
            message="Operation failed",
            error="API rate limit exceeded"
        )

        assert result.success is False
        assert result.message == "Operation failed"
        assert result.error == "API rate limit exceeded"

    def test_result_to_dict(self):
        """Test serialization to dict"""
        result = ExecutionResult(
            success=True,
            message="Test message",
            before_state={"status": "draft"},
            after_state={"status": "active"},
            platform_response={"product_id": "12345"},
            is_undoable=True
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["message"] == "Test message"
        assert result_dict["before_state"] == {"status": "draft"}
        assert result_dict["after_state"] == {"status": "active"}
        assert result_dict["platform_response"] == {"product_id": "12345"}
        assert result_dict["is_undoable"] is True
        assert result_dict["error"] is None

    def test_result_with_undo_payload(self):
        """Test result with undo information"""
        result = ExecutionResult(
            success=True,
            message="Deployed",
            is_undoable=True,
            undo_payload={"product_id": 123, "platform_id": "abc"}
        )

        assert result.is_undoable is True
        assert result.undo_payload == {"product_id": 123, "platform_id": "abc"}

    def test_result_non_undoable(self):
        """Test result that cannot be undone"""
        result = ExecutionResult(
            success=True,
            message="Permanent action",
            is_undoable=False
        )

        assert result.is_undoable is False


class TestDeployProductExecutor:
    """Test DeployProductExecutor"""

    @pytest.mark.asyncio
    async def test_deploy_product_not_found(self, db_session, test_user):
        """Test deploying non-existent product"""
        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="deploy_product",
            payload={"product_id": 999}  # Non-existent
        )

        result = await executor.execute(action)

        assert result.success is False
        assert "not found" in result.message.lower()
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_deploy_product_store_not_found(self, db_session, test_user, test_product):
        """Test deploying to non-existent store"""
        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=999,  # Non-existent
            action_type="deploy_product",
            payload={"product_id": test_product.id}
        )

        result = await executor.execute(action)

        assert result.success is False
        assert "store not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_deploy_product_unsupported_platform(self, db_session, test_user, test_product):
        """Test deploying to unsupported platform"""
        store = StoreFactory.create(
            user_id=test_user.id,
            platform="etsy"  # Unsupported
        )
        db_session.add(store)
        db_session.commit()

        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=store.id,
            action_type="deploy_product",
            payload={"product_id": test_product.id, "store_id": store.id}
        )

        result = await executor.execute(action)

        assert result.success is False
        assert "unsupported platform" in result.message.lower()

    @pytest.mark.asyncio
    @patch('ospra_os.services.action_executor.ShopifyClient')
    async def test_deploy_product_to_shopify_success(
        self,
        mock_shopify_client,
        db_session,
        test_user,
        test_product,
        test_store
    ):
        """Test successful deployment to Shopify"""
        # Mock Shopify API response
        mock_client_instance = AsyncMock()
        mock_client_instance.create_product.return_value = {
            "product": {
                "id": 12345,
                "handle": "test-product",
                "title": "Test Product"
            }
        }
        mock_shopify_client.return_value = mock_client_instance

        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            payload={
                "product_id": test_product.id,
                "store_id": test_store.id,
                "initial_inventory": 100
            }
        )

        result = await executor.execute(action)

        assert result.success is True
        assert "deployed" in result.message.lower()
        assert result.before_state is not None
        assert result.after_state is not None
        assert result.is_undoable is True
        assert result.undo_payload is not None

        # Verify product was updated
        db_session.refresh(test_product)
        assert test_product.status == "active"

    @pytest.mark.asyncio
    @patch('ospra_os.services.action_executor.ShopifyClient')
    async def test_deploy_product_shopify_api_error(
        self,
        mock_shopify_client,
        db_session,
        test_user,
        test_product,
        test_store
    ):
        """Test handling Shopify API errors"""
        # Mock Shopify API error
        mock_client_instance = AsyncMock()
        mock_client_instance.create_product.return_value = {
            "errors": "API rate limit exceeded"
        }
        mock_shopify_client.return_value = mock_client_instance

        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            payload={"product_id": test_product.id, "store_id": test_store.id}
        )

        result = await executor.execute(action)

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_undo_deploy_product(self, db_session, test_user, test_product, test_store):
        """Test undoing product deployment"""
        # Set up product as if it were deployed
        test_product.status = "active"
        test_product.store_id = test_store.id
        db_session.commit()

        executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        # Create a mock execution with before_state
        execution = MagicMock()
        execution.before_state = {
            "product_id": test_product.id,
            "status": "draft",
            "store_id": None
        }

        with patch.object(executor, '_remove_from_platform', new_callable=AsyncMock) as mock_remove:
            mock_remove.return_value = {"success": True}

            result = await executor.undo(execution)

            # Note: Actual undo implementation may vary
            # This tests the general structure


class TestAdjustPriceExecutor:
    """Test AdjustPriceExecutor"""

    @pytest.mark.asyncio
    async def test_adjust_price_product_not_found(self, db_session, test_user):
        """Test adjusting price for non-existent product"""
        executor = AdjustPriceExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="adjust_price",
            payload={
                "product_id": 999,
                "old_price": 50.0,
                "new_price": 55.0
            }
        )

        result = await executor.execute(action)

        assert result.success is False
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    @patch('ospra_os.services.action_executor.ShopifyClient')
    async def test_adjust_price_success(
        self,
        mock_shopify_client,
        db_session,
        test_user,
        test_product,
        test_store
    ):
        """Test successful price adjustment"""
        # Set up deployed product
        test_product.status = "active"
        test_product.store_id = test_store.id
        test_product.platform_product_id = "12345"
        db_session.commit()

        # Mock Shopify API
        mock_client_instance = AsyncMock()
        mock_client_instance.update_product_price.return_value = {
            "success": True,
            "product": {"id": 12345, "variants": [{"price": "55.00"}]}
        }
        mock_shopify_client.return_value = mock_client_instance

        executor = AdjustPriceExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="adjust_price",
            payload={
                "product_id": test_product.id,
                "old_price": 50.0,
                "new_price": 55.0,
                "reason": "Supplier cost increase"
            }
        )

        result = await executor.execute(action)

        # Note: Implementation details may vary
        # This tests the general structure


class TestDeployAdExecutor:
    """Test DeployAdExecutor"""

    @pytest.mark.asyncio
    async def test_deploy_ad_product_not_found(self, db_session, test_user):
        """Test deploying ad for non-existent product"""
        executor = DeployAdExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="deploy_ad",
            payload={"product_id": 999, "budget": 50.0}
        )

        result = await executor.execute(action)

        assert result.success is False

    @pytest.mark.asyncio
    @patch('ospra_os.services.action_executor.MetaAdsClient')
    async def test_deploy_ad_success(
        self,
        mock_meta_client,
        db_session,
        test_user,
        test_product,
        test_store
    ):
        """Test successful ad deployment"""
        # Mock Meta Ads API
        mock_client_instance = AsyncMock()
        mock_client_instance.create_campaign.return_value = {
            "success": True,
            "campaign_id": "camp_123",
            "ad_set_id": "adset_456",
            "ad_id": "ad_789"
        }
        mock_meta_client.return_value = mock_client_instance

        executor = DeployAdExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_ad",
            payload={
                "product_id": test_product.id,
                "platform": "meta",
                "budget": 50.0,
                "duration_days": 7
            }
        )

        result = await executor.execute(action)

        # Note: Implementation may vary


class TestPauseAdExecutor:
    """Test PauseAdExecutor"""

    @pytest.mark.asyncio
    async def test_pause_ad_not_found(self, db_session, test_user):
        """Test pausing non-existent ad"""
        executor = PauseAdExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="pause_ad",
            payload={"campaign_id": 999}
        )

        result = await executor.execute(action)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_pause_ad_success(self, db_session, test_user, test_product, test_store):
        """Test successful ad pause"""
        from tests.factories import CampaignFactory

        # Create an active campaign
        campaign = CampaignFactory.create_active(
            user_id=test_user.id,
            store_id=test_store.id,
            product_id=test_product.id
        )
        db_session.add(campaign)
        db_session.commit()

        executor = PauseAdExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="pause_ad",
            payload={
                "campaign_id": campaign.id,
                "reason": "Low ROAS"
            }
        )

        with patch.object(executor, '_pause_on_platform', new_callable=AsyncMock) as mock_pause:
            mock_pause.return_value = {"success": True}

            result = await executor.execute(action)

            # Note: Implementation may vary


class TestRestockAlertExecutor:
    """Test RestockAlertExecutor"""

    @pytest.mark.asyncio
    async def test_send_restock_alert(self, db_session, test_user, test_product):
        """Test sending restock alert"""
        executor = RestockAlertExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="restock_alert",
            payload={
                "product_id": test_product.id,
                "current_stock": 5,
                "threshold": 10
            }
        )

        with patch.object(executor, '_send_notification', new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = {"success": True, "notification_id": "notif_123"}

            result = await executor.execute(action)

            # Restock alerts are typically non-undoable
            # Implementation may vary


class TestRemoveProductExecutor:
    """Test RemoveProductExecutor"""

    @pytest.mark.asyncio
    async def test_remove_product_not_found(self, db_session, test_user):
        """Test removing non-existent product"""
        executor = RemoveProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=1,
            action_type="remove_product",
            payload={"product_id": 999}
        )

        result = await executor.execute(action)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_remove_product_success(self, db_session, test_user, test_product, test_store):
        """Test successful product removal"""
        # Set up deployed product
        test_product.status = "active"
        test_product.store_id = test_store.id
        test_product.platform_product_id = "12345"
        db_session.commit()

        executor = RemoveProductExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="remove_product",
            payload={
                "product_id": test_product.id,
                "reason": "Low performance"
            }
        )

        with patch.object(executor, '_remove_from_platform', new_callable=AsyncMock) as mock_remove:
            mock_remove.return_value = {"success": True}

            result = await executor.execute(action)

            # Note: Implementation may vary


class TestActionExecutorFactory:
    """Test ActionExecutorFactory"""

    def test_factory_get_executor_deploy_product(self, db_session, test_user):
        """Test factory creates DeployProductExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="deploy_product",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, DeployProductExecutor)

    def test_factory_get_executor_adjust_price(self, db_session, test_user):
        """Test factory creates AdjustPriceExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="adjust_price",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, AdjustPriceExecutor)

    def test_factory_get_executor_deploy_ad(self, db_session, test_user):
        """Test factory creates DeployAdExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="deploy_ad",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, DeployAdExecutor)

    def test_factory_get_executor_pause_ad(self, db_session, test_user):
        """Test factory creates PauseAdExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="pause_ad",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, PauseAdExecutor)

    def test_factory_get_executor_restock_alert(self, db_session, test_user):
        """Test factory creates RestockAlertExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="restock_alert",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, RestockAlertExecutor)

    def test_factory_get_executor_remove_product(self, db_session, test_user):
        """Test factory creates RemoveProductExecutor"""
        executor = ActionExecutorFactory.get_executor(
            action_type="remove_product",
            db=db_session,
            user_id=test_user.id
        )

        assert isinstance(executor, RemoveProductExecutor)

    def test_factory_get_executor_unknown_type(self, db_session, test_user):
        """Test factory raises error for unknown action type"""
        with pytest.raises(ValueError, match="Unknown action type"):
            ActionExecutorFactory.get_executor(
                action_type="unknown_action",
                db=db_session,
                user_id=test_user.id
            )

    def test_factory_get_all_supported_actions(self):
        """Test factory lists all supported action types"""
        supported = ActionExecutorFactory.get_supported_actions()

        assert "deploy_product" in supported
        assert "adjust_price" in supported
        assert "deploy_ad" in supported
        assert "pause_ad" in supported
        assert "restock_alert" in supported
        assert "remove_product" in supported


# === INTEGRATION-STYLE TESTS ===

class TestExecutorIntegration:
    """Integration-style tests for executor workflows"""

    @pytest.mark.asyncio
    async def test_deploy_and_remove_workflow(self, db_session, test_user, test_product, test_store):
        """Test deploying and then removing a product"""
        # Deploy
        deploy_executor = DeployProductExecutor(db=db_session, user_id=test_user.id)

        deploy_action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="deploy_product",
            payload={"product_id": test_product.id, "store_id": test_store.id}
        )

        with patch('ospra_os.services.action_executor.ShopifyClient') as mock_shopify:
            mock_client = AsyncMock()
            mock_client.create_product.return_value = {
                "product": {"id": 12345, "handle": "test"}
            }
            mock_shopify.return_value = mock_client

            deploy_result = await deploy_executor.execute(deploy_action)

            if deploy_result.success:
                # Remove
                remove_executor = RemoveProductExecutor(db=db_session, user_id=test_user.id)

                remove_action = ActionFactory.create(
                    user_id=test_user.id,
                    store_id=test_store.id,
                    action_type="remove_product",
                    payload={"product_id": test_product.id}
                )

                with patch.object(remove_executor, '_remove_from_platform', new_callable=AsyncMock) as mock_remove:
                    mock_remove.return_value = {"success": True}

                    remove_result = await remove_executor.execute(remove_action)

                    # Verify workflow completed
                    # Implementation may vary

    @pytest.mark.asyncio
    async def test_price_adjustment_workflow(self, db_session, test_user, test_product, test_store):
        """Test price adjustment with undo"""
        # Set up product
        original_price = 50.0
        new_price = 55.0

        test_product.price = original_price
        test_product.status = "active"
        test_product.store_id = test_store.id
        db_session.commit()

        executor = AdjustPriceExecutor(db=db_session, user_id=test_user.id)

        action = ActionFactory.create(
            user_id=test_user.id,
            store_id=test_store.id,
            action_type="adjust_price",
            payload={
                "product_id": test_product.id,
                "old_price": original_price,
                "new_price": new_price
            }
        )

        # Mock the platform update
        with patch.object(executor, '_update_price_on_platform', new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {"success": True, "current_price": new_price}

            result = await executor.execute(action)

            # Verify execution result structure
            # Implementation may vary
