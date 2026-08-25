"""/api/learning/* must derive identity from the token, never from the request.

Router-level auth (65ca7cc) closed anonymous access, but every handler still
took `user_id` from the URL or request body — so ANY authenticated tenant could
read another tenant's model weights, and worse, WRITE into another tenant's
learning model (feedback, ad metrics, personal learning) and steer their
product scoring.

These tests inspect the actual handler signatures and source, so they fail if
someone reintroduces a caller-supplied identity.
"""

import inspect

from ospra_os.learning import learning_routes as lr


def _src(fn):
    return inspect.getsource(fn)


def test_write_endpoints_take_no_caller_supplied_user_id():
    """A WRITE keyed on a caller-supplied user_id is the dangerous case."""
    for fn in (lr.record_ad_performance,):
        params = inspect.signature(fn).parameters
        assert "user_id" not in params, (
            f"{fn.__name__} accepts a caller-supplied user_id — a caller could "
            "write into another tenant's learning model"
        )


def test_write_endpoints_use_the_token_identity():
    for fn in (lr.record_feedback, lr.record_ad_performance,
               lr.learn_personal, lr.contribute_to_global,
               lr.set_custom_weights):
        src = _src(fn)
        assert "current_user.id" in src, f"{fn.__name__} must key on the token's user"
        assert "request.user_id" not in src, (
            f"{fn.__name__} still reads user_id from the request body"
        )


def test_path_param_endpoints_override_with_token_identity():
    """These keep the path param for URL compatibility but must ignore it."""
    for fn in (lr.get_personal_weights, lr.get_learning_insights,
               lr.trigger_personal_analysis):
        src = _src(fn)
        assert "user_id = current_user.id" in src, (
            f"{fn.__name__} must reassign user_id from the token before use"
        )


def test_every_handler_receives_current_user():
    """No learning handler should be able to run without an identity."""
    handlers = [
        lr.get_personal_weights, lr.get_learning_insights,
        lr.trigger_personal_analysis, lr.record_feedback,
        lr.record_ad_performance, lr.learn_personal,
        lr.contribute_to_global, lr.get_adjusted_score,
        lr.get_learning_report, lr.set_custom_weights,
    ]
    for fn in handlers:
        assert "current_user" in inspect.signature(fn).parameters, (
            f"{fn.__name__} has no current_user parameter"
        )
