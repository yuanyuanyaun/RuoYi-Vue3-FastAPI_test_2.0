-- ============================================================
-- RuoYi-Vue3-FastAPI 测试数据重置脚本（冒烟测试与回归测试共用的数据环境准备工具）。
--
-- 文件职责：
--     每次执行将 11 张核心表（5 张业务表 + 4 张关联表 + 2 张日志表）恢复为基准初始状态，
--     清除用例执行过程中产生的脏数据，为依赖初始数据的用例提供
--     确定性、可重复执行的数据环境。
--
-- 覆盖范围：
--     业务表   sys_user / sys_role / sys_menu / sys_dept / sys_post
--     关联表   sys_user_role / sys_user_post / sys_role_menu / sys_role_dept
--     日志表   sys_oper_log / sys_logininfor（运行期写入，无基准初始数据）
--
-- 设计约束：
--     - 清空统一使用 TRUNCATE 而非 DELETE：TRUNCATE 同时重置自增主键，
--       保证每次执行后主键从基准值开始，用例对主键与记录数量的断言稳定可复现；
--       DELETE 仅删除数据行、不重置自增计数器，无法满足该契约。
--     - 不重置 sys_config 参数表：验证码开关等系统参数保留当前运行值，
--       避免影响登录等依赖系统配置的用例，实现数据环境与系统配置的隔离。
--     - 不操作 Redis 缓存：验证码等参数缓存由后端写入/失效逻辑自行处理，
--       本脚本仅负责关系型数据库侧的数据复位。
--     - 清空顺序遵循外键依赖方向：先清空关联表与日志表，后清空业务表，
--       避免清空过程中触发外键约束冲突。
--
-- 执行方式（数据库需已存在，于项目根目录执行）：
--     mysql -uroot -p123456 ruoyi-fastapi < scripts/reset_mysql.sql
-- ============================================================

-- 设置客户端字符集为 utf8mb4：种子数据包含中文，与库表字符集保持一致，
-- 避免数据经 mysql 客户端传输时发生编码错乱（乱码）
SET NAMES utf8mb4;
-- 临时关闭外键检查：TRUNCATE 无法直接清空仍被其他表外键引用的表，
-- 先解除约束校验以便顺利清空全部目标表，脚本末尾再恢复检查
SET FOREIGN_KEY_CHECKS = 0;

-- 1) 清空 11 张表（TRUNCATE 同时重置自增主键，保证主键从基准值开始）
--    清空顺序遵循外键依赖方向：先清空 4 张关联表（sys_user_role / sys_user_post /
--    sys_role_menu / sys_role_dept），再清空 2 张日志表，最后清空 5 张业务表，
--    避免清空过程中触发外键约束冲突
TRUNCATE TABLE sys_user_role;
TRUNCATE TABLE sys_user_post;
TRUNCATE TABLE sys_role_menu;
TRUNCATE TABLE sys_role_dept;
-- 日志表：由系统运行期写入（操作日志 / 登录日志），无基准初始数据，仅需清空
TRUNCATE TABLE sys_oper_log;
TRUNCATE TABLE sys_logininfor;
-- 业务表：其数据被关联表及子级数据引用，放于最后清空
TRUNCATE TABLE sys_user;
TRUNCATE TABLE sys_role;
TRUNCATE TABLE sys_menu;
TRUNCATE TABLE sys_dept;
TRUNCATE TABLE sys_post;

-- 2) 恢复基准数据
-- 重建各表初始记录，供依赖初始状态的用例使用，典型场景包括：
--     - admin / niangao 两个种子账号支撑登录、认证与权限校验类用例
--     - 角色、菜单、部门、岗位数据支撑菜单树断言、数据权限范围校验与参数化查询

