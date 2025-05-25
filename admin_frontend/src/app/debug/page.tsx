'use client';

import { useState, useEffect } from 'react';
import { Card, Button, Table, Typography, Space, Alert, Tabs, Descriptions, Tag, Divider, message } from 'antd';
import { ToolOutlined, DatabaseOutlined, MessageOutlined, HomeOutlined } from '@ant-design/icons';
import axios from 'axios';
import Link from 'next/link';

const { Title, Text, Paragraph } = Typography;
const { TabPane } = Tabs;

export default function DebugPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [debugInfo, setDebugInfo] = useState<any>({});
  const [testLoading, setTestLoading] = useState(false);
  
  useEffect(() => {
    fetchDebugInfo();
  }, []);
  
  const fetchDebugInfo = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get('/api/debug');
      console.log('调试信息:', response.data);
      setDebugInfo(response.data);
    } catch (error: any) {
      console.error('获取调试信息失败:', error);
      setError(error.response?.data?.detail || '获取调试信息失败');
    } finally {
      setLoading(false);
    }
  };
  
  const handleCreateTestConversation = async () => {
    try {
      setTestLoading(true);
      const response = await axios.post('/api/debug/create-test-conversation');
      message.success('测试会话创建成功');
      console.log('测试会话创建结果:', response.data);
      // 刷新调试信息
      fetchDebugInfo();
      
      // 显示会话链接
      message.info(
        <span>
          测试会话已创建，ID: {response.data.conversation_id}，
          <a href={`/conversation/${response.data.conversation_id}`} target="_blank" rel="noopener noreferrer">
            点击查看
          </a>
        </span>
      );
    } catch (error) {
      console.error('创建测试会话失败:', error);
      message.error('创建测试会话失败');
    } finally {
      setTestLoading(false);
    }
  };
  
  const handleResetTestData = async () => {
    try {
      setTestLoading(true);
      const response = await axios.post('/api/debug/reset-test-data');
      message.success('测试数据重置成功');
      console.log('测试数据重置结果:', response.data);
      // 刷新调试信息
      fetchDebugInfo();
      
      // 显示会话链接
      message.info(
        <span>
          测试数据已重置，会话ID: {response.data.conversation_id}，
          <a href={`/conversation/${response.data.conversation_id}`} target="_blank" rel="noopener noreferrer">
            点击查看
          </a>
        </span>
      );
    } catch (error) {
      console.error('重置测试数据失败:', error);
      message.error('重置测试数据失败');
    } finally {
      setTestLoading(false);
    }
  };
  
  const handleAddTestMessage = async (convId: number) => {
    try {
      setTestLoading(true);
      await axios.post(`/api/debug/add-test-message/${convId}`);
      message.success(`已添加测试消息到会话 ${convId}`);
      // 刷新调试信息
      fetchDebugInfo();
    } catch (error) {
      console.error('添加测试消息失败:', error);
      message.error('添加测试消息失败');
    } finally {
      setTestLoading(false);
    }
  };
  
  const conversationsColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '用户ID',
      dataIndex: 'user_id',
      key: 'user_id',
    },
    {
      title: '商品ID',
      dataIndex: 'item_id',
      key: 'item_id',
    },
    {
      title: '消息数',
      dataIndex: 'message_count',
      key: 'message_count',
      render: (count: number) => (
        <Tag color={count > 0 ? 'green' : 'red'}>{count}</Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button 
            size="small"
            type="primary" 
            onClick={() => handleAddTestMessage(record.id)}
          >
            添加测试消息
          </Button>
          <Button 
            size="small"
            onClick={() => window.open(`/conversation/${record.id}`, '_blank')}
          >
            查看详情
          </Button>
        </Space>
      ),
    },
  ];
  
  const messagesColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '会话ID',
      dataIndex: 'conversation_id',
      key: 'conversation_id',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => {
        const color = role === 'user' ? 'blue' : (role === 'assistant' ? 'green' : 'purple');
        return <Tag color={color}>{role}</Tag>;
      }
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
    },
    {
      title: '意图',
      dataIndex: 'intent',
      key: 'intent',
      render: (intent: string) => intent ? <Tag color="purple">{intent}</Tag> : '-'
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (timestamp: string) => new Date(timestamp).toLocaleString()
    },
  ];
  
  if (loading) {
    return (
      <div style={{ padding: '50px', textAlign: 'center' }}>
        <Title level={3}>正在加载调试信息...</Title>
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={{ padding: '50px' }}>
        <Alert
          message="获取调试信息失败"
          description={error}
          type="error"
          showIcon
        />
      </div>
    );
  }
  
  return (
    <div style={{ padding: '20px' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={2}><ToolOutlined /> 系统调试页面</Title>
          <Space>
            <Button onClick={fetchDebugInfo}>刷新数据</Button>
            <Button type="primary" onClick={handleCreateTestConversation} loading={testLoading}>
              创建测试会话
            </Button>
            <Button type="primary" onClick={handleResetTestData} loading={testLoading}>
              重置测试数据
            </Button>
            <Link href="/">
              <Button icon={<HomeOutlined />}>返回首页</Button>
            </Link>
          </Space>
        </div>
        
        <Card title={<Space><DatabaseOutlined /> 数据库信息</Space>}>
          <Descriptions bordered>
            <Descriptions.Item label="数据库文件" span={3}>
              {debugInfo.database_file}
            </Descriptions.Item>
            
            <Descriptions.Item label="用户表">
              <Tag color="blue">{debugInfo.tables?.users || 0} 条记录</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="商品表">
              <Tag color="orange">{debugInfo.tables?.items || 0} 条记录</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="会话表">
              <Tag color="green">{debugInfo.tables?.conversations || 0} 条记录</Tag>
            </Descriptions.Item>
            
            <Descriptions.Item label="消息表" span={3}>
              <Tag color="purple">{debugInfo.tables?.messages || 0} 条记录</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
        
        <Tabs defaultActiveKey="1">
          <TabPane tab="会话列表" key="1">
            <Card>
              <Table 
                dataSource={debugInfo.conversations || []} 
                columns={conversationsColumns}
                rowKey="id"
                pagination={{ pageSize: 5 }}
              />
            </Card>
          </TabPane>
          
          <TabPane tab="最新消息" key="2">
            <Card>
              <Table 
                dataSource={debugInfo.latest_messages || []} 
                columns={messagesColumns}
                rowKey="id"
                pagination={false}
              />
            </Card>
          </TabPane>
        </Tabs>
      </Space>
    </div>
  );
} 