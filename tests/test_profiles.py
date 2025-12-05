"""Tests for profile management."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from hqp.profiles import ProfileManager
from hqp.models import Profile


class TestProfileManager:
    """Tests for ProfileManager."""

    @pytest.fixture
    def manager(self):
        return ProfileManager(
            host="hqplayer.local",
            user="hqplayer",
            profiles_path="/var/lib/hqplayer/home/cfgs",
            config_path="/etc/hqplayer/hqplayerd.xml",
        )

    def test_init(self, manager):
        assert manager.host == "hqplayer.local"
        assert manager.user == "hqplayer"

    @pytest.mark.asyncio
    async def test_list_profiles(self, manager):
        with patch.object(manager, "_list_files", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = ["Bedroom.xml", "Living Room.xml", "Office.xml"]
            profiles = await manager.list_profiles()

            assert len(profiles) == 3
            names = [p.name for p in profiles]
            assert "Bedroom" in names
            assert "Living Room" in names
            assert "Office" in names
            mock_list.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, manager):
        with patch.object(manager, "_list_files", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []
            profiles = await manager.list_profiles()
            assert len(profiles) == 0

    @pytest.mark.asyncio
    async def test_switch_profile(self, manager):
        with patch.object(manager, "_copy_file", new_callable=AsyncMock) as mock_copy:
            with patch.object(manager, "_run_command", new_callable=AsyncMock) as mock_cmd:
                with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                    mock_copy.return_value = True
                    mock_cmd.return_value = ("", "", 0)
                    mock_wait.return_value = True
                    result = await manager.switch_profile("Bedroom")

                    assert result is True
                    mock_copy.assert_called_once()
                    mock_cmd.assert_called_once()  # systemctl restart

    @pytest.mark.asyncio
    async def test_switch_profile_with_spaces(self, manager):
        with patch.object(manager, "_copy_file", new_callable=AsyncMock) as mock_copy:
            with patch.object(manager, "_run_command", new_callable=AsyncMock) as mock_cmd:
                with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                    mock_copy.return_value = True
                    mock_cmd.return_value = ("", "", 0)
                    mock_wait.return_value = True
                    result = await manager.switch_profile("Living Room")

                    assert result is True
                    # Check the copy was called with the right paths
                    copy_call = mock_copy.call_args
                    assert "Living Room" in copy_call[0][0]

    @pytest.mark.asyncio
    async def test_switch_profile_failure(self, manager):
        with patch.object(manager, "_copy_file", new_callable=AsyncMock) as mock_copy:
            mock_copy.return_value = False
            result = await manager.switch_profile("NonExistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_current_profile(self, manager):
        # Current profile detection compares config hash to profile hashes
        with patch.object(manager, "_list_files", new_callable=AsyncMock) as mock_list:
            with patch.object(manager, "_get_file_hash", new_callable=AsyncMock) as mock_hash:
                mock_list.return_value = ["Bedroom.xml", "Living Room.xml", "Office.xml"]
                # First call is for current config, then each profile
                mock_hash.side_effect = [
                    "abc123",  # current config hash
                    "abc123",  # Bedroom.xml - matches!
                ]
                current = await manager.get_current_profile()
                assert current == "Bedroom"

    @pytest.mark.asyncio
    async def test_get_current_profile_no_match(self, manager):
        with patch.object(manager, "_list_files", new_callable=AsyncMock) as mock_list:
            with patch.object(manager, "_get_file_hash", new_callable=AsyncMock) as mock_hash:
                mock_list.return_value = ["Bedroom.xml", "Office.xml"]
                # Config hash doesn't match any profile
                mock_hash.side_effect = [
                    "xyz999",  # current config hash
                    "abc123",  # Bedroom.xml
                    "def456",  # Office.xml
                ]
                current = await manager.get_current_profile()
                assert current is None
