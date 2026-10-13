-- =====================================================================
-- RoboSuper Agent 数据库初始化脚本
-- 依据：backend/plan.md §9 数据库设计（§9.1 实体关系图 + §9.2 表清单）
-- 范围：public schema 12 张业务表
-- 说明：
--   1. 不依赖任何 PG 扩展（zhparser/pg_trgm 已弃用，关键词检索由
--      jieba + rank-bm25 在应用层内存索引实现）
--   2. 报警码/原因/SOP 等知识在 Neo4j，PG 侧只存 alarm_code 字符串，
--      通过该字段跨存储关联，不建外键
--   3. LangGraph Checkpoint 的 langgraph schema 由
--      langgraph-checkpoint-postgres 的 checkpointer.setup() 自动创建，
--      不在本脚本范围内
--   4. 每张表和字段都带 COMMENT，可用 psql 的 \d+ 表名 查看
-- 运行：psql -U postgres -d sentinel_ai -f init.sql
-- =====================================================================

-- =====================================================================
-- 认证模块
-- =====================================================================

-- 系统用户：三种角色（admin 管理员 / engineer 工程师 / viewer 只读）
CREATE TABLE IF NOT EXISTS sys_user (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('admin', 'engineer', 'viewer')),
    name          VARCHAR(50),
    email         VARCHAR(100),
    phone         VARCHAR(20),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE  sys_user                    IS '系统用户：admin 管理员 / engineer 工程师 / viewer 只读';
COMMENT ON COLUMN sys_user.id                 IS '用户 ID（主键，自增）';
COMMENT ON COLUMN sys_user.username           IS '登录用户名（唯一）';
COMMENT ON COLUMN sys_user.password_hash      IS '密码哈希（bcrypt）';
COMMENT ON COLUMN sys_user.role               IS '角色：admin / engineer / viewer';
COMMENT ON COLUMN sys_user.name               IS '姓名';
COMMENT ON COLUMN sys_user.email              IS '邮箱';
COMMENT ON COLUMN sys_user.phone              IS '手机号';
COMMENT ON COLUMN sys_user.is_active          IS '是否启用，禁用后无法登录';
COMMENT ON COLUMN sys_user.created_at         IS '创建时间';
COMMENT ON COLUMN sys_user.updated_at         IS '最后更新时间';

-- =====================================================================
-- 业务模块
-- =====================================================================

-- 机器人品牌
CREATE TABLE IF NOT EXISTS brand (
    id          BIGSERIAL PRIMARY KEY,
    code        VARCHAR(20) NOT NULL UNIQUE,   -- FANUC / ABB / KUKA / YASKAWA
    name        VARCHAR(50) NOT NULL,
    country     VARCHAR(50),
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  brand            IS '机器人品牌（FANUC / ABB / KUKA / YASKAWA 等）';
COMMENT ON COLUMN brand.id         IS '品牌 ID（主键）';
COMMENT ON COLUMN brand.code       IS '品牌代码（唯一，如 FANUC）';
COMMENT ON COLUMN brand.name       IS '品牌名称';
COMMENT ON COLUMN brand.country    IS '品牌所属国家';
COMMENT ON COLUMN brand.description IS '品牌说明';
COMMENT ON COLUMN brand.created_at IS '创建时间';

-- 机器人控制器型号
CREATE TABLE IF NOT EXISTS controller (
    id          BIGSERIAL PRIMARY KEY,
    brand_id    BIGINT NOT NULL REFERENCES brand(id),
    code        VARCHAR(30) NOT NULL,          -- R-30iB Plus / IRC5 / KSS
    name        VARCHAR(100) NOT NULL,
    series      VARCHAR(50),
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, code)
);
COMMENT ON TABLE  controller             IS '机器人控制器型号（如 R-30iB Plus / IRC5 / KSS）';
COMMENT ON COLUMN controller.id          IS '控制器 ID（主键）';
COMMENT ON COLUMN controller.brand_id    IS '所属品牌（外键 → brand.id）';
COMMENT ON COLUMN controller.code        IS '控制器代码（品牌内唯一）';
COMMENT ON COLUMN controller.name        IS '控制器名称';
COMMENT ON COLUMN controller.series      IS '系列';
COMMENT ON COLUMN controller.description IS '说明';
COMMENT ON COLUMN controller.created_at  IS '创建时间';

