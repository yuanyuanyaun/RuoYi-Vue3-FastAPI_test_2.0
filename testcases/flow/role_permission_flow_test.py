"""流程测试（受限角色权限拦截链路）测试用例。

覆盖接口：
    POST   /system/user              新增受限用户：仅建人，不授予任何角色
    POST   /system/role              新增受限角色：只挂载菜单100（用户管理，system:user:list）
    PUT    /system/user/authRole     给用户分配受限角色（替换语义）
    POST   /login                    受限用户登录（携带有效 token 是后续权限校验的前提）
    GET    /getInfo                  验证受限用户的 roles/permissions 只含被授予的最小权限
    GET    /system/user/list         有权限接口对照：持有 system:user:list → 放行
    GET    /system/role/list         无权限接口对照：缺 system:role:list → 业务码 403 拦截
    POST   /logout                   退出登录（token 生命周期闭环）
    DELETE /system/user/{id}         删除受限用户（清理）
    DELETE /system/role/{id}         删除受限角色（清理）

测试策略：
    - 验证"权限配置真实生效于接口层"，而非仅停留在 getInfo 的返回体。
      单模块用例全部以 admin（permissions=['*:*:*']）身份调用，权限注解恒放行，
      故设计此流程填补"无权限被拦"的集成测试盲区。
    - 最小权限角色设计：新角色只挂载 1 个菜单（menu100，perms=system:user:list），
      权限面最小、允许/拒绝边界清晰。
    - 对照组设计：
        同一接口 /system/role/list——受限用户被 403 拦截、admin 正常 200，
        用"同接口双身份对比"证明拦截源于权限而非接口故障或环境问题。
    - 跨用例数据依赖：受限用户/角色 ID 登记到模块级全局变量供后续用例接力，
      故此用例必须按定义顺序整类执行，不可单独或乱序运行。
"""

import pytest
import allure
import time
from utils.function import auth

# 模块级毫秒时间戳：自建数据名以同一时间戳命名，保证整类用例名称唯一、互不重名
ts = int(time.time()) * 1000
# ===== 模块级唯一名称与 ID 登记位（ID 由对应创建用例经列表反查后登记，供后续用例接力使用）=====
user_name = f"perm_user_{ts}"
user_nick = f"受限用户昵称{ts}"
user_id = None
role_name = f"受限角色{ts}"
role_key = f"perm_key_{ts}"
role_id = None
login_token = None
# 受限角色只挂载该菜单，使权限面最小——仅有列表查询用户接口的权限
menu_id = 100
# 有权限接口需持有的权限串（菜单100 的 perms）与无权限接口需持有的权限串（菜单101，未授予）
user_perm = "system:user:list"
role_perm = "system:role:list"