-- -------- sys_dept：部门树基准数据 --------
-- 构造 10 个部门的四级树形结构：根节点 id=100（集团总公司）→ 分公司（101/102）→ 部门（103~109）
-- 字段说明：
--     ancestors（如 '0,100,101'）为祖级路径，标识该节点在部门树中的完整上级链，
--     数据权限范围判定（仅可见授权部门及其子级）依赖该字段，勿随意改动
--     parent_id 为父节点 id，根节点父 id 为 0；order_num 决定同级部门的展示顺序
-- 该数据支撑部门管理用例的树查询、新增子部门、数据权限范围过滤等断言
insert into sys_dept values(100,  0,   '0',          '集团总公司',   0, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(101,  100, '0,100',      '深圳分公司', 1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(102,  100, '0,100',      '长沙分公司', 2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(103,  101, '0,100,101',  '研发部门',   1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(104,  101, '0,100,101',  '市场部门',   2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(105,  101, '0,100,101',  '测试部门',   3, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(106,  101, '0,100,101',  '财务部门',   4, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(107,  101, '0,100,101',  '运维部门',   5, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(108,  102, '0,100,102',  '市场部门',   1, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);
insert into sys_dept values(109,  102, '0,100,102',  '财务部门',   2, '年糕', '15888888888', 'niangao@qq.com', '0', '0', 'admin', sysdate(), '', null);

-- -------- sys_user：用户基准数据 --------
-- 种子账号说明：
--     admin（user_id=1，密码 admin123）绑定角色 '1'（超级管理员），拥有全部权限，
--           支撑冒烟测试的正向主链路（登录 → 获取信息/路由 → 退出）与全局管理类用例
--     niangao（user_id=2，密码 admin123）绑定角色 '2'（普通角色），
--           用于权限受限场景，验证普通角色视角下的鉴权与数据权限过滤
-- 密码统一以 BCrypt 密文落库，与登录接口的校验逻辑对应；dept_id 关联部门树中的研发/测试部门
insert into sys_user values(1,  103, 'admin',   '超级管理员', '00', 'niangao@163.com', '15888888888', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '127.0.0.1', sysdate(), sysdate(), 'admin', sysdate(), '', null, '管理员');
insert into sys_user values(2,  105, 'niangao', '年糕', 			'00', 'niangao@qq.com',  '15666666666', '1', '', '$2a$10$7JB720yubVSZvUI0rEqK/.VqGOZTH.ulu33dHOiBE8ByOhJIrdAu2', '0', '0', '127.0.0.1', sysdate(), sysdate(), 'admin', sysdate(), '', null, '测试员');

-- -------- sys_post：岗位基准数据 --------
-- 构造 4 个岗位，岗位编码唯一（ceo / se / hr / user），
-- 岗位管理用例的列表查询、按编码参数化查询与新增时的唯一性校验均依赖该数据
insert into sys_post values(1, 'ceo',  '董事长',    1, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(2, 'se',   '项目经理',  2, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(3, 'hr',   '人力资源',  3, '0', 'admin', sysdate(), '', null, '');
insert into sys_post values(4, 'user', '普通员工',  4, '0', 'admin', sysdate(), '', null, '');

-- -------- sys_role：角色基准数据 --------
-- role_id '1'（超级管理员）：后端按角色标识直接放行，无需菜单权限配置即拥有全部权限；
-- role_id '2'（普通角色）：其菜单与按钮权限集合由关联表 sys_role_menu 全量绑定（见后文），
-- 用于普通角色视角的菜单树、按钮权限与接口鉴权断言
insert into sys_role values('1', '超级管理员',  'admin',  1, 1, 1, 1, '0', '0', 'admin', sysdate(), '', null, '超级管理员');
insert into sys_role values('2', '普通角色',    'common', 2, 2, 1, 1, '0', '0', 'admin', sysdate(), '', null, '普通角色');

-- -------- sys_menu：菜单与按钮权限基准数据 --------
-- 菜单权限采用 目录(M) / 菜单(C) / 按钮(F) 三级结构：
--     M 目录：一级/二级导航目录（如 系统管理、日志管理），不挂载页面组件
--     C 菜单：可访问的页面菜单，path 指向前端路由、component 指向页面组件
--     F 按钮：页面内的操作按钮，perms 权限标识（如 system:user:list）与后端接口
--             鉴权注解一一对应，接口级权限控制依据该标识判定
-- 普通角色（role_id '2'）的完整权限集合由 sys_role_menu 全量绑定，见下文关联表部分
insert into sys_menu values('1',  '系统管理', '0', '1',  'system',           null, '', '', 1, 0, 'M', '0', '0', '', 'system',   'admin', sysdate(), '', null, '系统管理目录');
insert into sys_menu values('2',  '系统监控', '0', '2',  'monitor',          null, '', '', 1, 0, 'M', '0', '0', '', 'monitor',  'admin', sysdate(), '', null, '系统监控目录');
insert into sys_menu values('3',  '系统工具', '0', '3',  'tool',             null, '', '', 1, 0, 'M', '0', '0', '', 'tool',     'admin', sysdate(), '', null, '系统工具目录');
insert into sys_menu values('99', '若依官网', '0', '99', 'http://ruoyi.vip', null, '', '', 0, 0, 'M', '0', '0', '', 'guide',    'admin', sysdate(), '', null, '若依官网地址');
-- 以下为系统管理（id=1）下的子菜单（C），order_num 决定侧边栏展示顺序
insert into sys_menu values('100',  '用户管理', '1',   '1', 'user',                'system/user/index',                 '', '', 1, 0, 'C', '0', '0', 'system:user:list',                 'user',          'admin', sysdate(), '', null, '用户管理菜单');
insert into sys_menu values('101',  '角色管理', '1',   '2', 'role',                'system/role/index',                 '', '', 1, 0, 'C', '0', '0', 'system:role:list',                 'peoples',       'admin', sysdate(), '', null, '角色管理菜单');
insert into sys_menu values('102',  '菜单管理', '1',   '3', 'menu',                'system/menu/index',                 '', '', 1, 0, 'C', '0', '0', 'system:menu:list',                 'tree-table',    'admin', sysdate(), '', null, '菜单管理菜单');
insert into sys_menu values('103',  '部门管理', '1',   '4', 'dept',                'system/dept/index',                 '', '', 1, 0, 'C', '0', '0', 'system:dept:list',                 'tree',          'admin', sysdate(), '', null, '部门管理菜单');
insert into sys_menu values('104',  '岗位管理', '1',   '5', 'post',                'system/post/index',                 '', '', 1, 0, 'C', '0', '0', 'system:post:list',                 'post',          'admin', sysdate(), '', null, '岗位管理菜单');
insert into sys_menu values('105',  '字典管理', '1',   '6', 'dict',                'system/dict/index',                 '', '', 1, 0, 'C', '0', '0', 'system:dict:list',                 'dict',          'admin', sysdate(), '', null, '字典管理菜单');
insert into sys_menu values('106',  '参数设置', '1',   '7', 'config',              'system/config/index',               '', '', 1, 0, 'C', '0', '0', 'system:config:list',               'edit',          'admin', sysdate(), '', null, '参数设置菜单');
insert into sys_menu values('107',  '通知公告', '1',   '8', 'notice',              'system/notice/index',               '', '', 1, 0, 'C', '0', '0', 'system:notice:list',               'message',       'admin', sysdate(), '', null, '通知公告菜单');
-- 日志管理（id=108）为二级目录（M），其下子菜单 500/501 于菜单区后段登记
insert into sys_menu values('108',  '日志管理', '1',   '9', 'log',                 '',                                  '', '', 1, 0, 'M', '0', '0', '',                                 'log',           'admin', sysdate(), '', null, '日志管理菜单');
insert into sys_menu values('119',  '文件管理', '1',  '10', 'file',                'system/file/index',                 '', '', 1, 0, 'C', '0', '0', 'system:file:list',                 'documentation', 'admin', sysdate(), '', null, '文件管理菜单');
insert into sys_menu values('120',  '插件管理', '1',  '11', 'plugin',              'system/plugin/index',               '', '', 1, 0, 'C', '0', '0', 'system:plugin:list',               'component',     'admin', sysdate(), '', null, '插件管理菜单');
-- 以下为系统监控（id=2）下的子菜单（C），含在线用户、定时任务、缓存监控等运维页面
insert into sys_menu values('109',  '在线用户', '2',   '1', 'online',              'monitor/online/index',              '', '', 1, 0, 'C', '0', '0', 'monitor:online:list',              'online',        'admin', sysdate(), '', null, '在线用户菜单');
insert into sys_menu values('110',  '定时任务', '2',   '2', 'job',                 'monitor/job/index',                 '', '', 1, 0, 'C', '0', '0', 'monitor:job:list',                 'job',           'admin', sysdate(), '', null, '定时任务菜单');
insert into sys_menu values('111',  '数据监控', '2',   '3', 'druid',               'monitor/druid/index',               '', '', 1, 0, 'C', '0', '0', 'monitor:druid:list',               'druid',         'admin', sysdate(), '', null, '数据监控菜单');
insert into sys_menu values('112',  '服务监控', '2',   '4', 'server',              'monitor/server/index',              '', '', 1, 0, 'C', '0', '0', 'monitor:server:list',              'server',        'admin', sysdate(), '', null, '服务监控菜单');
insert into sys_menu values('113',  '缓存监控', '2',   '5', 'cache',               'monitor/cache/index',               '', '', 1, 0, 'C', '0', '0', 'monitor:cache:list',               'redis',         'admin', sysdate(), '', null, '缓存监控菜单');
insert into sys_menu values('114',  '缓存列表', '2',   '6', 'cacheList',           'monitor/cache/list',                '', '', 1, 0, 'C', '0', '0', 'monitor:cache:list',               'redis-list',    'admin', sysdate(), '', null, '缓存列表菜单');
insert into sys_menu values('118',  '传输加密', '2',   '7', 'transportCrypto',     'monitor/transportCrypto/index',     '', '', 1, 0, 'C', '0', '0', 'monitor:transportCrypto:list',     'chart',         'admin', sysdate(), '', null, '传输加密监控菜单');
-- 以下为系统工具（id=3）下的子菜单（C）
insert into sys_menu values('115',  '表单构建', '3',   '1', 'build',               'tool/build/index',                  '', '', 1, 0, 'C', '0', '0', 'tool:build:list',                  'build',         'admin', sysdate(), '', null, '表单构建菜单');
insert into sys_menu values('116',  '代码生成', '3',   '2', 'gen',                 'tool/gen/index',                    '', '', 1, 0, 'C', '0', '0', 'tool:gen:list',                    'code',          'admin', sysdate(), '', null, '代码生成菜单');
insert into sys_menu values('117',  '系统接口', '3',   '3', 'swagger',             'tool/swagger/index',                '', '', 1, 0, 'C', '0', '0', 'tool:swagger:list',                'swagger',       'admin', sysdate(), '', null, '系统接口菜单');
-- 以下为日志管理目录（id=108）下的操作日志/登录日志子菜单（C）
insert into sys_menu values('500',  '操作日志', '108', '1', 'operlog',    'monitor/operlog/index',    '', '', 1, 0, 'C', '0', '0', 'monitor:operlog:list',    'form',          'admin', sysdate(), '', null, '操作日志菜单');
insert into sys_menu values('501',  '登录日志', '108', '2', 'logininfor', 'monitor/logininfor/index', '', '', 1, 0, 'C', '0', '0', 'monitor:logininfor:list', 'logininfor',    'admin', sysdate(), '', null, '登录日志菜单');
-- 以下为按钮级权限（F）：对应各菜单页面内的操作按钮，perms 权限标识被后端接口鉴权注解引用，
-- 用例通过持有/缺失某按钮权限验证接口级权限控制，父菜单 id（第 3 列）指明该按钮归属
insert into sys_menu values('1000', '用户查询', '100', '1',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1001', '用户新增', '100', '2',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1002', '用户修改', '100', '3',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1003', '用户删除', '100', '4',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1004', '用户导出', '100', '5',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:export',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1005', '用户导入', '100', '6',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:import',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1006', '重置密码', '100', '7',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:user:resetPwd',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1007', '角色查询', '101', '1',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:role:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1008', '角色新增', '101', '2',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:role:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1009', '角色修改', '101', '3',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:role:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1010', '角色删除', '101', '4',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:role:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1011', '角色导出', '101', '5',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:role:export',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1012', '菜单查询', '102', '1',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:menu:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1013', '菜单新增', '102', '2',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:menu:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1014', '菜单修改', '102', '3',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:menu:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1015', '菜单删除', '102', '4',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:menu:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1016', '部门查询', '103', '1',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:dept:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1017', '部门新增', '103', '2',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:dept:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1018', '部门修改', '103', '3',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:dept:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1019', '部门删除', '103', '4',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:dept:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1020', '岗位查询', '104', '1',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:post:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1021', '岗位新增', '104', '2',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:post:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1022', '岗位修改', '104', '3',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:post:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1023', '岗位删除', '104', '4',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:post:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1024', '岗位导出', '104', '5',  '', '', '', '', 1, 0, 'F', '0', '0', 'system:post:export',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1025', '字典查询', '105', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:dict:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1026', '字典新增', '105', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:dict:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1027', '字典修改', '105', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:dict:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1028', '字典删除', '105', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:dict:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1029', '字典导出', '105', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:dict:export',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1030', '参数查询', '106', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:config:query',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1031', '参数新增', '106', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:config:creat',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1032', '参数修改', '106', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:config:edit',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1033', '参数删除', '106', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:config:remove',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1034', '参数导出', '106', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:config:export',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1035', '公告查询', '107', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:notice:query',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1036', '公告新增', '107', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:notice:creat',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1037', '公告修改', '107', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:notice:edit',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1038', '公告删除', '107', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:notice:remove',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1061', '文件查询', '119', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1062', '文件下载', '119', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:download',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1063', '文件删除', '119', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1064', '文件授权', '119', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1065', '文件转移', '119', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:transfer',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1066', '文件恢复', '119', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:restore',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1067', '文件清理', '119', '7', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:purge',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1068', '存储对账', '119', '8', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:file:reconcile',      '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1069', '插件查询', '120', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:plugin:query',        '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1070', '插件修改', '120', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:plugin:edit',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1071', '插件列表', '120', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:plugin:list',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1072', '插件导出', '120', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'system:plugin:export',       '#', 'admin', sysdate(), '', null, '');
-- 以下为日志管理子菜单（500 操作日志 / 501 登录日志）下的按钮权限（F）
insert into sys_menu values('1039', '操作查询', '500', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:query',      '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1040', '操作删除', '500', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:remove',     '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1041', '日志导出', '500', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:operlog:export',     '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1042', '登录查询', '501', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:query',   '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1043', '登录删除', '501', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:remove',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1044', '日志导出', '501', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:export',  '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1045', '账户解锁', '501', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:logininfor:unlock',  '#', 'admin', sysdate(), '', null, '');
-- 以下为系统监控（id=2）下各菜单的按钮权限（F）
insert into sys_menu values('1046', '在线查询', '109', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:online:query',       '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1047', '批量强退', '109', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:online:batchLogout', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1048', '单条强退', '109', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:online:forceLogout', '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1049', '任务查询', '110', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:query',          '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1050', '任务新增', '110', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:creat',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1051', '任务修改', '110', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:edit',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1052', '任务删除', '110', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:remove',         '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1053', '状态修改', '110', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:changeStatus',   '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1054', '任务导出', '110', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'monitor:job:export',         '#', 'admin', sysdate(), '', null, '');
-- 以下为代码生成菜单（116）下的按钮权限（F）
insert into sys_menu values('1055', '生成查询', '116', '1', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:query',             '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1056', '生成修改', '116', '2', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:edit',              '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1057', '生成删除', '116', '3', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:remove',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1058', '导入代码', '116', '4', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:import',            '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1059', '预览代码', '116', '5', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:preview',           '#', 'admin', sysdate(), '', null, '');
insert into sys_menu values('1060', '生成代码', '116', '6', '#', '', '', '', 1, 0, 'F', '0', '0', 'tool:gen:code',              '#', 'admin', sysdate(), '', null, '');

-- -------- sys_user_role：用户-角色关联表 --------
-- 建立用户与角色的多对多关联：user_id=1 -> role '1'（超级管理员），user_id=2 -> role '2'（普通角色），
-- 登录后接口鉴权与菜单路由解析均依据该关联确定当前用户角色
insert into sys_user_role values ('1', '1');
insert into sys_user_role values ('2', '2');

-- -------- sys_role_menu：角色-菜单关联表 --------
-- 为普通角色（role_id '2'）绑定全部菜单与按钮权限，覆盖 M 目录 / C 菜单 / F 按钮三层节点，
-- 使权限类用例可在"普通角色持有全量权限"的前提下按角色标识做鉴权断言；
-- 超级管理员（role '1'）由后端按角色标识直接放行，无需在此登记权限
insert into sys_role_menu values ('2', '1');
insert into sys_role_menu values ('2', '2');
insert into sys_role_menu values ('2', '3');
insert into sys_role_menu values ('2', '100');
insert into sys_role_menu values ('2', '101');
insert into sys_role_menu values ('2', '102');
insert into sys_role_menu values ('2', '103');
insert into sys_role_menu values ('2', '104');
insert into sys_role_menu values ('2', '105');
insert into sys_role_menu values ('2', '106');
insert into sys_role_menu values ('2', '107');
insert into sys_role_menu values ('2', '108');
insert into sys_role_menu values ('2', '109');
insert into sys_role_menu values ('2', '110');
insert into sys_role_menu values ('2', '111');
insert into sys_role_menu values ('2', '112');
insert into sys_role_menu values ('2', '113');
insert into sys_role_menu values ('2', '114');
insert into sys_role_menu values ('2', '118');
insert into sys_role_menu values ('2', '119');
insert into sys_role_menu values ('2', '120');
insert into sys_role_menu values ('2', '115');
insert into sys_role_menu values ('2', '116');
insert into sys_role_menu values ('2', '117');
insert into sys_role_menu values ('2', '500');
insert into sys_role_menu values ('2', '501');
insert into sys_role_menu values ('2', '1000');
insert into sys_role_menu values ('2', '1001');
insert into sys_role_menu values ('2', '1002');
insert into sys_role_menu values ('2', '1003');
insert into sys_role_menu values ('2', '1004');
insert into sys_role_menu values ('2', '1005');
insert into sys_role_menu values ('2', '1006');
insert into sys_role_menu values ('2', '1007');
insert into sys_role_menu values ('2', '1008');
insert into sys_role_menu values ('2', '1009');
insert into sys_role_menu values ('2', '1010');
insert into sys_role_menu values ('2', '1011');
insert into sys_role_menu values ('2', '1012');
insert into sys_role_menu values ('2', '1013');
insert into sys_role_menu values ('2', '1014');
insert into sys_role_menu values ('2', '1015');
insert into sys_role_menu values ('2', '1016');
insert into sys_role_menu values ('2', '1017');
insert into sys_role_menu values ('2', '1018');
insert into sys_role_menu values ('2', '1019');
insert into sys_role_menu values ('2', '1020');
insert into sys_role_menu values ('2', '1021');
insert into sys_role_menu values ('2', '1022');
insert into sys_role_menu values ('2', '1023');
insert into sys_role_menu values ('2', '1024');
insert into sys_role_menu values ('2', '1025');
insert into sys_role_menu values ('2', '1026');
insert into sys_role_menu values ('2', '1027');
insert into sys_role_menu values ('2', '1028');
insert into sys_role_menu values ('2', '1029');
insert into sys_role_menu values ('2', '1030');
insert into sys_role_menu values ('2', '1031');
insert into sys_role_menu values ('2', '1032');
insert into sys_role_menu values ('2', '1033');
insert into sys_role_menu values ('2', '1034');
insert into sys_role_menu values ('2', '1035');
insert into sys_role_menu values ('2', '1036');
insert into sys_role_menu values ('2', '1037');
insert into sys_role_menu values ('2', '1038');
insert into sys_role_menu values ('2', '1039');
insert into sys_role_menu values ('2', '1040');
insert into sys_role_menu values ('2', '1041');
insert into sys_role_menu values ('2', '1042');
insert into sys_role_menu values ('2', '1043');
insert into sys_role_menu values ('2', '1044');
insert into sys_role_menu values ('2', '1045');
insert into sys_role_menu values ('2', '1046');
insert into sys_role_menu values ('2', '1047');
insert into sys_role_menu values ('2', '1048');
insert into sys_role_menu values ('2', '1049');
insert into sys_role_menu values ('2', '1050');
insert into sys_role_menu values ('2', '1051');
insert into sys_role_menu values ('2', '1052');
insert into sys_role_menu values ('2', '1053');
insert into sys_role_menu values ('2', '1054');
insert into sys_role_menu values ('2', '1055');
insert into sys_role_menu values ('2', '1056');
insert into sys_role_menu values ('2', '1057');
insert into sys_role_menu values ('2', '1058');
insert into sys_role_menu values ('2', '1059');
insert into sys_role_menu values ('2', '1060');
insert into sys_role_menu values ('2', '1061');
insert into sys_role_menu values ('2', '1062');
insert into sys_role_menu values ('2', '1063');
insert into sys_role_menu values ('2', '1064');
insert into sys_role_menu values ('2', '1065');
insert into sys_role_menu values ('2', '1066');
insert into sys_role_menu values ('2', '1067');
insert into sys_role_menu values ('2', '1068');
insert into sys_role_menu values ('2', '1069');
insert into sys_role_menu values ('2', '1070');
insert into sys_role_menu values ('2', '1071');
insert into sys_role_menu values ('2', '1072');

-- -------- sys_role_dept：角色-部门关联表（数据权限范围） --------
-- 为普通角色（role '2'）绑定 100/101/105 部门及其子级作为可见的数据权限范围，
-- 数据权限用例据此验证"仅可见授权部门及其子级数据"的过滤规则
insert into sys_role_dept values ('2', '100');
insert into sys_role_dept values ('2', '101');
insert into sys_role_dept values ('2', '105');

-- -------- sys_user_post：用户-岗位关联表 --------
-- 建立用户与岗位的多对多关联：user_id=1 -> 岗位 1（董事长），user_id=2 -> 岗位 2（项目经理），
-- 用户管理用例的岗位回显与按岗位筛选均依赖该关联数据
insert into sys_user_post values ('1', '1');
insert into sys_user_post values ('2', '2');

-- 恢复外键检查：数据重置完成后，后续数据库操作重新受外键约束保护，
-- 避免测试过程中产生孤立数据破坏引用完整性
SET FOREIGN_KEY_CHECKS = 1;

-- 脚本执行完毕：11 张表已恢复至基准初始状态，可开始执行冒烟/回归测试用例
