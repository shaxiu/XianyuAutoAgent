"""Shared pytest fixtures for XianyuAutoAgent tests."""
import os
import sys
import tempfile
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "测试回复"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def sample_context():
    """Sample conversation context."""
    return [
        {"role": "user", "content": "这个多少钱？"},
        {"role": "assistant", "content": "这个商品售价100元"},
        {"role": "user", "content": "能便宜点吗？"},
    ]


@pytest.fixture
def sample_item_data():
    """Sample item data."""
    return {
        "item_id": "12345",
        "soldPrice": 100.0,
        "desc": "测试商品描述",
        "title": "测试商品"
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("API_KEY", "test_api_key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://test.api.com")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("COOKIES_STR", "unb=test_user; cookie2=test_cookie")


@pytest.fixture
def sample_cookies():
    """Sample cookies string."""
    return "unb=123456; cookie2=abcdef; _m_h5_tk=token123_456; cna=device123"


@pytest.fixture
def mock_requests_session():
    """Mock requests session."""
    mock_session = Mock()
    mock_session.cookies = Mock()
    mock_session.cookies.get = Mock(side_effect=lambda key, default='': {
        'unb': '123456',
        'cookie2': 'abcdef',
        '_m_h5_tk': 'token123_456',
        'cna': 'device123'
    }.get(key, default))
    mock_session.headers = Mock()
    mock_session.headers.update = Mock()
    return mock_session


@pytest.fixture
def temp_prompts_dir(tmp_path):
    """Create temporary prompts directory with example files."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    
    # Create example prompt files
    (prompts_dir / "classify_prompt.txt").write_text("分类提示词")
    (prompts_dir / "price_prompt.txt").write_text("价格提示词")
    (prompts_dir / "tech_prompt.txt").write_text("技术提示词")
    (prompts_dir / "default_prompt.txt").write_text("默认提示词")
    
    return prompts_dir