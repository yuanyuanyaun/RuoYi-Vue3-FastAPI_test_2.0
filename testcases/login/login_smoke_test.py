"""登录模块冒烟测试用例。

覆盖接口：
    POST /login         登录接口：账号密码登录，返回 JWT token
    GET  /getInfo       获取用户信息接口：返回当前用户的角色、权限与基本信息
    GET  /getRouters    获取用户路由接口：返回当前用户可见的动态菜单路由
    POST /logout        退出登录接口：注销 token 使其立即失效

测试策略：
    正向主链路闭环：登录成功 → 携带 token 获取用户信息与动态路由 → 退出后原 token 失效（401）。
    用例之间存在数据依赖：test_login 负责登录并缓存 token，后续用例复用该 token，
    因此本类用例必须按定义顺序执行，不可单独或乱序运行。
"""

import pytest
import allure

# 种子账号（预置数据）：admin / admin123，冒烟测试统一使用超级管理员身份
admin = {"username": "admin", "password": "admin123"}


@pytest.mark.login
@pytest.mark.smoke
@allure.feature("登录模块")
class TestLoginSmoke:
    """登录模块冒烟用例：验证登录 → 获取信息/路由 → 退出的完整正向主链路。"""

    login_token = None  # 类变量：缓存登录成功返回的 token，供后续用例共享认证凭证

    @allure.story("登录接口")
    @allure.title("admin 登录成功")
    def test_login(self, login_api):
        """验证种子账号 admin 使用正确密码登录成功，并返回合法、非空的 JWT token。"""
        resp = login_api.login(**admin)
        # 断言登录成功契约：HTTP 状态码 200 + 业务 code 200 + 成功标识为 True + token 非空
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert data['code'] == 200
        assert data['msg'] == "登录成功"
        assert data["success"] == True
        assert data["token"]
        # 从响应体取出 JWT token，登记到类变量 login_token，
        # 作为后续 getInfo / getRouters / logout 用例的认证凭证复用，避免每个用例重复登录
        TestLoginSmoke.login_token = data["token"]

    @allure.story("获取用户信息接口")
    @allure.title("带token获取用户信息成功")
    def test_get_info(self, login_api):
        """验证携带有效 token 请求时，接口返回当前登录用户的角色、权限与基本信息。"""
        resp = login_api.get_info(TestLoginSmoke.login_token)
        # 断言接口调用成功：HTTP 200 + 业务 code 200
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    @allure.story("获取用户路由接口")
    @allure.title("带token获取用户路由成功")
    def test_get_routers(self, login_api):
        """验证携带有效 token 请求时，接口返回当前用户可见的动态路由（前端侧边栏菜单数据来源）。"""
        resp = login_api.get_routers(TestLoginSmoke.login_token)
        # 断言接口调用成功：HTTP 200 + 业务 code 200
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    @allure.story("退出登录接口")
    @allure.title("带token退出登录成功")
    def test_logout(self, login_api):
        """验证退出登录成功，且退出后同一 token 立即失效（再次请求被认证拦截返回 401）。"""
        resp = login_api.logout(TestLoginSmoke.login_token)
        # 断言退出接口本身调用成功：HTTP 200 + 业务 code 200
        assert resp.status_code == 200
        assert resp.json()["code"] == 200
        # 验证 token 已失效：用已退出的 token 再次请求 getRouters / getInfo，均被认证拦截返回 401
        getRouters_resp = login_api.get_routers(TestLoginSmoke.login_token)
        assert getRouters_resp.json()["code"] == 401
        getInfo_resp = login_api.get_info(TestLoginSmoke.login_token)
        assert getInfo_resp.json()["code"] == 401
