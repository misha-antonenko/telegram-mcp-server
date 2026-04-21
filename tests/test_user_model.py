"""Tests for the User model."""

from unittest.mock import MagicMock

from telegram_mcp_server.ids import encode_user_photo
from telegram_mcp_server.models.user import User


def _make_full(user_id=1, first="Alice", last="Smith", username="alice", about="Bio text", has_photo=True):
    user = MagicMock()
    user.id = user_id
    user.first_name = first
    user.last_name = last
    user.username = username
    user.photo = MagicMock() if has_photo else None

    full_user = MagicMock()
    full_user.about = about

    full = MagicMock()
    full.users = [user]
    full.full_user = full_user
    return full


class TestUserFromFull:
    def test_basic_fields(self):
        full = _make_full(user_id=5, first="Alice", last="Smith", username="alice", about="Hello")
        user = User.from_full(full)
        assert user.id == 5
        assert user.name == "Alice Smith"
        assert user.nickname == "alice"
        assert user.bio == "Hello"

    def test_profile_image_id_set(self):
        full = _make_full(user_id=5, has_photo=True)
        user = User.from_full(full)
        assert user.profile_image_id == encode_user_photo(5)

    def test_no_profile_photo(self):
        full = _make_full(has_photo=False)
        user = User.from_full(full)
        assert user.profile_image_id is None

    def test_no_bio(self):
        full = _make_full(about=None)
        user = User.from_full(full)
        assert user.bio is None

    def test_name_no_last(self):
        full = _make_full(first="Bob", last="")
        user = User.from_full(full)
        assert user.name == "Bob"

    def test_to_dict_keys(self):
        full = _make_full()
        d = User.from_full(full).to_dict()
        assert set(d.keys()) == {"id", "name", "nickname", "bio", "profile_image_id"}