-- 机器人型号
CREATE TABLE IF NOT EXISTS robot_model (
    id            BIGSERIAL PRIMARY KEY,
    brand_id      BIGINT NOT NULL REFERENCES brand(id),
    controller_id BIGINT REFERENCES controller(id),
    code          VARCHAR(50) NOT NULL,        -- R-2000iC/210L
    name          VARCHAR(100) NOT NULL,
    payload_kg    NUMERIC(8, 2),
    reach_mm      NUMERIC(10, 2),
    axes          SMALLINT,
    description   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (brand_id, code)
);
COMMENT ON TABLE  robot_model             IS '机器人型号（品牌 + 控制器确定一台的规格基线）';
COMMENT ON COLUMN robot_model.id          IS '型号 ID（主键）';
COMMENT ON COLUMN robot_model.brand_id    IS '所属品牌（外键 → brand.id）';
COMMENT ON COLUMN robot_model.controller_id IS '使用的控制器（外键 → controller.id）';
COMMENT ON COLUMN robot_model.code        IS '型号代码（品牌内唯一，如 R-2000iC/210L）';
COMMENT ON COLUMN robot_model.name        IS '型号名称';
COMMENT ON COLUMN robot_model.payload_kg  IS '额定负载（kg）';
COMMENT ON COLUMN robot_model.reach_mm    IS '臂展/工作半径（mm）';
COMMENT ON COLUMN robot_model.axes        IS '轴数';
COMMENT ON COLUMN robot_model.description IS '说明';
COMMENT ON COLUMN robot_model.created_at  IS '创建时间';

-- 机器人实例：客户现场的每一台具体设备
CREATE TABLE IF NOT EXISTS robot_instance (
    id              BIGSERIAL PRIMARY KEY,
    robot_model_id  BIGINT NOT NULL REFERENCES robot_model(id),
    asset_no        VARCHAR(50) NOT NULL UNIQUE,   -- 客户资产编号，稳定标识
    name            VARCHAR(100),
    serial_no       VARCHAR(50),
    line_id         VARCHAR(50),                   -- LINE-001
    install_date    DATE,
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'idle', 'alarm', 'maintenance', 'offline')),
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  robot_instance              IS '机器人实例：客户现场的每一台具体设备（资产维度）';
COMMENT ON COLUMN robot_instance.id           IS '实例 ID（主键）';
COMMENT ON COLUMN robot_instance.robot_model_id IS '所属型号（外键 → robot_model.id）';
COMMENT ON COLUMN robot_instance.asset_no     IS '客户资产编号（唯一，稳定标识，跨系统通用）';
COMMENT ON COLUMN robot_instance.name         IS '实例名称/别名';
COMMENT ON COLUMN robot_instance.serial_no    IS '出厂序列号';
COMMENT ON COLUMN robot_instance.line_id      IS '所属产线（如 LINE-001）';
COMMENT ON COLUMN robot_instance.install_date IS '安装日期';
COMMENT ON COLUMN robot_instance.status       IS '运行状态：running / idle / alarm / maintenance / offline';
COMMENT ON COLUMN robot_instance.note         IS '备注';
COMMENT ON COLUMN robot_instance.created_at   IS '创建时间';
CREATE INDEX IF NOT EXISTS idx_robot_instance_model ON robot_instance(robot_model_id);
CREATE INDEX IF NOT EXISTS idx_robot_instance_line  ON robot_instance(line_id);

