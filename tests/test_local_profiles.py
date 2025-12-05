"""Tests for local profile management."""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from hqp.profiles import LocalProfileManager, create_profile_manager


class TestLocalProfileManager:
    """Tests for LocalProfileManager using real filesystem in temp directory."""

    @pytest.fixture
    def test_env(self, tmp_path):
        """Create a fake HQPlayer environment in temp directory."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        config_path = config_dir / "hqplayerd.xml"

        # Create some test profiles
        bedroom_content = "<Config><Output>Bedroom DAC</Output></Config>"
        living_content = "<Config><Output>Living Room DAC</Output></Config>"
        office_content = "<Config><Output>Office DAC</Output></Config>"

        (profiles_dir / "Bedroom.xml").write_text(bedroom_content)
        (profiles_dir / "Living Room.xml").write_text(living_content)
        (profiles_dir / "Office.xml").write_text(office_content)

        # Set current config to match Bedroom
        config_path.write_text(bedroom_content)

        return {
            "profiles_path": str(profiles_dir),
            "config_path": str(config_path),
            "profiles_dir": profiles_dir,
            "config_dir": config_dir,
        }

    @pytest.fixture
    def manager(self, test_env):
        return LocalProfileManager(
            profiles_path=test_env["profiles_path"],
            config_path=test_env["config_path"],
        )

    def test_init(self, manager):
        assert manager.host == "localhost"

    @pytest.mark.asyncio
    async def test_list_profiles(self, manager):
        profiles = await manager.list_profiles()

        names = {p.name for p in profiles}
        assert "Bedroom" in names
        assert "Living Room" in names
        assert "Office" in names
        assert len(profiles) == 3

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, test_env):
        empty_dir = Path(test_env["profiles_path"]).parent / "empty"
        empty_dir.mkdir()

        manager = LocalProfileManager(
            profiles_path=str(empty_dir),
            config_path=test_env["config_path"],
        )
        profiles = await manager.list_profiles()
        assert len(profiles) == 0

    @pytest.mark.asyncio
    async def test_get_current_profile(self, manager):
        current = await manager.get_current_profile()
        assert current == "Bedroom"

    @pytest.mark.asyncio
    async def test_get_current_profile_no_match(self, manager, test_env):
        # Modify config to not match any profile
        Path(test_env["config_path"]).write_text("<Config><Output>Unknown</Output></Config>")

        current = await manager.get_current_profile()
        assert current is None

    @pytest.mark.asyncio
    async def test_switch_profile(self, manager, test_env):
        # Mock the service restart and wait
        with patch.object(manager, "_run_command", new_callable=AsyncMock) as mock_cmd:
            with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                mock_cmd.return_value = ("", "", 0)
                mock_wait.return_value = True

                result = await manager.switch_profile("Living Room")

                assert result is True

                # Verify config was copied
                config_content = Path(test_env["config_path"]).read_text()
                assert "Living Room DAC" in config_content

                # Verify systemctl restart was called
                mock_cmd.assert_called_once_with("sudo systemctl restart hqplayerd")

    @pytest.mark.asyncio
    async def test_switch_profile_nonexistent(self, manager):
        with patch.object(manager, "_run_command", new_callable=AsyncMock) as mock_cmd:
            with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                mock_cmd.return_value = ("", "", 0)
                mock_wait.return_value = True

                result = await manager.switch_profile("NonExistent")

                # Copy should fail for nonexistent profile
                assert result is False

    @pytest.mark.asyncio
    async def test_switch_profile_no_wait(self, manager, test_env):
        with patch.object(manager, "_run_command", new_callable=AsyncMock) as mock_cmd:
            with patch.object(manager, "_wait_for_hqplayer", new_callable=AsyncMock) as mock_wait:
                mock_cmd.return_value = ("", "", 0)

                result = await manager.switch_profile("Office", wait=False)

                assert result is True
                # Should not have called wait
                mock_wait.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_current_as_profile(self, manager, test_env):
        result = await manager.save_current_as_profile("New Profile")

        assert result is True

        # Verify new profile was created
        new_profile = Path(test_env["profiles_path"]) / "New Profile.xml"
        assert new_profile.exists()
        assert "Bedroom DAC" in new_profile.read_text()

    @pytest.mark.asyncio
    async def test_delete_profile(self, manager, test_env):
        # Create a profile to delete
        to_delete = Path(test_env["profiles_path"]) / "ToDelete.xml"
        to_delete.write_text("<Config/>")

        result = await manager.delete_profile("ToDelete")

        assert result is True
        assert not to_delete.exists()

    @pytest.mark.asyncio
    async def test_get_file_hash(self, manager, test_env):
        hash1 = await manager._get_file_hash(test_env["config_path"])
        hash2 = await manager._get_file_hash(str(Path(test_env["profiles_path"]) / "Bedroom.xml"))

        # Same content should have same hash
        assert hash1 == hash2
        assert hash1 is not None
        assert len(hash1) == 32  # MD5 hex digest length


class TestCreateProfileManager:
    """Tests for the factory function."""

    def test_create_ssh_manager(self):
        manager = create_profile_manager(
            mode="ssh",
            host="hqplayer.local",
            user="hqplayer",
        )
        from hqp.profiles import SSHProfileManager
        assert isinstance(manager, SSHProfileManager)
        assert manager.host == "hqplayer.local"
        assert manager.user == "hqplayer"

    def test_create_local_manager(self):
        manager = create_profile_manager(
            mode="local",
            profiles_path="/custom/profiles",
            config_path="/custom/config.xml",
        )
        from hqp.profiles import LocalProfileManager
        assert isinstance(manager, LocalProfileManager)
        assert manager.host == "localhost"
        assert manager.profiles_path == "/custom/profiles"
        assert manager.config_path == "/custom/config.xml"
