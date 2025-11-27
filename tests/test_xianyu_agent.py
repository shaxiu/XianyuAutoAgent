"""Tests for XianyuAgent classes."""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from XianyuAgent import (
    XianyuReplyBot,
    IntentRouter,
    BaseAgent,
    PriceAgent,
    TechAgent,
    ClassifyAgent,
    DefaultAgent
)


class TestXianyuReplyBot:
    """Tests for XianyuReplyBot class."""
    
    @patch('XianyuAgent.OpenAI')
    def test_init(self, mock_openai, mock_env_vars, temp_prompts_dir, monkeypatch):
        """Test XianyuReplyBot initialization."""
        monkeypatch.chdir(temp_prompts_dir.parent)
        
        bot = XianyuReplyBot()
        
        assert bot.client is not None
        assert bot.router is not None
        assert 'classify' in bot.agents
        assert 'price' in bot.agents
        assert 'tech' in bot.agents
        assert 'default' in bot.agents
    
    def test_safe_filter_blocks_sensitive_words(self):
        """Test that safe filter blocks sensitive words."""
        bot = Mock()
        bot._safe_filter = XianyuReplyBot._safe_filter.__get__(bot, XianyuReplyBot)
        
        # Test blocked phrases
        assert "安全提醒" in bot._safe_filter("加我微信")
        assert "安全提醒" in bot._safe_filter("QQ联系")
        assert "安全提醒" in bot._safe_filter("支付宝转账")
        assert "安全提醒" in bot._safe_filter("线下交易")
    
    def test_safe_filter_allows_normal_text(self):
        """Test that safe filter allows normal text."""
        bot = Mock()
        bot._safe_filter = XianyuReplyBot._safe_filter.__get__(bot, XianyuReplyBot)
        
        normal_text = "这个商品很不错"
        assert bot._safe_filter(normal_text) == normal_text
    
    def test_format_history(self, sample_context):
        """Test format_history method."""
        bot = Mock()
        bot.format_history = XianyuReplyBot.format_history.__get__(bot, XianyuReplyBot)
        
        formatted = bot.format_history(sample_context)
        
        assert isinstance(formatted, str)
        assert "user:" in formatted
        assert "assistant:" in formatted
        assert "这个多少钱" in formatted
    
    def test_extract_bargain_count(self):
        """Test extracting bargain count from context."""
        bot = Mock()
        bot._extract_bargain_count = XianyuReplyBot._extract_bargain_count.__get__(bot, XianyuReplyBot)
        
        context = [
            {"role": "user", "content": "能便宜吗？"},
            {"role": "system", "content": "议价次数: 3"}
        ]
        
        count = bot._extract_bargain_count(context)
        assert count == 3
    
    def test_extract_bargain_count_no_count(self):
        """Test extracting bargain count when none exists."""
        bot = Mock()
        bot._extract_bargain_count = XianyuReplyBot._extract_bargain_count.__get__(bot, XianyuReplyBot)
        
        context = [
            {"role": "user", "content": "你好"}
        ]
        
        count = bot._extract_bargain_count(context)
        assert count == 0


class TestIntentRouter:
    """Tests for IntentRouter class."""
    
    def test_detect_tech_intent_by_keyword(self):
        """Test detecting tech intent by keyword."""
        mock_classify_agent = Mock()
        router = IntentRouter(mock_classify_agent)
        
        result = router.detect("这个参数是多少？", "商品描述", "")
        
        assert result == 'tech'
        # Should not call classify agent for keyword match
        mock_classify_agent.generate.assert_not_called()
    
    def test_detect_price_intent_by_keyword(self):
        """Test detecting price intent by keyword."""
        mock_classify_agent = Mock()
        router = IntentRouter(mock_classify_agent)
        
        result = router.detect("能便宜点吗？", "商品描述", "")
        
        assert result == 'price'
    
    def test_detect_tech_intent_by_pattern(self):
        """Test detecting tech intent by pattern."""
        mock_classify_agent = Mock()
        router = IntentRouter(mock_classify_agent)
        
        result = router.detect("这个和iPhone比怎么样？", "商品描述", "")
        
        assert result == 'tech'
    
    def test_detect_fallback_to_llm(self):
        """Test fallback to LLM classification."""
        mock_classify_agent = Mock()
        mock_classify_agent.generate.return_value = 'default'
        router = IntentRouter(mock_classify_agent)
        
        result = router.detect("你好", "商品描述", "")
        
        assert result == 'default'
        mock_classify_agent.generate.assert_called_once()


class TestBaseAgent:
    """Tests for BaseAgent class."""
    
    def test_generate(self, mock_openai_client):
        """Test base agent generate method."""
        safety_filter = lambda x: x
        agent = BaseAgent(mock_openai_client, "系统提示词", safety_filter)
        
        result = agent.generate("用户消息", "商品描述", "对话历史")
        
        assert result == "测试回复"
        mock_openai_client.chat.completions.create.assert_called_once()
    
    def test_build_messages(self, mock_openai_client):
        """Test message building."""
        safety_filter = lambda x: x
        agent = BaseAgent(mock_openai_client, "系统提示词", safety_filter)
        
        messages = agent._build_messages("用户消息", "商品描述", "对话历史")
        
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert "商品描述" in messages[0]['content']
        assert messages[1]['content'] == "用户消息"


class TestPriceAgent:
    """Tests for PriceAgent class."""
    
    def test_calc_temperature(self, mock_openai_client):
        """Test temperature calculation."""
        safety_filter = lambda x: x
        agent = PriceAgent(mock_openai_client, "价格提示词", safety_filter)
        
        # Test increasing temperature with bargain count
        temp_0 = agent._calc_temperature(0)
        temp_1 = agent._calc_temperature(1)
        temp_3 = agent._calc_temperature(3)
        
        assert temp_0 < temp_1 < temp_3
        assert temp_3 <= 0.9  # Max temperature
    
    def test_generate_includes_bargain_count(self, mock_openai_client):
        """Test that generate includes bargain count."""
        safety_filter = lambda x: x
        agent = PriceAgent(mock_openai_client, "价格提示词", safety_filter)
        
        result = agent.generate("能便宜吗？", "商品100元", "历史", bargain_count=2)
        
        # Check that bargain count was included in the call
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert "议价轮次" in messages[0]['content']
        assert "2" in messages[0]['content']


class TestTechAgent:
    """Tests for TechAgent class."""
    
    def test_generate_enables_search(self, mock_openai_client):
        """Test that tech agent enables search."""
        safety_filter = lambda x: x
        agent = TechAgent(mock_openai_client, "技术提示词", safety_filter)
        
        result = agent.generate("参数是多少？", "商品描述", "历史")
        
        # Check that enable_search was set
        call_args = mock_openai_client.chat.completions.create.call_args
        extra_body = call_args[1].get('extra_body', {})
        assert extra_body.get('enable_search') is True