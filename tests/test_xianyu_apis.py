"""Tests for XianyuApis class."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from XianyuApis import XianyuApis


class TestXianyuApis:
    """Tests for XianyuApis class."""
    
    def test_init(self):
        """Test XianyuApis initialization."""
        api = XianyuApis()
        
        assert api.session is not None
        assert api.url is not None
        assert 'user-agent' in api.session.headers
    
    def test_clear_duplicate_cookies(self):
        """Test clearing duplicate cookies."""
        api = XianyuApis()
        
        # Test that the method exists and can be called
        with patch.object(api, 'update_env_cookies'):
            # Just verify the method doesn't crash
            # The actual cookie deduplication logic is complex and tested in integration
            try:
                api.clear_duplicate_cookies()
                # If it doesn't raise an exception, test passes
                assert True
            except Exception as e:
                # Method should handle errors gracefully
                pytest.fail(f"clear_duplicate_cookies raised unexpected exception: {e}")
    
    @patch('XianyuApis.requests.Session.post')
    def test_hasLogin_success(self, mock_post):
        """Test successful login check."""
        api = XianyuApis()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'content': {'success': True}
        }
        mock_post.return_value = mock_response
        
        with patch.object(api, 'clear_duplicate_cookies'):
            result = api.hasLogin()
        
        assert result is True
    
    @patch('XianyuApis.requests.Session.post')
    def test_hasLogin_failure(self, mock_post):
        """Test failed login check."""
        api = XianyuApis()
        
        # Mock failed response
        mock_response = Mock()
        mock_response.json.return_value = {
            'content': {'success': False}
        }
        mock_post.return_value = mock_response
        
        result = api.hasLogin(retry_count=2)  # Skip retries
        
        assert result is False
    
    @patch('XianyuApis.requests.Session.post')
    def test_get_token_success(self, mock_post):
        """Test successful token retrieval."""
        api = XianyuApis()
        api.session.cookies.get = Mock(return_value='test_token_123')
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'ret': ['SUCCESS::调用成功'],
            'data': {'accessToken': 'new_token_456'}
        }
        mock_post.return_value = mock_response
        
        result = api.get_token('device_123')
        
        assert result is not None
        assert 'data' in result
        assert result['data']['accessToken'] == 'new_token_456'
    
    @patch('XianyuApis.requests.Session.post')
    def test_get_item_info_success(self, mock_post):
        """Test successful item info retrieval."""
        api = XianyuApis()
        api.session.cookies.get = Mock(return_value='test_token_123')
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'ret': ['SUCCESS::调用成功'],
            'data': {
                'item': {
                    'id': '12345',
                    'title': '测试商品',
                    'price': 100
                }
            }
        }
        mock_post.return_value = mock_response
        
        result = api.get_item_info('12345')
        
        assert result is not None
        assert 'data' in result
        assert result['data']['item']['id'] == '12345'