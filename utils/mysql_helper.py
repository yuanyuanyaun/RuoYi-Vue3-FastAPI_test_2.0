"""
mysql_helper：数据库访问工具层（PyMySQL 封装）。

职责：
    1. 为测试用例提供直接的 SQL 查询/执行能力，支撑数据库校验类断言
    2. 提供数据库重置函数（环境初始化用，不接入 pytest 生命周期）

数据库校验的使用场景（技术判断标准）：
    - API 响应层面无法验证的事实：例如"分配不存在的用户"呈现假成功的已知缺陷——
      已分配列表接口因 JOIN 用户表查不到关联而返回空，只有直接查询 sys_user_role
      关联表才能证明孤儿数据（如用户 999 与角色 2 的关联）确实被插入
    - 事务回滚的落库证明、删除后 del_flag 软删除（del_flag='2'）的事实验证
    - 测试结束后的残留数据确认（清理策略的兜底检查）

不需要数据库校验的场景：
    - 正常成功用例：API 断言（响应码 + 查询接口验证）已闭环，查库属于重复验证
    - 无副作用的假成功：如删除不存在的记录，未产生任何数据变化

使用约定：
    - 连接开启 autocommit=True：查询不受影响，execute_sql 的写操作立即落库
    - 游标使用 DictCursor：查询结果以字典返回，按 row["字段名"] 取值
"""
import os
import pymysql
from config.setting import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_conn():
    """创建数据库连接（内部使用）：按全局配置组装连接参数。"""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",  # utf8mb4 编码完整覆盖多字节字符，避免中文字符乱码
        autocommit=True,  # 自动提交：写操作立即生效落库，无需显式 commit
        cursorclass=pymysql.cursors.DictCursor  # 字典游标：查询结果以字典返回，按字段名取值
    )


def query_one(sql, params=None):
    """查询单条记录；连接在 finally 中关闭，保证资源释放。"""
    conn = _get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()
    finally:
        conn.close()


def query_all(sql, params=None):
    """查询全部记录。"""
    conn = _get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        conn.close()


def execute_sql(sql, params=None):
    """执行非查询 SQL（INSERT/UPDATE/DELETE）：autocommit 下写操作立即落库。"""
    conn = _get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
    finally:
        conn.close()


def reset_database():
    """执行 scripts/reset_mysql.sql 重置数据库（手动/CI 环境初始化用，不接入 pytest 生命周期）。"""
    conn = _get_conn()
    try:
        with conn.cursor() as cursor:
            # 读取重置脚本，按分号拆分为单条语句后逐条执行
            with open(os.path.join(BASE_DIR, "scripts", "reset_mysql.sql"), encoding="utf-8") as f:
                sql_content = f.read()
            statements = [s.strip() for s in sql_content.split(";") if s.strip()]
            for stmt in statements:
                cursor.execute(stmt)
        print("\n数据库重置完成")
    finally:
        conn.close()
