"""Tests for ChatContextManager class."""
import pytest
import os
import json
from datetime import datetime
from context_manager import ChatContextManager


class TestChatContextManager:
    """Tests for ChatContextManager."""
    
    def test_init_creates_database(self, temp_db):
        """Test that initialization creates database."""
        manager = ChatContextManager(db_path=temp_db)
        
        assert os.path.exists(temp_db)
    
    def test_save_and_get_item_info(self, temp_db, sample_item_data):
        """Test saving and retrieving item info."""
        manager = ChatContextManager(db_path=temp_db)
        item_id = sample_item_data['item_id']
        
        manager.save_item_info(item_id, sample_item_data)
        retrieved = manager.get_item_info(item_id)
        
        assert retrieved is not None
        assert retrieved['item_id'] == item_id
        assert retrieved['soldPrice'] == sample_item_data['soldPrice']
        assert retrieved['desc'] == sample_item_data['desc']
    
    def test_get_nonexistent_item_info(self, temp_db):
        """Test retrieving non-existent item info."""
        manager = ChatContextManager(db_path=temp_db)
        
        result = manager.get_item_info("nonexistent_id")
        
        assert result is None
    
    def test_add_message_by_chat(self, temp_db):
        """Test adding messages by chat ID."""
        manager = ChatContextManager(db_path=temp_db)
        chat_id = "chat_123"
        user_id = "user_456"
        item_id = "item_789"
        
        manager.add_message_by_chat(chat_id, user_id, item_id, "user", "你好")
        manager.add_message_by_chat(chat_id, user_id, item_id, "assistant", "你好！")
        
        context = manager.get_context_by_chat(chat_id)
        
        assert len(context) == 2
        assert context[0]['role'] == 'user'
        assert context[0]['content'] == '你好'
        assert context[1]['role'] == 'assistant'
        assert context[1]['content'] == '你好！'
    
    def test_get_context_by_chat_empty(self, temp_db):
        """Test getting context for non-existent chat."""
        manager = ChatContextManager(db_path=temp_db)
        
        context = manager.get_context_by_chat("nonexistent_chat")
        
        assert context == []
    
    def test_increment_bargain_count(self, temp_db):
        """Test incrementing bargain count."""
        manager = ChatContextManager(db_path=temp_db)
        chat_id = "chat_123"
        
        # Initial count should be 0
        assert manager.get_bargain_count_by_chat(chat_id) == 0
        
        # Increment once
        manager.increment_bargain_count_by_chat(chat_id)
        assert manager.get_bargain_count_by_chat(chat_id) == 1
        
        # Increment again
        manager.increment_bargain_count_by_chat(chat_id)
        assert manager.get_bargain_count_by_chat(chat_id) == 2
    
    def test_bargain_count_in_context(self, temp_db):
        """Test that bargain count appears in context."""
        manager = ChatContextManager(db_path=temp_db)
        chat_id = "chat_123"
        
        manager.add_message_by_chat(chat_id, "user1", "item1", "user", "能便宜吗？")
        manager.increment_bargain_count_by_chat(chat_id)
        
        context = manager.get_context_by_chat(chat_id)
        
        # Should have user message + system message with bargain count
        assert len(context) == 2
        assert context[1]['role'] == 'system'
        assert '议价次数' in context[1]['content']
        assert '1' in context[1]['content']
    
    def test_max_history_limit(self, temp_db):
        """Test that max history limit is enforced."""
        max_history = 5
        manager = ChatContextManager(max_history=max_history, db_path=temp_db)
        chat_id = "chat_123"
        
        # Add more messages than max_history
        for i in range(10):
            manager.add_message_by_chat(
                chat_id, "user1", "item1", "user", f"Message {i}"
            )
        
        context = manager.get_context_by_chat(chat_id)
        
        # Should only have max_history messages
        assert len(context) <= max_history
        # Should have the most recent messages (5-9 when max_history=5)
        # The last message should be from the most recent batch
        assert "Message" in context[-1]['content']
        # Verify we have exactly max_history messages
        assert len(context) == max_history
    
    def test_update_item_info(self, temp_db, sample_item_data):
        """Test updating existing item info."""
        manager = ChatContextManager(db_path=temp_db)
        item_id = sample_item_data['item_id']
        
        # Save initial data
        manager.save_item_info(item_id, sample_item_data)
        
        # Update with new data
        updated_data = sample_item_data.copy()
        updated_data['soldPrice'] = 200.0
        manager.save_item_info(item_id, updated_data)
        
        # Retrieve and verify
        retrieved = manager.get_item_info(item_id)
        assert retrieved['soldPrice'] == 200.0