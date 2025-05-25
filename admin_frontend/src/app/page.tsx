'use client';

import { useState, useEffect } from 'react';
import { Layout, Menu, Button, Card, Row, Col, Statistic, Table, Space, Tabs, Form, Input, Switch, InputNumber, message, Empty, Tag, Descriptions, Divider } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import axios from 'axios';
import type { TabsProps } from 'antd';

const { Header, Content, Footer, Sider } = Layout;

// 统计卡片组件
const StatsCards = ({ stats }: { stats: any }) => {
  return (
    <Row gutter={16} style={{ marginBottom: 24 }}>
      <Col span={6}>
        <Card>
          <Statistic
            title="总对话数"
            value={stats.total_conversations}
            valueStyle={{ color: '#3f8600' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="活跃对话"
            value={stats.active_conversations}
            valueStyle={{ color: '#1890ff' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="已完成对话"
            value={stats.completed_conversations}
            valueStyle={{ color: '#722ed1' }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="成功议价次数"
            value={stats.successful_negotiations}
            valueStyle={{ color: '#fa8c16' }}
          />
        </Card>
      </Col>
    </Row>
  );
};

// 对话列表组件
const ConversationsTable = ({ conversations, loading }: { conversations: any[], loading: boolean }) => {
  if (loading) {
    return <div style={{ textAlign: 'center', padding: '20px' }}>加载会话列表中...</div>;
  }
  
  if (!conversations || conversations.length === 0) {
    return (
      <Empty 
        description="暂无会话数据" 
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }

  const expandedRowRender = (record: any) => {
    // 创建意图统计显示
    const intentTags = Object.entries(record.intent_stats || {}).map(([intent, count]: [string, any]) => (
      <Tag color="purple" key={intent}>
        {intent}: {count}次
      </Tag>
    ));

    return (
      <div style={{ padding: '10px 0' }}>
        <Row gutter={16}>
          <Col span={12}>
            <Card size="small" title="最近对话" bordered={false}>
              {record.recent_messages && record.recent_messages.length > 0 ? (
                <div className="recent-messages">
                  {record.recent_messages.map((msg: any) => (
                    <div key={msg.id} className={`message-item ${msg.role}`}>
                      <div className="message-header">
                        <Tag color={msg.role === 'user' ? 'blue' : 'green'}>
                          {msg.role === 'user' ? '买家' : '机器人'}
                        </Tag>
                        {msg.intent && <Tag color="purple">{msg.intent}</Tag>}
                        <span className="message-time">
                          {msg.timestamp ? new Date(msg.timestamp).toLocaleString() : ''}
                        </span>
                      </div>
                      <div className="message-content">{msg.content}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty description="暂无对话记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="商品信息" bordered={false}>
              <Descriptions column={1} size="small">
                <Descriptions.Item label="商品名称">{record.item_title || '未知商品'}</Descriptions.Item>
                <Descriptions.Item label="价格">¥{record.item_price || '未知'}</Descriptions.Item>
                <Descriptions.Item label="描述">
                  {record.item_description || '无描述'}
                </Descriptions.Item>
              </Descriptions>
              <Divider style={{ margin: '12px 0' }} />
              <div>
                <div style={{ marginBottom: '8px' }}>意图识别统计:</div>
                <Space wrap>
                  {intentTags.length > 0 ? intentTags : <span>暂无意图数据</span>}
                </Space>
              </div>
            </Card>
          </Col>
        </Row>
      </div>
    );
  };

  const columns = [
    {
      title: '用户ID',
      dataIndex: 'user_id',
      key: 'user_id',
    },
    {
      title: '商品信息',
      dataIndex: 'item_title',
      key: 'item_title',
      render: (text: string, record: any) => (
        <div>
          <div>{text || '未知商品'}</div>
          <div style={{ fontSize: '12px', color: '#999' }}>
            价格: ¥{record.item_price || '未知'} | ID: {record.item_id}
          </div>
        </div>
      ),
    },
    {
      title: '最后更新',
      dataIndex: 'last_update',
      key: 'last_update',
      render: (text: string) => text ? new Date(text).toLocaleString() : '未知时间',
    },
    {
      title: '消息数',
      dataIndex: 'message_count',
      key: 'message_count',
      render: (count: number) => (
        <Tag color={count > 0 ? 'green' : 'red'}>{count || 0}</Tag>
      )
    },
    {
      title: '议价次数',
      dataIndex: 'bargain_count',
      key: 'bargain_count',
      render: (count: number) => (
        <Tag color={count > 0 ? 'orange' : 'gray'}>{count || 0}</Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (text: string) => (
        <span style={{ color: text === 'active' ? 'green' : 'gray' }}>
          {text === 'active' ? '活跃' : '不活跃'}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space size="middle">
          <Button type="link" onClick={() => window.open(`/conversation/${record.id}`, '_blank')}>
            查看详情
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      expandable={{
        expandedRowRender,
        rowExpandable: record => record.message_count > 0,
      }}
      dataSource={conversations}
      rowKey="id"
      pagination={{ pageSize: 10 }}
    />
  );
};

// 设置表单组件
const SettingsForm = ({ settings, onSave }: { settings: any, onSave: (values: any) => void }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    form.setFieldsValue(settings);
  }, [settings, form]);

  const onFinish = (values: any) => {
    onSave(values);
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onFinish}
      initialValues={settings}
    >
      <Card title="基本设置" style={{ marginBottom: 24 }}>
        <Form.Item name="default_model" label="默认模型">
          <Input placeholder="模型名称" />
        </Form.Item>
        <Form.Item name="auto_response" label="自动回复" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Card>

      <Card title="议价设置" style={{ marginBottom: 24 }}>
        <Form.Item name={['price_negotiation', 'enabled']} label="启用议价" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name={['price_negotiation', 'min_price_percentage']} label="最低价格百分比">
          <InputNumber min={0} max={100} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name={['price_negotiation', 'steps']} label="降价阶梯数">
          <InputNumber min={1} max={10} style={{ width: '100%' }} />
        </Form.Item>
      </Card>

      <Card title="通知设置">
        <Form.Item name={['notification', 'email_enabled']} label="启用邮件通知" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name={['notification', 'email']} label="邮箱地址">
          <Input placeholder="邮箱地址" />
        </Form.Item>
        <Form.Item name={['notification', 'ding_talk_enabled']} label="启用钉钉通知" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name={['notification', 'ding_talk_webhook']} label="钉钉Webhook">
          <Input placeholder="钉钉Webhook地址" />
        </Form.Item>
      </Card>

      <Form.Item>
        <Button type="primary" htmlType="submit">
          保存设置
        </Button>
      </Form.Item>
    </Form>
  );
};

export default function Home() {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState('1');
  const [stats, setStats] = useState({
    total_conversations: 0,
    active_conversations: 0,
    completed_conversations: 0,
    avg_response_time: 0,
    successful_negotiations: 0,
  });
  const [conversations, setConversations] = useState([]);
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 获取统计数据
    axios.get('/api/stats')
      .then(response => {
        console.log('获取统计数据成功:', response.data);
        setStats(response.data);
      })
      .catch(error => {
        console.error('获取统计数据失败:', error);
      });

    // 获取对话列表
    axios.get('/api/conversations')
      .then(response => {
        console.log('获取对话列表成功:', response.data);
        if (response.data.conversations && response.data.conversations.length > 0) {
          console.log('有 ' + response.data.conversations.length + ' 条会话');
          setConversations(response.data.conversations);
        } else {
          console.log('没有会话数据');
          setConversations([]);
        }
      })
      .catch(error => {
        console.error('获取对话列表失败:', error);
      });

    // 获取设置
    axios.get('/api/settings')
      .then(response => {
        setSettings(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error('获取设置失败:', error);
        setLoading(false);
      });
  }, []);

  const handleSaveSettings = (values: any) => {
    setLoading(true);
    axios.post('/api/settings', values)
      .then(response => {
        message.success('设置已保存');
        setSettings(response.data.settings);
        setLoading(false);
      })
      .catch(error => {
        console.error('保存设置失败:', error);
        message.error('保存设置失败');
        setLoading(false);
      });
  };

  const items: TabsProps['items'] = [
    {
      key: '1',
      label: '仪表盘',
      children: (
        <>
          <StatsCards stats={stats} />
          <Card title="最近对话">
            <ConversationsTable conversations={conversations} loading={loading} />
          </Card>
        </>
      ),
    },
    {
      key: '2',
      label: '系统设置',
      children: (
        <SettingsForm settings={settings} onSave={handleSaveSettings} />
      ),
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        width={200}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div className="logo">
          {collapsed ? 'XY' : '闲鱼AutoAgent'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          defaultSelectedKeys={['1']}
          items={[
            {
              key: '1',
              icon: <DashboardOutlined />,
              label: '仪表盘',
              onClick: () => setActiveTab('1'),
            },
            {
              key: '2',
              icon: <SettingOutlined />,
              label: '系统设置',
              onClick: () => setActiveTab('2'),
            },
            {
              key: '3',
              icon: <ToolOutlined />,
              label: '系统调试',
              onClick: () => window.location.href = '/debug',
            },
          ]}
        />
      </Sider>
      <Layout className="site-layout" style={{ marginLeft: collapsed ? 80 : 200 }}>
        <Header style={{ padding: 0, background: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingRight: 24 }}>
            <Space>
              <Button icon={<UserOutlined />}>管理员</Button>
              <Button icon={<LogoutOutlined />} type="primary" danger>
                退出
              </Button>
            </Space>
          </div>
        </Header>
        <Content style={{ margin: '24px 16px 0', overflow: 'initial' }}>
          <div style={{ padding: 24, background: '#fff', minHeight: 360 }}>
            <Tabs activeKey={activeTab} items={items} onChange={setActiveTab} />
          </div>
        </Content>
        <Footer style={{ textAlign: 'center' }}>
          闲鱼AutoAgent管理后台 ©{new Date().getFullYear()} Created by XianyuAutoAgent
        </Footer>
      </Layout>
    </Layout>
  );
} 