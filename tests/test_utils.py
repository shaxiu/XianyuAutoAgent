"""Tests for utility functions in utils/xianyu_utils.py"""
import pytest
import time
import hashlib
from utils.xianyu_utils import (
    trans_cookies,
    generate_mid,
    generate_uuid,
    generate_device_id,
    generate_sign,
    MessagePackDecoder
)


class TestTransCookies:
    """Tests for trans_cookies function."""
    
    def test_trans_cookies_basic(self):
        """Test basic cookie parsing."""
        cookies_str = "unb=123456; cookie2=abcdef; _m_h5_tk=token123"
        result = trans_cookies(cookies_str)
        
        assert isinstance(result, dict)
        assert result['unb'] == '123456'
        assert result['cookie2'] == 'abcdef'
        assert result['_m_h5_tk'] == 'token123'
    
    def test_trans_cookies_with_equals_in_value(self):
        """Test cookie parsing with equals sign in value."""
        cookies_str = "key1=value1; key2=value=with=equals"
        result = trans_cookies(cookies_str)
        
        assert result['key1'] == 'value1'
        assert result['key2'] == 'value=with=equals'
    
    def test_trans_cookies_empty_string(self):
        """Test empty cookie string."""
        result = trans_cookies("")
        assert result == {}
    
    def test_trans_cookies_malformed(self):
        """Test malformed cookie string."""
        cookies_str = "invalid_cookie_format"
        result = trans_cookies(cookies_str)
        # Should handle gracefully without crashing
        assert isinstance(result, dict)


class TestGenerateMid:
    """Tests for generate_mid function."""
    
    def test_generate_mid_format(self):
        """Test mid generation format."""
        mid = generate_mid()
        
        assert isinstance(mid, str)
        assert mid.endswith(" 0")
        # Should contain timestamp
        assert len(mid) > 10
    
    def test_generate_mid_uniqueness(self):
        """Test that consecutive calls generate different mids."""
        mid1 = generate_mid()
        time.sleep(0.001)
        mid2 = generate_mid()
        
        assert mid1 != mid2


class TestGenerateUuid:
    """Tests for generate_uuid function."""
    
    def test_generate_uuid_format(self):
        """Test uuid generation format."""
        uuid = generate_uuid()
        
        assert isinstance(uuid, str)
        assert uuid.startswith("-")
        assert uuid.endswith("1")
    
    def test_generate_uuid_uniqueness(self):
        """Test that consecutive calls generate different uuids."""
        uuid1 = generate_uuid()
        time.sleep(0.001)
        uuid2 = generate_uuid()
        
        assert uuid1 != uuid2


class TestGenerateDeviceId:
    """Tests for generate_device_id function."""
    
    def test_generate_device_id_format(self):
        """Test device ID generation format."""
        user_id = "test_user_123"
        device_id = generate_device_id(user_id)
        
        assert isinstance(device_id, str)
        assert device_id.endswith(f"-{user_id}")
        # UUID format: 8-4-4-4-12 characters
        assert len(device_id) == 36 + 1 + len(user_id)  # 36 for UUID + 1 for dash + user_id
    
    def test_generate_device_id_contains_user_id(self):
        """Test that device ID contains user ID."""
        user_id = "12345"
        device_id = generate_device_id(user_id)
        
        assert user_id in device_id
    
    def test_generate_device_id_has_correct_structure(self):
        """Test device ID has UUID-like structure."""
        device_id = generate_device_id("test")
        parts = device_id.rsplit("-", 1)[0]  # Remove user_id part
        
        # Check for dashes at correct positions
        assert parts[8] == "-"
        assert parts[13] == "-"
        assert parts[18] == "-"
        assert parts[23] == "-"
        # Check for '4' at position 14 (UUID version 4)
        assert parts[14] == "4"


class TestGenerateSign:
    """Tests for generate_sign function."""
    
    def test_generate_sign_format(self):
        """Test sign generation format."""
        t = "1234567890"
        token = "test_token"
        data = '{"key":"value"}'
        
        sign = generate_sign(t, token, data)
        
        assert isinstance(sign, str)
        assert len(sign) == 32  # MD5 hash length
    
    def test_generate_sign_consistency(self):
        """Test that same inputs generate same sign."""
        t = "1234567890"
        token = "test_token"
        data = '{"key":"value"}'
        
        sign1 = generate_sign(t, token, data)
        sign2 = generate_sign(t, token, data)
        
        assert sign1 == sign2
    
    def test_generate_sign_different_inputs(self):
        """Test that different inputs generate different signs."""
        t = "1234567890"
        token = "test_token"
        data1 = '{"key":"value1"}'
        data2 = '{"key":"value2"}'
        
        sign1 = generate_sign(t, token, data1)
        sign2 = generate_sign(t, token, data2)
        
        assert sign1 != sign2
    
    def test_generate_sign_matches_expected(self):
        """Test sign generation matches expected MD5."""
        t = "1234567890"
        token = "token"
        data = "data"
        app_key = "34839810"
        
        expected_msg = f"{token}&{t}&{app_key}&{data}"
        expected_sign = hashlib.md5(expected_msg.encode('utf-8')).hexdigest()
        
        actual_sign = generate_sign(t, token, data)
        
        assert actual_sign == expected_sign


class TestMessagePackDecoder:
    """Tests for MessagePackDecoder class."""
    
    def test_decode_positive_fixint(self):
        """Test decoding positive fixint."""
        data = bytes([0x05])  # 5
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result == 5
    
    def test_decode_nil(self):
        """Test decoding nil."""
        data = bytes([0xc0])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result is None
    
    def test_decode_false(self):
        """Test decoding false."""
        data = bytes([0xc2])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result is False
    
    def test_decode_true(self):
        """Test decoding true."""
        data = bytes([0xc3])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result is True
    
    def test_decode_fixstr(self):
        """Test decoding fixstr."""
        # 0xa3 = fixstr with length 3, followed by "abc"
        data = bytes([0xa3, 0x61, 0x62, 0x63])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result == "abc"
    
    def test_decode_negative_fixint(self):
        """Test decoding negative fixint."""
        data = bytes([0xff])  # -1
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result == -1
    
    def test_decode_unexpected_end(self):
        """Test handling of unexpected end of data."""
        data = bytes([0xa5])  # fixstr length 5, but no data
        decoder = MessagePackDecoder(data)
        
        # The decoder catches exceptions and returns base64 encoded data
        result = decoder.decode()
        # Should return base64 encoded string as fallback
        assert isinstance(result, str)
    
    def test_decode_array(self):
        """Test decoding array."""
        # 0x92 = fixarray with 2 elements, followed by 1 and 2
        data = bytes([0x92, 0x01, 0x02])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result == [1, 2]
    
    def test_decode_map(self):
        """Test decoding map."""
        # 0x81 = fixmap with 1 pair, key=1, value=2
        data = bytes([0x81, 0x01, 0x02])
        decoder = MessagePackDecoder(data)
        result = decoder.decode()
        
        assert result == {1: 2}