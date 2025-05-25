'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Layout, Card, Button, Input, Typography, Space, Spin, message, Descriptions, Tag, Divider, Empty, Alert } from 'antd';
import { ArrowLeftOutlined, SendOutlined, ShoppingOutlined, CommentOutlined, DollarOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Header, Content } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

export default function ConversationDetail() {
  const params = useParams();
  const id = params.id as string;
  
  const [conversation, setConversation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConversation();
  }, []);

  const fetchConversation = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('正在获取会话详情:', id);
      const response = await axios.get(`/api/conversations/${id}`);
      console.log('获取到的会话数据:', response.data);
      
      // 确保会话数据具有正确的结构
      const conversationData = response.data;
      
      // 检查并确保messages字段存在，如果不存在则初始化为空数组
      if (!conversationData.messages) {
        console.warn('会话数据中没有messages字段，初始化为空数组');
        conversationData.messages = [];
      }
      
      // 确保messages是数组
      if (!Array.isArray(conversationData.messages)) {
        console.warn('messages不是数组，转换为数组');
        conversationData.messages = [];
      }
      
      setConversation(conversationData);
      
      // 检查消息数据
      if (conversationData.messages.length === 0) {
        console.log('没有找到消息记录');
      } else {
        console.log(`找到 ${conversationData.messages.length} 条消息记录`);
      }
    } catch (error: any) {
      console.error('获取会话详情失败:', error);
      message.error('获取会话详情失败');
      setError(error.response?.data?.detail || '获取会话详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim()) return;
    
    try {
      setSending(true);
      await axios.post(`/api/send_message/${id}`, { message: newMessage });
      message.success('消息已发送');
      setNewMessage('');
      // 重新获取会话数据
      fetchConversation();
    } catch (error: any) {
      console.error('发送消息失败:', error);
      message.error('发送消息失败');
    } finally {
      setSending(false);
    }
  };

  const getRoleLabel = (role: string) => {
    switch(role) {
      case 'user': return '买家';
      case 'assistant': return '机器人';
      case 'admin': return '管理员';
      default: return role;
    }
  };
  
  const getRoleColor = (role: string) => {
    switch(role) {
      case 'user': return '#1890ff';
      case 'assistant': return '#52c41a';
      case 'admin': return '#722ed1';
      default: return '#f0f0f0';
    }
  };

  if (loading && !conversation) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
        />
        <Button 
          type="primary" 
          style={{ marginTop: '20px' }}
          onClick={() => window.history.back()}
        >
          返回
        </Button>
      </div>
    );
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#fff', padding: '0 16px' }}>
        <Space>
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => window.history.back()}
          >
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            与用户 {conversation?.user_id} 的对话
          </Title>
        </Space>
      </Header>
      <Content style={{ padding: '24px' }}>
        {conversation && (
          <>
            <Card 
              title={<Space><ShoppingOutlined /> 商品信息</Space>}
              style={{ marginBottom: 24 }}
            >
              <Descriptions bordered column={{ xxl: 4, xl: 3, lg: 3, md: 2, sm: 1, xs: 1 }}>
                <Descriptions.Item label="商品ID">{conversation.item_id}</Descriptions.Item>
                <Descriptions.Item label="商品名称">{conversation.item_title || '未知商品'}</Descriptions.Item>
                <Descriptions.Item label="价格">¥{conversation.item_price || '未知'}</Descriptions.Item>
                <Descriptions.Item label="议价次数">
                  <Tag color="orange">{conversation.bargain_count || 0}次</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="商品描述" span={4}>
                  <Paragraph ellipsis={{ rows: 3, expandable: true }}>
                    {conversation.item_description || '无描述'}
                  </Paragraph>
                </Descriptions.Item>
              </Descriptions>
            </Card>
            
            <Card 
              title={<Space><CommentOutlined /> 对话历史</Space>}
              extra={
                <Space>
                  <Button onClick={fetchConversation}>刷新</Button>
                  <Tag color="blue">{conversation.messages.length} 条消息</Tag>
                </Space>
              }
              style={{ marginBottom: 24 }}
            >
              <div className="chat-container">
                {conversation.messages && conversation.messages.length > 0 ? (
                  conversation.messages.map((msg: any, index: number) => (
                    <div 
                      key={index}
                      className={`message ${msg.role === 'user' ? 'message-user' : 'message-agent'}`}
                    >
                      <Space style={{ marginBottom: '4px' }}>
                        <Tag color={getRoleColor(msg.role)}>{getRoleLabel(msg.role)}</Tag>
                        <small>{msg.timestamp ? new Date(msg.timestamp).toLocaleString() : '未知时间'}</small>
                        {msg.intent && <Tag color="purple">{msg.intent}</Tag>}
                      </Space>
                      <div className="message-content">
                        <Text>{msg.content || '无内容'}</Text>
                      </div>
                    </div>
                  ))
                ) : (
                  <Empty 
                    description={
                      <span>
                        暂无对话记录
                        <Button 
                          type="link" 
                          size="small"
                          onClick={() => {
                            message.info('正在重新获取会话数据...');
                            fetchConversation();
                          }}
                        >
                          重新加载
                        </Button>
                      </span>
                    }
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                )}
              </div>
            </Card>

            <Card title={<Space><SendOutlined /> 发送消息</Space>}>
              <TextArea 
                rows={4}
                value={newMessage}
                onChange={e => setNewMessage(e.target.value)}
                placeholder="输入要发送的消息..."
                style={{ marginBottom: 16 }}
              />
              <Button 
                type="primary" 
                icon={<SendOutlined />} 
                onClick={handleSendMessage}
                loading={sending}
              >
                发送
              </Button>
            </Card>
          </>
        )}
      </Content>
    </Layout>
  );
} 