@pytest.mark.flow
@allure.feature("流程测试")
class TestRolePermissionFlow:
    """受限角色权限拦截链路用例：最小权限角色 → 登录 → 有权限放行/无权限 403 业务码拦截 → admin 同接口对照 → 倒序清理。"""

    @allure.title("创建受限用户")
    def test_creat_user(self, user_api):
        """正向场景：创建流程首位的受限用户（不授予任何角色），登记 userId 供后续用例复用。"""
        global user_id, user_name
        resp = user_api.creat(
            userName=user_name,
            nickName=user_nick,
            password="Perm@123456",
            email=f"perm@qq.com",
            phonenumber=f"18960958103",
        )
        # 断言新增用户成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # 创建响应体不含 ID，按唯一业务名反查列表登记 userId
        user_id = user_api.list(userName=user_name).json()["rows"][0]["userId"]

    @allure.title("创建受限角色（仅挂载用户管理菜单）")
    def test_creat_role_min_perms(self, role_api):
        """正向场景：创建最小权限角色——只挂载菜单100（perms=system:user:list）"""
        global role_id, role_name, role_key
        resp = role_api.creat(
            **{
                "roleName": role_name,
                "roleKey": role_key,
                "roleSort": 9,
                "status": "0",
                "menuIds": [menu_id],
                "remark": "流程测试最小权限角色"
            }
        )
        # 断言新增角色成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        role_id = role_api.list(roleName=role_name).json()["rows"][0]["roleId"]

    @allure.title("给受限用户分配受限角色")
    def test_assign_role_to_user(self, user_api):
        """正向场景：通过 authRole（替换语义）把受限角色授予受限用户。"""
        global role_id, user_id
        resp = user_api.assign_roles(user_id, str(role_id))
        # 断言分配成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

    @allure.title("受限用户登录")
    def test_login_limited_user(self, login_api):
        """正向场景：受限用户可正常登录（权限不足只拦接口，不拦登录），token 供后续用例复用。"""
        global login_token, user_name
        resp = login_api.login(
            username=user_name,
            password="Perm@123456"
        )
        # 断言登录成功契约：业务 code 200 + 成功标识为 True + 提示「登录成功」
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()['msg'] == "登录成功"
        login_token = resp.json()['token']

    @allure.title("验证受限用户 getInfo：权限面只有被授予的最小权限")
    def test_get_info_min_perms(self, login_api):
        """正向场景：getInfo 返回受限用户的角色与权限，证明权限面确实最小"""
        global role_key, role_id, login_token, user_id, user_name
        resp = login_api.get_info(login_token)
        data = resp.json()
        # 断言接口成功契约：业务 code 200 + 成功标识为 True
        assert data["code"] == 200
        assert data["success"] == True
        # 角色生效：roles（role_key 列表）应含本流程受限角色的 role_key
        assert role_key in data["roles"]
        # 权限最小化：只有被授予的 system:user:list，绝无 admin 专属的 *:*:*
        assert user_perm in data["permissions"]
        assert role_perm not in data["permissions"]
        assert "*:*:*" not in data["permissions"]
        # 用户身份一致：user.roleIds 为受限角色 id 字符串
        assert data["user"]["roleIds"] == str(role_id)
        assert data["user"]["userId"] == user_id
        assert data["user"]["userName"] == user_name

    @allure.title("有权限接口：调用用户列表成功")
    def test_call_allowed_api(self, client):
        """正向场景：受限用户持有 system:user:list → GET /system/user/list 放行（业务 code 200）"""
        global login_token
        # 受限用户自己的 token 直接调接口（api 封装夹具绑定的是 admin token，故此处用 client+auth）
        resp = client.get("system/user/list", headers=auth(login_token))
        # 断言放行契约：业务 code 200 + 成功标识为 True + 能查到种子用户（数据权限为全部）
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        names = [row["userName"] for row in resp.json()["rows"]]
        assert "admin" in names

    @allure.title("无权限接口：调用角色列表被业务码403拦截")
    def test_call_forbidden_api(self, client):
        """权限拦截核心用例：受限用户缺 system:role:list → GET /system/role/list 被拦。 """
        global login_token
        resp = client.get("system/role/list", headers=auth(login_token))
        # 断言拦截契约：业务 code 403 + 成功标识为 False + 提示「该用户无此接口权限」
        assert resp.json()["code"] == 403
        assert resp.json()["success"] is False
        assert resp.json()["msg"] == "该用户无此接口权限"

    @allure.title("对照组：admin 调用同一接口成功")
    def test_admin_can_call_same_api(self, client, token):
        """对照用例：同一接口 /system/role/list，admin（*:*:*）调用返回 200。"""
        resp = client.get("system/role/list", headers=auth(token))
        # 断言放行契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

    @allure.title("受限用户退出登录")
    def test_logout(self, login_api):
        """正向场景：受限用户退出登录成功，token 生命周期闭环（登录→调用→退出）。"""
        global login_token
        resp = login_api.logout(login_token)
        # 断言退出成功契约：业务 code 200 + 成功标识为 True + 提示「退出成功」
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "退出成功"

    @allure.title("清理受限用户与角色")
    def test_cleanup_user_role(self, user_api, role_api):
        """清理：先删用户（释放 sys_user_role 关联）再删角色。
        后端校验约束（顺序颠倒会删除失败）：
            删角色前若仍有关联用户 → 「角色已分配,不能删除」（count_user_role > 0）。
        """
        global user_id, role_id
        user_resp = user_api.delete(user_id)
        # 断言删除用户成功契约：业务 code 200 + 提示「删除成功」
        assert user_resp.json()["code"] == 200
        assert user_resp.json()["msg"] == "删除成功"
        role_resp = role_api.delete(role_id)
        # 断言删除角色成功契约：业务 code 200 + 提示「删除成功」
        assert role_resp.json()["code"] == 200
        assert role_resp.json()["msg"] == "删除成功"