-- 备件库存：EPC 图号 + 分仓库存量
CREATE TABLE IF NOT EXISTS part_inventory (
    id                BIGSERIAL PRIMARY KEY,
    part_no           VARCHAR(50) NOT NULL,        -- EPC 图号
    name              VARCHAR(200) NOT NULL,
    brand_id          BIGINT REFERENCES brand(id),
    category          VARCHAR(50),
    price             NUMERIC(12, 2),
    lead_time_days    SMALLINT,
    compatible_brands TEXT[],                      -- 兼容品牌列表
    quantity          INT         NOT NULL DEFAULT 0,
    warehouse         VARCHAR(50) NOT NULL,
    location          VARCHAR(50),
    safety_stock      INT         NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (part_no, warehouse)
);
COMMENT ON TABLE  part_inventory              IS '备件库存（按 EPC 图号 + 仓库）；检索是结构化查询，放 PG 而非 Neo4j';
COMMENT ON COLUMN part_inventory.id           IS '库存记录 ID（主键）';
COMMENT ON COLUMN part_inventory.part_no      IS 'EPC 图号/备件编号';
COMMENT ON COLUMN part_inventory.name         IS '备件名称';
COMMENT ON COLUMN part_inventory.brand_id     IS '主品牌（外键 → brand.id）';
COMMENT ON COLUMN part_inventory.category     IS '备件分类';
COMMENT ON COLUMN part_inventory.price        IS '单价';
COMMENT ON COLUMN part_inventory.lead_time_days IS '采购周期（天）';
COMMENT ON COLUMN part_inventory.compatible_brands IS '兼容品牌列表（数组）';
COMMENT ON COLUMN part_inventory.quantity     IS '当前库存数量';
COMMENT ON COLUMN part_inventory.warehouse    IS '所属仓库';
COMMENT ON COLUMN part_inventory.location     IS '货位';
COMMENT ON COLUMN part_inventory.safety_stock IS '安全库存阈值（低于此值应补货）';
COMMENT ON COLUMN part_inventory.updated_at   IS '库存最后更新时间';
CREATE INDEX IF NOT EXISTS idx_part_inventory_brand ON part_inventory(brand_id);

-- 伺服参数定义：按型号维护参数的默认值/范围
CREATE TABLE IF NOT EXISTS servo_param (
    id             BIGSERIAL PRIMARY KEY,
    robot_model_id BIGINT NOT NULL REFERENCES robot_model(id),
    param_code     VARCHAR(50) NOT NULL,
    param_name     VARCHAR(100) NOT NULL,
    default_value  NUMERIC(12, 4),
    min_value      NUMERIC(12, 4),
    max_value      NUMERIC(12, 4),
    unit           VARCHAR(20),
    description    TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (robot_model_id, param_code)
);
COMMENT ON TABLE  servo_param               IS '伺服参数定义（按机器人型号维护默认值/上下限）';
COMMENT ON COLUMN servo_param.id            IS '参数 ID（主键）';
COMMENT ON COLUMN servo_param.robot_model_id IS '所属型号（外键 → robot_model.id）';
COMMENT ON COLUMN servo_param.param_code    IS '参数代码（型号内唯一）';
COMMENT ON COLUMN servo_param.param_name    IS '参数名称';
COMMENT ON COLUMN servo_param.default_value IS '出厂默认值';
COMMENT ON COLUMN servo_param.min_value     IS '允许下限';
COMMENT ON COLUMN servo_param.max_value     IS '允许上限';
COMMENT ON COLUMN servo_param.unit          IS '单位';
COMMENT ON COLUMN servo_param.description   IS '说明';
COMMENT ON COLUMN servo_param.created_at    IS '创建时间';
CREATE INDEX IF NOT EXISTS idx_servo_param_model ON servo_param(robot_model_id);

