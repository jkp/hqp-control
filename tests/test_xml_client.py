"""Tests for HQPlayer XML client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from hqp.xml_client import HQPClient, parse_status_xml
from hqp.models import HQPStatus


# Sample XML responses from real HQPlayer
SAMPLE_STATUS_XML = '''<?xml version="1.0" encoding="utf-8"?><Status active_bits="1" active_channels="2" active_filter="poly-sinc-gauss-long" active_mode="SDM (DSD)" active_rate="22579200" active_shaper="ASDM7ECv3" apod="0" begin_min="0" begin_sec="0" clips="0" correction="0" display_position="0" filter_20k="0" input_fill="0" length="0" min="0" output_delay="0" output_fill="0" position="0" queued="0" random="0" remain_min="0" remain_sec="0" repeat="0" sec="0" state="0" total_min="0" total_sec="0" track="0" track_serial="8" tracks_total="0" transport_serial="14" volume="-21"/>'''

SAMPLE_PLAYING_STATUS_XML = '''<?xml version="1.0" encoding="utf-8"?><Status active_bits="24" active_channels="2" active_filter="poly-sinc-gauss-long" active_mode="SDM (DSD)" active_rate="22579200" active_shaper="ASDM7ECv3" apod="0" begin_min="0" begin_sec="0" clips="0" correction="0" display_position="0" filter_20k="0" input_fill="50" length="240" min="2" output_delay="0" output_fill="75" position="120" queued="5" random="0" remain_min="2" remain_sec="0" repeat="0" sec="30" state="1" total_min="4" total_sec="0" track="3" track_serial="10" tracks_total="12" transport_serial="20" volume="-15"/>'''

SAMPLE_VOLUME_OK = '''<?xml version="1.0" encoding="utf-8"?><Volume result="OK"/>'''
SAMPLE_VOLUME_ERROR = '''<?xml version="1.0" encoding="utf-8"?><Volume result="Error">clXmlElement::GetAttribute("value"): not found</Volume>'''

SAMPLE_STOP_OK = '''<?xml version="1.0" encoding="utf-8"?><Stop result="OK"/>'''
SAMPLE_PLAY_ERROR = '''<?xml version="1.0" encoding="utf-8"?><Play result="Error">clHQPlayerEngine::Play(): Empty transport</Play>'''


class TestParseStatusXml:
    """Tests for XML status parsing."""

    def test_parse_stopped_status(self):
        status = parse_status_xml(SAMPLE_STATUS_XML)
        assert isinstance(status, HQPStatus)
        assert status.state == 0
        assert status.is_stopped
        assert status.volume == -21.0
        assert status.active_filter == "poly-sinc-gauss-long"
        assert status.active_mode == "SDM (DSD)"
        assert status.active_shaper == "ASDM7ECv3"
        assert status.active_rate == 22579200

    def test_parse_playing_status(self):
        status = parse_status_xml(SAMPLE_PLAYING_STATUS_XML)
        assert status.state == 1
        assert status.is_playing
        assert status.volume == -15.0
        assert status.track == 3
        assert status.tracks_total == 12
        assert status.position == 120
        assert status.length == 240
        assert status.min == 2
        assert status.sec == 30

    def test_status_properties(self):
        status = parse_status_xml(SAMPLE_PLAYING_STATUS_XML)
        assert status.state_name == "playing"
        assert status.position_str == "2:30"
        assert status.remaining_str == "2:00"


class TestHQPClient:
    """Tests for HQPClient."""

    @pytest.fixture
    def client(self):
        return HQPClient(host="test.local")

    @pytest.mark.asyncio
    async def test_get_status(self, client):
        with patch.object(client, "_send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SAMPLE_STATUS_XML
            status = await client.get_status()
            assert status.is_stopped
            assert status.volume == -21.0
            mock_send.assert_called_once_with("<Status/>")

    @pytest.mark.asyncio
    async def test_set_volume(self, client):
        with patch.object(client, "_send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SAMPLE_VOLUME_OK
            result = await client.set_volume(-20)
            assert result is True
            mock_send.assert_called_once_with('<Volume value="-20"/>')

    @pytest.mark.asyncio
    async def test_set_volume_float(self, client):
        with patch.object(client, "_send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SAMPLE_VOLUME_OK
            result = await client.set_volume(-15.5)
            assert result is True
            mock_send.assert_called_once_with('<Volume value="-15.5"/>')

    @pytest.mark.asyncio
    async def test_stop(self, client):
        with patch.object(client, "_send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SAMPLE_STOP_OK
            result = await client.stop()
            assert result is True

    @pytest.mark.asyncio
    async def test_play_empty_transport_returns_false(self, client):
        with patch.object(client, "_send_command", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = SAMPLE_PLAY_ERROR
            result = await client.play()
            assert result is False

    @pytest.mark.asyncio
    async def test_volume_up(self, client):
        with patch.object(client, "get_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "set_volume", new_callable=AsyncMock) as mock_set:
                mock_status.return_value = HQPStatus(volume=-20)
                mock_set.return_value = True
                result = await client.volume_up()
                assert result is True
                mock_set.assert_called_once_with(-19)

    @pytest.mark.asyncio
    async def test_volume_down(self, client):
        with patch.object(client, "get_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "set_volume", new_callable=AsyncMock) as mock_set:
                mock_status.return_value = HQPStatus(volume=-20)
                mock_set.return_value = True
                result = await client.volume_down()
                assert result is True
                mock_set.assert_called_once_with(-21)

    @pytest.mark.asyncio
    async def test_volume_up_respects_max(self, client):
        with patch.object(client, "get_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "set_volume", new_callable=AsyncMock) as mock_set:
                mock_status.return_value = HQPStatus(volume=0)
                mock_set.return_value = True
                result = await client.volume_up()
                assert result is True
                mock_set.assert_called_once_with(0)  # Should not exceed 0

    @pytest.mark.asyncio
    async def test_volume_down_respects_min(self, client):
        with patch.object(client, "get_status", new_callable=AsyncMock) as mock_status:
            with patch.object(client, "set_volume", new_callable=AsyncMock) as mock_set:
                mock_status.return_value = HQPStatus(volume=-40)
                mock_set.return_value = True
                result = await client.volume_down()
                assert result is True
                mock_set.assert_called_once_with(-40)  # Should not go below -40
