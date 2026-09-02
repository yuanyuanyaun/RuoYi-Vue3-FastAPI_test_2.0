"""登录模块-其他场景 测试用例：覆盖登录正向多场景、登录失败反向场景与 getInfo 认证/权限差异。

覆盖接口：
    POST /login   登录接口：账号密码登录，返回 JWT token；退出登录后原 token 立即失效
    GET  /getInfo 获取用户信息接口：返回当前用户的角色、权限与基本信息

测试策略：
    - 正向：第二种子账号 niangao 登录、登录后退出再登录、同一账号连续登录的多会话共存
      （后端按 session_id 维度存储 token，多会话 token 互不影响）
    - 反向（认证链差异，经源码验证）：
        无 token 调 getInfo → OAuth2 依赖层拦截，抛出 HTTP 401
        无效 token 调 getInfo → JWT 解析失败抛 AuthException → HTTP 200 + 业务 code 401
    - 权限差异：普通角色 niangao（无 *:*:* 全量权限）与 admin 超级管理员的 getInfo 角色/权限对比
    - 数据驱动：data/login/login_fail_data.json 提供登录失败场景数据，
      按业务失败（login_fail_cases_code）与 HTTP 状态失败（login_fail_cases_status）两类参数化驱动
"""

import pytest
import allure
import json
import requests


@pytest.mark.login
@allure.feature("登录模块")
class TestLoginPositive:
    """登录模块正向多场景用例：验证第二账号登录、退出后重登、多会话共存等登录主链路变体。"""

    @allure.story("登录接口")
    @allure.title("niangao 登录成功（第二账号）")
    def test_login_second_account(self, login_api):
        """验证第二种子账号 niangao 使用正确密码登录成功：非 admin 账号同样可正常获取 JWT token。"""
        resp = login_api.login(
            username="niangao",
            password="admin123"

        )
        # 断言登录成功契约：HTTP 状态码 200 + 业务 code 200 + 成功标识为 True + token 非空
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert data['code'] == 200
        assert data['msg'] == "登录成功"
        assert data["success"] == True
        assert data["token"]

    @allure.story("登录接口")
    @allure.title("登录再退出再登录成功")
    def test_login_relogin(self, login_api):
        """验证退出登录仅使已注销的 token 失效，不影响账号本身：退出后同一账号可再次登录成功。"""
        first_resp = login_api.login(
            username="admin",
            password="admin123"
        )
        # 断言首次登录成功：HTTP 200 + 业务 code 200，并取出 token 作为退出接口的认证凭证
        assert first_resp.status_code == 200
        assert first_resp.json()["code"] == 200
        login_token = first_resp.json()["token"]
        logout_resp = login_api.logout(login_token)
        # 断言退出接口成功：业务 code 200 + 成功标识为 True，注销当前 token 使其失效
        assert logout_resp.json()["code"] == 200
        assert logout_resp.json()["success"] == True
        second_resp = login_api.login(
            username="admin",
            password="admin123"
        )
        # 断言再次登录成功：token 注销不影响账号认证能力，重新登录即签发新 token
        assert second_resp.status_code == 200
        assert second_resp.json()["code"] == 200

    @allure.story("登录接口")
    @allure.title("同一账号重复登录多会话共存")
    def test_login_multi_session(self, login_api):
        """验证同一账号连续登录两次产生两个互不影响的 token：后端按 session_id 维度存储登录状态。"""
        a_resp = login_api.login(
            username="admin",
            password="admin123"
        )
        # 断言第一次登录成功：HTTP 200 + 业务 code 200
        assert a_resp.status_code == 200
        assert a_resp.json()["code"] == 200
        b_resp = login_api.login(
            username="admin",
            password="admin123"
        )
        # 断言第二次登录成功：HTTP 200 + 业务 code 200（与第一次登录互不挤占）
        assert b_resp.status_code == 200
        assert b_resp.json()["code"] == 200
        a_token = a_resp.json()["token"]
        b_token = b_resp.json()["token"]
        # 用两个 token 分别请求 getInfo：均返回用户信息，验证多会话 token 并存且互不影响
        resp_a = login_api.get_info(a_token)
        assert resp_a.status_code == 200
        assert resp_a.json()["code"] == 200
        resp_b = login_api.get_info(b_token)
        assert resp_b.status_code == 200
        assert resp_b.json()["code"] == 200


