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
        mock_output = "Bedroom.xml\nLiving Room.xml\nOffice.xml\n"

        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            mock_ssh.return_value = (mock_output, "", 0)
            profiles = await manager.list_profiles()

            assert len(profiles) == 3
            assert profiles[0].name == "Bedroom"
            assert profiles[1].name == "Living Room"
            assert profiles[2].name == "Office"
            mock_ssh.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, manager):
        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            mock_ssh.return_value = ("", "", 0)
            profiles = await manager.list_profiles()
            assert len(profiles) == 0

    @pytest.mark.asyncio
    async def test_switch_profile(self, manager):
        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                mock_ssh.return_value = ("", "", 0)
                mock_wait.return_value = True
                result = await manager.switch_profile("Bedroom")

                assert result is True
                # Should have been called twice: cp + restart
                assert mock_ssh.call_count == 2

    @pytest.mark.asyncio
    async def test_switch_profile_with_spaces(self, manager):
        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                mock_ssh.return_value = ("", "", 0)
                mock_wait.return_value = True
                result = await manager.switch_profile("Living Room")

                assert result is True
                # Check the cp command properly quotes the path
                cp_call = mock_ssh.call_args_list[0]
                assert "Living Room" in cp_call[0][0]

    @pytest.mark.asyncio
    async def test_switch_profile_failure(self, manager):
        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            mock_ssh.return_value = ("", "cp: cannot stat: No such file", 1)
            result = await manager.switch_profile("NonExistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_get_current_profile(self, manager):
        # Current profile detection would compare config file hash to profiles
        # For now, return None if unknown
        with patch.object(manager, "_run_ssh_command", new_callable=AsyncMock) as mock_ssh:
            # Simulate md5sum output
            mock_ssh.side_effect = [
                ("abc123  /etc/hqplayer/hqplayerd.xml\n", "", 0),  # current config
                ("abc123  Bedroom.xml\ndef456  Living Room.xml\nxyz789  Office.xml\n", "", 0),  # profiles
            ]
            current = await manager.get_current_profile()
            assert current == "Bedroom"
