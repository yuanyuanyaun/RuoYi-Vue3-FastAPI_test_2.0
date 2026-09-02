"""testcases 目录的 pytest 全局配置文件：统一提供所有测试用例共享的环境夹具（fixtures）与用例结果钩子。

覆盖接口（经由各模块接口封装夹具注入用例文件，用例仅需声明参数名即可自动注入）：
    LoginApi   登录模块接口封装：账号密码登录、获取用户信息、获取动态路由、退出登录
    RoleApi    角色模块接口封装：角色增删改查与菜单权限分配
    UserApi    用户模块接口封装：用户增删改查与状态管理
    PostApi    岗位模块接口封装：岗位增删改查
    MenuApi    菜单模块接口封装：菜单增删改查（列表为非分页接口）
    DeptApi    部门模块接口封装：部门增删改查（列表为非分页接口，含父子层级）

测试策略：
    - 会话级夹具共享环境：client / token / mysql / xxx_api 在整个测试会话内仅初始化一次，
      跨用例复用 HTTP 连接、认证令牌与数据库工具，避免每个用例重复登录与重复建连。
    - 函数级数据工厂夹具（creat_user / creat_role / creat_post / creat_menu / creat_dept）：
      用例内调用 creat(**overrides) 时，由工厂函数 make_xxx 构造最小必填数据 → 调用创建接口 →
      仅登记真实创建成功（业务 code==200）的记录，用例结束后 teardown 统一删除（自建自删，不留残留数据）。
    - 用例结果钩子 pytest_runtest_makereport：用例失败或 xfail 已知缺陷时，
      将最近一次 HTTP 请求与响应附加到 allure 报告，便于失败现场定位，无需另行查阅日志。
    - 数据隔离原则：不将数据库重置接入 pytest 生命周期，依靠自建自删保证用例间数据互不污染；
      重置工具仅保留为手动脚本，供 CI 全量初始化与种子数据恢复等场景使用。
"""

import pytest
import allure
from utils.function import make_role, make_user, make_post, make_menu, make_dept
from utils.api_client import APIClient
from utils.mysql_helper import query_one, query_all, execute_sql
from utils.role_api import RoleApi
from utils.user_api import UserApi
from utils.post_api import PostApi
from utils.menu_api import MenuApi
from utils.dept_api import DeptApi
from utils.login_api import LoginApi
from utils import api_client

# ============ 数据库重置（默认关闭）：仅供手动场景启用 ============
# reset_database() 会清空 11 张表并恢复种子数据，所有手动造的数据都会丢失，
# 因此不接入 pytest 生命周期：自建自删的清理策略已保证用例间数据隔离，
# 仅在 CI 全量初始化与种子数据被污染后恢复两种手动场景使用。
# 以下为已废弃的自动重置夹具，保持注释状态仅供查阅，不参与测试执行：
# from utils.mysql_helper import reset_database
#
#
# @pytest.fixture(scope="session", autouse=True)
# def reset_db_before_test():
#     reset_database()
#     yield


@pytest.fixture(scope="session")
def mysql():
    """数据库校验工具（会话级）：提供 query_one / query_all / execute_sql，供用例校验落库事实。"""
    return {
        "one": query_one,
        "all": query_all,
        "exec": execute_sql
    }


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """用例结果钩子：失败或 xfail 时把最近一次请求/响应附加到 allure 报告。"""
    box = yield
    rep = box.get_result()
    resp = api_client.last_response
    resq = api_client.last_request
    # xfail 已知缺陷用例（期望失败）→ 附加缺陷响应现场
    if rep.when == "call" and rep.skipped and getattr(rep, "wasxfail", None):
        if resp is not None:
            allure.attach(f"{resq}\nHTTP: {resp.status_code}\n{resp.text}",
                          "已知缺陷（xfail）响应现场", allure.attachment_type.TEXT)
            for header in ("request-id", "trace-id", "span-id"):
                if header in resp.headers:
                    allure.attach(resp.headers[header], header, allure.attachment_type.TEXT)
    # 用例真实失败（断言失败或异常）→ 附加失败响应现场
    if rep.failed and rep.when == "call":
        if resp is not None:
            allure.attach(
                f"{resq}\nHTTP: {resp.status_code}\n{resp.text}",
                "接口响应（失败现场）",
                allure.attachment_type.TEXT
            )
            for header in ("request-id", "trace-id", "span-id"):
                if header in resp.headers:
                    allure.attach(resp.headers[header], header, allure.attachment_type.TEXT)


