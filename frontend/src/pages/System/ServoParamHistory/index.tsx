import { App, Button, Form, Input, InputNumber, Modal, Select, Table } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import PageHeader from '../../../components/PageHeader'
import FilterBar from '../../../components/FilterBar'
import Pager from '../../../components/Pager'
import { createServoParamHistory, listServoParamHistories } from '../../../api/servoParamHistory'
import type {
  ServoParamHistoryCreatePayload,
  ServoParamHistoryOut,
  ServoParamHistoryQuery,
} from '../../../api/servoParamHistory'
import { useCrud } from '../../../hooks/useCrud'
import { usePermission } from '../../../hooks/usePermission'
import { useRobotInstanceOptions, useRobotModelOptions, useUserOptions } from '../../../hooks/useOptions'

export default function ServoParamHistoryList() {
  const { message } = App.useApp()
  const { hasRole } = usePermission()
  const canWrite = hasRole('admin', 'engineer')
  const canSeeUsers = hasRole('admin')
  const [form] = Form.useForm()
  const [queryForm] = Form.useForm()
  const instanceOptions = useRobotInstanceOptions()
  const instanceMap = new Map(instanceOptions.map((o) => [o.value, o.label]))
  const modelOptions = useRobotModelOptions()
  const modelMap = new Map(modelOptions.map((o) => [o.value, o.label]))
  const userOptions = useUserOptions(canSeeUsers)
  const userMap = new Map(userOptions.map((o) => [o.value, o.label]))

  // 参数变更历史只增只查，无 update/remove
  const crud = useCrud<
    ServoParamHistoryOut,
    ServoParamHistoryQuery,
    ServoParamHistoryCreatePayload,
    never
  >(
    { list: listServoParamHistories, create: createServoParamHistory },
    {
      robot_instance_id: undefined,
      robot_model_id: undefined,
      param_code: undefined,
      changed_by: undefined,
    },
  )

  const onOpenCreate = () => {
    form.resetFields()
    crud.openCreate()
  }

  const onSubmit = async () => {
    const values = form.getFieldsValue()
    await crud.save(values)
  }

  const columns: TableColumnsType<ServoParamHistoryOut> = [
    {
      title: '机器人',
      dataIndex: 'robot_instance_id',
      width: 180,
      render: (v: number | null) => (v ? instanceMap.get(v) || v : '-'),
    },
    {
      title: '型号',
      dataIndex: 'robot_model_id',
      width: 190,
      render: (v: number | null) => (v ? modelMap.get(v) || v : '-'),
    },
    { title: '参数代码', dataIndex: 'param_code', width: 140 },
    {
      title: '旧值',
      dataIndex: 'old_value',
      width: 90,
      render: (v: number | string | null) => v ?? '-',
    },
    {
      title: '新值',
      dataIndex: 'new_value',
      width: 90,
      render: (v: number | string | null) => v ?? '-',
    },
    {
      title: '修改人',
      dataIndex: 'changed_by',
      width: 130,
      render: (v: number | null) => (v ? userMap.get(v) || v : '-'),
    },
    { title: '原因', dataIndex: 'reason', ellipsis: true, render: (v: string) => v || '-' },
    {
      title: '变更时间',
      dataIndex: 'changed_at',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ]

  return (
    <div>
      <PageHeader
        title="伺服参数历史"
        actions={
          canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={onOpenCreate}>
              记录参数变更
            </Button>
          )
        }
      />

      <FilterBar
        form={queryForm}
        onSearch={() => crud.onSearch(queryForm.getFieldsValue() as ServoParamHistoryQuery)}
        onReset={() => {
          queryForm.resetFields()
          crud.onReset()
        }}
      >
        <Form.Item label="机器人" name="robot_instance_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={instanceOptions} style={{ width: 190 }} />
        </Form.Item>
        <Form.Item label="型号" name="robot_model_id">
          <Select placeholder="全部" allowClear showSearch optionFilterProp="label" options={modelOptions} style={{ width: 190 }} />
        </Form.Item>
        <Form.Item label="参数代码" name="param_code">
          <Input placeholder="参数代码" allowClear style={{ width: 140 }} />
        </Form.Item>
        <Form.Item label="修改人" name="changed_by">
          <Select placeholder="全部" allowClear options={userOptions} style={{ width: 150 }} disabled={!canSeeUsers} />
        </Form.Item>
      </FilterBar>

      <div className="table-card">
        <Table<ServoParamHistoryOut>
          rowKey="id"
          loading={crud.loading}
          dataSource={crud.list}
          columns={columns}
          pagination={false}
          scroll={{ x: 1100 }}
        />
        <Pager
          current={crud.page}
          pageSize={crud.pageSize}
          total={crud.total}
          onChange={crud.onPageChange}
        />
      </div>

      <Modal
        title="记录参数变更"
        width={560}
        open={crud.modalOpen}
        confirmLoading={crud.submitting}
        okText="确定"
        cancelText="取消"
        forceRender
        onOk={() => form.submit()}
        onCancel={() => crud.setModalOpen(false)}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} style={{ marginTop: 8 }}>
          <Form.Item name="robot_instance_id" label="变更对象">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={instanceOptions} />
          </Form.Item>
          <Form.Item name="robot_model_id" label="所属型号">
            <Select placeholder="可选" allowClear showSearch optionFilterProp="label" options={modelOptions} />
          </Form.Item>
          <Form.Item name="param_code" label="参数代码" rules={[{ required: true, message: '请输入参数代码' }]}>
            <Input placeholder="被修改的参数代码" maxLength={50} />
          </Form.Item>
          <Form.Item name="old_value" label="旧值">
            <InputNumber stringMode placeholder="修改前数值" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="new_value" label="新值">
            <InputNumber stringMode placeholder="修改后数值" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="changed_by"
            label="修改人"
            extra={!canSeeUsers ? '默认当前用户，仅管理员可指定' : undefined}
          >
            <Select placeholder="留空默认当前用户" allowClear options={userOptions} disabled={!canSeeUsers} />
          </Form.Item>
          <Form.Item name="reason" label="修改原因">
            <Input.TextArea placeholder="变更原因说明" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