# 登录失败场景数据加载：模块导入时执行一次，读取 data/login/login_fail_data.json，
# 按业务失败（login_fail_cases_code）与 HTTP 状态失败（login_fail_cases_status）两类数据驱动下方参数化用例
with open('data/login/login_fail_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)


@pytest.mark.login
@allure.feature("登录模块")
@allure.story("登录接口")
class TestLoginNegative:
    """登录模块反向用例：通过数据驱动覆盖业务层失败与 HTTP 层失败两类登录失败场景。"""

    # 业务失败类：HTTP 200 + 业务 code（如 601：用户不存在/密码错误/账号锁定），
    # 由 login_fail_cases_code 数据逐条参数化驱动
    @pytest.mark.parametrize(
        "case",
        data["login_fail_cases_code"]
    )
    @allure.title("{case[name]}")
    def test_login_fail_code(self, login_api, case):
        """验证业务层登录失败契约：请求本身成功（HTTP 200），响应业务 code 与数据驱动中的预期值一致。"""
        resp = login_api.login(**case["payload"])
        assert resp.status_code == 200
        assert resp.json()["code"] == case["expected_code"]

    # HTTP 状态类：4xx/5xx 会抛出 HTTPError（如验证码相关 422），
    # 由 login_fail_cases_status 数据逐条参数化驱动
    @pytest.mark.parametrize(
        "case",
        data["login_fail_cases_status"],
    )
    @allure.title("{case[name]}")
    def test_login_fail_status(self, login_api, case):
        """验证 HTTP 层登录失败契约：请求抛出 HTTPError 异常，其响应状态码与数据驱动中的预期值一致。"""
        with pytest.raises(requests.exceptions.HTTPError) as e:
            login_api.login(**case["payload"])
        assert e.value.response.status_code == case["expected_status"]


@pytest.mark.login
@allure.feature("登录模块")
@allure.story("获取用户信息接口")
class TestLoginOthers:
    """getInfo 差异场景用例：验证不同角色的权限差异与缺失/无效认证凭证的拦截行为。"""

    @allure.title("niangao与admin的getInfo角色权限差异")
    def test_get_info_role_diff(self, login_api):
        """验证普通角色 niangao 的 getInfo 返回：角色列表不含 admin、权限非全量 *:*:*（与超级管理员存在差异）。"""
        token = login_api.login(
            username="niangao",
            password="admin123"
        ).json()["token"]
        resp = login_api.get_info(token)
        assert resp.status_code == 200
        data = resp.json()
        # 断言角色差异契约：niangao 角色列表包含 common 且不含 admin
        assert "common" in data["roles"]
        assert "admin" not in data["roles"]
        # 断言权限差异契约：普通角色权限不是全量 *:*:*（全量权限为超级管理员专属）
        assert data["permissions"] != ["*:*:*"]

    @allure.story("获取用户信息接口")
    @allure.title("无token，获取用户信息失败")
    def test_get_info_without_token(self, login_api):
        """验证缺失 Authorization 头时被 OAuth2 依赖层拦截：抛出 HTTPError，响应 code 与状态码均为 401。"""
        with pytest.raises(requests.exceptions.HTTPError) as e:
            login_api.get_info()
        assert e.value.response.json()["code"] == 401
        assert e.value.response.status_code == 401

    @allure.story("获取用户信息接口")
    @allure.title("无效token，获取用户信息失败")
    def test_get_info_invalid_token(self, login_api):
        """验证无效 token 的认证拦截位置：可通过 OAuth2 头提取，但 JWT 解析失败抛 AuthException → HTTP 200 + 业务 code 401。"""
        resp = login_api.get_info("invalid_token_123")
        assert resp.status_code == 200
        assert resp.json()["code"] == 401