@pytest.fixture
def creat_user(user_api):
    """创建用户并登记清理（ID 经列表反查），用例结束 teardown 自动删除。"""
    created_ids = []

    def creat(**overrides):
        data = make_user(**overrides)
        resp = user_api.creat(**data)
        user_id = None
        if resp.json()["code"] == 200:
            # 创建响应体不含 ID，按唯一业务名（userName）反查列表登记
            list_resp = user_api.list(userName=data["userName"]).json()
            rows = list_resp["rows"]
            if rows is not None and len(rows) > 0:
                user_id = rows[0]["userId"]
                created_ids.append(user_id)
        return resp, user_id, data["userName"]

    yield creat
    for uid in created_ids:
        user_api.delete(uid)


@pytest.fixture
def creat_role(role_api):
    """创建角色并登记清理（ID 经列表反查），用例结束 teardown 自动删除。"""
    created_ids = []

    def creat(**overrides):
        data = make_role(**overrides)
        resp = role_api.creat(**data)
        role_id = None
        if resp.json()["code"] == 200:
            list_resp = role_api.list(roleName=data["roleName"]).json()
            rows = list_resp["rows"]
            if rows is not None and len(rows) > 0:
                role_id = rows[0]["roleId"]
                created_ids.append(role_id)
        return resp, role_id, data["roleName"]

    yield creat
    for rid in created_ids:
        # 用 SQL 直连清掉该角色的全部用户关联（含"分配不存在用户"的孤儿关联——
        # 这类关联 allocated_users 查询不到、cancel_all 也处理不了）
        execute_sql("delete from sys_user_role where role_id=%s", (rid,))
        role_api.delete(rid)

@pytest.fixture
def creat_post(post_api):
    """创建岗位并登记清理（ID 经列表反查），用例结束 teardown 自动删除。"""
    created_ids = []

    def creat(**overrides):
        data = make_post(**overrides)
        resp = post_api.creat(**data)
        post_id = None
        if resp.json()["code"] == 200:
            list_resp = post_api.list(postCode=data["postCode"]).json()
            rows = list_resp["rows"]
            if rows is not None and len(rows) > 0:
                post_id = rows[0]["postId"]
                created_ids.append(post_id)
        return resp, post_id, data["postCode"]

    yield creat
    for pid in created_ids:
        post_api.delete(pid)


@pytest.fixture
def creat_menu(menu_api):
    """创建菜单并登记清理（ID 经列表反查），用例结束 teardown 自动删除。"""
    created_ids = []

    def creat(**overrides):
        data = make_menu(**overrides)
        resp = menu_api.creat(**data)
        menu_id = None
        if resp.json()["code"] == 200:
            # 菜单列表为非分页接口，数据在 data 数组
            list_resp = menu_api.list(menuName=data["menuName"]).json()
            rows = list_resp.get("data") or []
            if rows:
                menu_id = rows[0]["menuId"]
                created_ids.append(menu_id)
        return resp, menu_id, data["menuName"]

    yield creat
    for mid in created_ids:
        menu_api.delete(mid)


@pytest.fixture
def creat_dept(dept_api):
    """创建部门并登记清理（ID 经列表反查），用例结束 teardown 逆序自动删除。"""
    created_ids = []

    def creat(**overrides):
        data = make_dept(**overrides)
        resp = dept_api.creat(**data)
        dept_id = None
        if resp.json()["code"] == 200:
            list_resp = dept_api.list(deptName=data["deptName"]).json()
            rows = list_resp.get("data") or []
            if rows:
                dept_id = rows[0]["deptId"]
                created_ids.append(dept_id)
        return resp, dept_id, data["deptName"]

    yield creat
    # 逆序清理：子部门必须先于父部门删除，否则父部门删除命中"存在下级部门"601
    for did in reversed(created_ids):
        dept_api.delete(did)


@pytest.fixture(scope="session")
def client():
    """HTTP 客户端（会话级）：各模块 API 封装的底层依赖。"""
    return APIClient()


@pytest.fixture(scope="session")
def token(client):
    """admin 登录令牌（会话级）：整个会话仅登录一次，供所有接口共用。"""
    token = client.post(
        "login",
        data={"username": "admin",
              "password": "admin123"}
    ).json()["token"]
    return token


@pytest.fixture(scope="session")
def role_api(client, token):
    """角色模块接口封装（会话级）。"""
    return RoleApi(client, token)


@pytest.fixture(scope="session")
def user_api(client, token):
    """用户模块接口封装（会话级）。"""
    return UserApi(client, token)


@pytest.fixture(scope="session")
def login_api(client):
    """登录模块接口封装（会话级）。"""
    return LoginApi(client)


@pytest.fixture(scope="session")
def post_api(client, token):
    """岗位模块接口封装（会话级）。"""
    return PostApi(client, token)


@pytest.fixture(scope="session")
def menu_api(client, token):
    """菜单模块接口封装（会话级）。"""
    return MenuApi(client, token)


@pytest.fixture(scope="session")
def dept_api(client, token):
    """部门模块接口封装（会话级）。"""
    return DeptApi(client, token)