-- 排障工单：报警→诊断→建单→指派→处理→验收 的运维闭环
CREATE TABLE IF NOT EXISTS work_order (
    id                BIGSERIAL PRIMARY KEY,
    work_order_no     VARCHAR(30) NOT NULL UNIQUE, -- WO-20260812-001
    robot_instance_id BIGINT REFERENCES robot_instance(id),
    alarm_code        VARCHAR(20),                 -- SRVO-050（Neo4j 跨存储关联）
    title             VARCHAR(200) NOT NULL,
    description       TEXT,
    priority          VARCHAR(10) NOT NULL DEFAULT 'normal'
                      CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status            VARCHAR(20) NOT NULL DEFAULT 'created'
                      CHECK (status IN ('created', 'assigned', 'in_progress', 'resolved', 'closed')),
    assignee_id       BIGINT REFERENCES sys_user(id), -- 指派工程师
    created_by        BIGINT REFERENCES sys_user(id),
    diagnosis_context JSONB,                        -- 诊断结论快照（Supervisor 输出）
    assigned_at       TIMESTAMPTZ,
    resolved_at       TIMESTAMPTZ,
    closed_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  work_order                   IS '排障工单：记录报警→诊断→指派→处理→验收的完整过程状态流转';
COMMENT ON COLUMN work_order.id                IS '工单 ID（主键）';
COMMENT ON COLUMN work_order.work_order_no     IS '工单号（唯一，如 WO-20260812-001）';
COMMENT ON COLUMN work_order.robot_instance_id IS '关联机器人实例（外键 → robot_instance.id）';
COMMENT ON COLUMN work_order.alarm_code        IS '报警码（如 SRVO-050，在 Neo4j 查详情）';
COMMENT ON COLUMN work_order.title             IS '工单标题';
COMMENT ON COLUMN work_order.description       IS '问题描述';
COMMENT ON COLUMN work_order.priority          IS '优先级：low / normal / high / urgent';
COMMENT ON COLUMN work_order.status            IS '状态流转：created→assigned→in_progress→resolved→closed';
COMMENT ON COLUMN work_order.assignee_id       IS '指派工程师（外键 → sys_user.id）';
COMMENT ON COLUMN work_order.created_by        IS '创建人（外键 → sys_user.id）';
COMMENT ON COLUMN work_order.diagnosis_context IS '诊断结论快照（JSONB，Supervisor 输出）';
COMMENT ON COLUMN work_order.assigned_at       IS '指派时间';
COMMENT ON COLUMN work_order.resolved_at       IS '解决时间';
COMMENT ON COLUMN work_order.closed_at         IS '关闭时间';
COMMENT ON COLUMN work_order.created_at        IS '创建时间';
COMMENT ON COLUMN work_order.updated_at        IS '最后更新时间';
CREATE INDEX IF NOT EXISTS idx_work_order_status   ON work_order(status, priority);
CREATE INDEX IF NOT EXISTS idx_work_order_assignee ON work_order(assignee_id);
CREATE INDEX IF NOT EXISTS idx_work_order_alarm    ON work_order(alarm_code);

-- =====================================================================
-- 运维模块
-- =====================================================================

-- 维修历史：与工单区别——工单记过程状态，这里记最终处理结果
CREATE TABLE IF NOT EXISTS maintenance_log (
    id                BIGSERIAL PRIMARY KEY,
    work_order_no     VARCHAR(30),                 -- 与 work_order 通过工单号关联
    robot_instance_id BIGINT REFERENCES robot_instance(id),
    alarm_code        VARCHAR(20),
    engineer_id       BIGINT REFERENCES sys_user(id),
    fault_description TEXT,
    root_cause        TEXT,
    sop_used          TEXT,
    parts_used        JSONB,                       -- 不同维修备件不同，JSONB 灵活扩展
    downtime_minutes  INT,
    occurred_at       TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  maintenance_log                IS '维修历史：记录最终处理结果（故障、根因、所用 SOP/备件、停机时长）';
COMMENT ON COLUMN maintenance_log.id             IS '日志 ID（主键）';
COMMENT ON COLUMN maintenance_log.work_order_no  IS '关联工单号（与 work_order 关联）';
COMMENT ON COLUMN maintenance_log.robot_instance_id IS '维修对象（外键 → robot_instance.id）';
COMMENT ON COLUMN maintenance_log.alarm_code     IS '报警码';
COMMENT ON COLUMN maintenance_log.engineer_id    IS '处理工程师（外键 → sys_user.id）';
COMMENT ON COLUMN maintenance_log.fault_description IS '故障现象描述';
COMMENT ON COLUMN maintenance_log.root_cause     IS '根因分析';
COMMENT ON COLUMN maintenance_log.sop_used       IS '采用的 SOP（来自知识图谱）';
COMMENT ON COLUMN maintenance_log.parts_used     IS '使用的备件清单（JSONB 数组，结构灵活）';
COMMENT ON COLUMN maintenance_log.downtime_minutes IS '停机时长（分钟）';
COMMENT ON COLUMN maintenance_log.occurred_at    IS '故障发生时间';
COMMENT ON COLUMN maintenance_log.created_at     IS '记录时间';
CREATE INDEX IF NOT EXISTS idx_maintenance_log_robot    ON maintenance_log(robot_instance_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_alarm    ON maintenance_log(alarm_code);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_work_no  ON maintenance_log(work_order_no);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_engineer ON maintenance_log(engineer_id);

-- 伺服参数变更历史：谁在什么时候改了什么参数
CREATE TABLE IF NOT EXISTS servo_param_history (
    id                BIGSERIAL PRIMARY KEY,
    robot_instance_id BIGINT REFERENCES robot_instance(id),
    robot_model_id    BIGINT REFERENCES robot_model(id),
    param_code        VARCHAR(50) NOT NULL,
    old_value         NUMERIC(12, 4),
    new_value         NUMERIC(12, 4),
    changed_by        BIGINT REFERENCES sys_user(id),
    reason            TEXT,
    changed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  servo_param_history              IS '伺服参数变更历史：可追溯谁在何时改了哪台设备的参数';
COMMENT ON COLUMN servo_param_history.id           IS '变更记录 ID（主键）';
COMMENT ON COLUMN servo_param_history.robot_instance_id IS '变更对象（外键 → robot_instance.id）';
COMMENT ON COLUMN servo_param_history.robot_model_id IS '型号（冗余，便于按型号统计）';
COMMENT ON COLUMN servo_param_history.param_code   IS '被修改的参数代码';
COMMENT ON COLUMN servo_param_history.old_value    IS '变更前值';
COMMENT ON COLUMN servo_param_history.new_value    IS '变更后值';
COMMENT ON COLUMN servo_param_history.changed_by   IS '修改人（外键 → sys_user.id）';
COMMENT ON COLUMN servo_param_history.reason       IS '修改原因';
COMMENT ON COLUMN servo_param_history.changed_at   IS '变更时间';
CREATE INDEX IF NOT EXISTS idx_servo_param_history_param
    ON servo_param_history(robot_instance_id, param_code, changed_at DESC);

-- =====================================================================
-- RAG 模块
-- =====================================================================

-- 知识库文档元数据（一份上传的 PDF/DOCX 等）
CREATE TABLE IF NOT EXISTS knowledge_base_document (
    id               BIGSERIAL PRIMARY KEY,
    title            VARCHAR(200) NOT NULL,
    category         VARCHAR(50),                  -- 文档分类（如 报警手册 / 操作手册）
    source_url       TEXT,
    brand            VARCHAR(20),                  -- FANUC/ABB/...
    robot_model      VARCHAR(50),                  -- 机器人型号（如 R-2000iC/210L）
    file_path        VARCHAR(500),                 -- 七牛云对象 key
    parse_result_path VARCHAR(500),                -- 七牛云对象 key（MinerU 解析产物 content_list.json）
    chunk_count      INT NOT NULL DEFAULT 0,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                      CHECK (processing_status IN ('PENDING', 'PROCESSING', 'READY', 'FAILED')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE  knowledge_base_document              IS '知识库文档元数据：一份上传的 PDF/DOCX 等（MinerU 在线解析入库）';
COMMENT ON COLUMN knowledge_base_document.id           IS '文档 ID（主键）';
COMMENT ON COLUMN knowledge_base_document.title        IS '文档标题';
COMMENT ON COLUMN knowledge_base_document.category     IS '文档分类（如 报警手册 / 操作手册，用于检索过滤）';
COMMENT ON COLUMN knowledge_base_document.source_url   IS '来源 URL（公开手册抓取时记录）';
COMMENT ON COLUMN knowledge_base_document.brand        IS '品牌（FANUC / ABB / ...，嵌入时下沉到 chunk 元数据，用于检索过滤）';
COMMENT ON COLUMN knowledge_base_document.robot_model  IS '机器人型号（如 R-2000iC/210L，嵌入时下沉到 chunk 元数据，用于检索过滤）';
COMMENT ON COLUMN knowledge_base_document.file_path    IS '七牛云对象 key（原始文件）';
COMMENT ON COLUMN knowledge_base_document.parse_result_path IS '七牛云对象 key（MinerU 解析产物 content_list.json，供重分块复用）';
COMMENT ON COLUMN knowledge_base_document.chunk_count  IS '分块数量';
COMMENT ON COLUMN knowledge_base_document.processing_status IS '解析状态：PENDING / PROCESSING / READY / FAILED';
COMMENT ON COLUMN knowledge_base_document.created_at   IS '创建时间';
COMMENT ON COLUMN knowledge_base_document.updated_at   IS '最后更新时间';
CREATE INDEX IF NOT EXISTS idx_kb_doc_status ON knowledge_base_document(processing_status);

-- 文档分块：text 向量存 Milvus；table/image 仅存 PG + OSS 资产（不入向量库）
CREATE TABLE IF NOT EXISTS knowledge_base_document_chunk (
    id           BIGSERIAL PRIMARY KEY,
    document_id  BIGINT NOT NULL REFERENCES knowledge_base_document(id) ON DELETE CASCADE,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    chunk_type   VARCHAR(20) NOT NULL DEFAULT 'text',  -- text / table / image
    embed_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                 CHECK (embed_status IN ('PENDING', 'VECTORIZED', 'STORED', 'FAILED')),
    milvus_id    VARCHAR(100),                      -- 向量在 Milvus，仅 text 分块有值
    asset_key    VARCHAR(255),                      -- 附件 OSS 对象 key（图片；表格预留）
    section      TEXT,
    page         INT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);
COMMENT ON TABLE  knowledge_base_document_chunk          IS '文档分块：text 向量存 Milvus，table/image 仅存 PG + OSS 资产';
COMMENT ON COLUMN knowledge_base_document_chunk.id       IS '分块 ID（主键）';
COMMENT ON COLUMN knowledge_base_document_chunk.document_id IS '所属文档（外键 → knowledge_base_document.id，级联删除）';
COMMENT ON COLUMN knowledge_base_document_chunk.chunk_index IS '块序号（文档内从 0 开始）；table/image 占位符 [table_{chunk_index}]/[image_{chunk_index}] 引用它';
COMMENT ON COLUMN knowledge_base_document_chunk.content  IS '分块内容（text=章节+正文；table=Markdown 表格；image=图题/描述）';
COMMENT ON COLUMN knowledge_base_document_chunk.chunk_type IS '分块类型：text / table / image';
COMMENT ON COLUMN knowledge_base_document_chunk.embed_status IS '嵌入/入库状态：PENDING / VECTORIZED(text) / STORED(table、image) / FAILED';
COMMENT ON COLUMN knowledge_base_document_chunk.milvus_id IS 'Milvus 向量 ID（向量本体存 Milvus；仅 text 有值）';
COMMENT ON COLUMN knowledge_base_document_chunk.asset_key IS '附件 OSS 对象 key（图片必填；表格预留）';
COMMENT ON COLUMN knowledge_base_document_chunk.section  IS '所属章节';
COMMENT ON COLUMN knowledge_base_document_chunk.page     IS '来源页码';
COMMENT ON COLUMN knowledge_base_document_chunk.created_at IS '创建时间';
CREATE INDEX IF NOT EXISTS idx_kb_chunk_doc     ON knowledge_base_document_chunk(document_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_type    ON knowledge_base_document_chunk(chunk_type);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_status  ON knowledge_base_document_chunk(chunk_type, embed_status);
