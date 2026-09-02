"""用户模块-查询 测试用例。

覆盖接口：
    GET /system/user/list    获取用户分页列表接口：分页条件查询用户，返回 rows 与 total
    GET /system/user/{id}    获取用户详情接口：返回指定用户完整信息，或岗位+角色下拉列表

测试策略：
    数据驱动：data/user/user_query_lis_.data.json 提供 success_cases / fail_cases /
    defect_cases 三类场景数据。
    正向 / 反向 / 边界 / 已知缺陷(xfail) 场景全覆盖：
    - 成功筛选：userName/status/deptId/分页等条件组合，按数据文件的期望字段选择性断言
      （rows 数 / 总数 / 首行用户名 / 状态）；
    - HTTP 失败：分页参数非法（pageNum=0/负数 → 500）、路径参数非数字 → HTTP 422；
    - 已知缺陷(xfail)：时间筛选非标准格式 → 500 泄漏；
    - 详情接口：不传 id 返回岗位+角色下拉列表（编辑页数据来源）；
      查询不存在用户 → 500（user_detail_services 无空值保护，与角色/岗位/菜单详情的
      200 全空行为不同）。
    代表覆盖：PageUtil 分页与时间解析被角色/岗位/菜单/部门查询共用，仅在本模块验证。
"""

import pytest
import allure
import json
import requests

# 模块导入时一次性加载查询场景数据（成功/HTTP 失败/缺陷三类），避免每个用例重复读文件
with open('data/user/user_query_lis_.data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)


@allure.feature("用户模块")
@allure.story("获取用户分页列表接口")
@pytest.mark.user
class TestUserQueryList():
    """用户分页列表查询用例：成功场景按数据文件期望字段选择性断言，失败与缺陷场景分别校验 HTTP 状态码与业务返回码。"""

    # ===== 成功筛选场景（数据驱动：userName/status/deptId/分页等条件组合）=====
    @pytest.mark.parametrize(
        "case",
        data["success_cases"]
    )
    @allure.title("{case[name]}")
    def test_list_success(self, user_api, case):
        """正向筛选场景：按数据文件声明的期望字段选择性断言（rows 数 / 总数 / 首行用户名 / 状态），未声明字段不强校验。"""
        resp = user_api.list(**case["params"])
        assert resp.json()["code"] == case["expected_code"]
        # 选择性断言：仅校验数据文件中声明的期望字段，用例与数据解耦，字段缺失时跳过对应校验
        if "expected_rows" in case:
            assert len(resp.json()["rows"]) == case["expected_rows"]
        if "expected_total" in case:
            assert resp.json()["total"] == case["expected_total"]
        if "expected_user_name" in case:
            assert resp.json()["rows"][0]["userName"] == case["expected_user_name"]
        if "expected_all_status" in case:
            assert resp.json()["rows"][0]["status"] == case["expected_all_status"]

    # ===== HTTP 失败场景（分页参数非法 → 422/500 抛 HTTPError）=====
    @pytest.mark.parametrize(
        "case",
        data["fail_cases"]
    )
    @allure.title("{case[name]}")
    def test_list_fail(self, user_api, case):
        """反向场景：非法查询参数触发 4xx/5xx，requests 抛出 HTTPError，断言响应 HTTP 状态码。"""
        # 非法参数（如 pageNum=0/负数）触发 500 等状态码，由 requests 包装为 HTTPError 后捕获断言
        with pytest.raises(requests.exceptions.HTTPError) as e:
            user_api.list(**case["params"])
        assert e.value.response.status_code == case["expected_status"]

    # ===== 缺陷场景（xfail：时间筛选非标准格式 → 500 泄漏等）=====
    defect_params = [
        pytest.param(
            case,
            marks=pytest.mark.xfail(
                reason=f"已知缺陷 {case['defect_desc']}，"
                       f"前端已经做出约束,一般情况下客户端OK"
            )
        )
        for case in data["defect_cases"]
    ]

    @pytest.mark.parametrize("case", defect_params)
    @allure.title("{case[name]}")
    def test_list_defect(self, user_api, case):
        """已知缺陷用例（xfail）：时间筛选非标准格式期望业务拦截，实际 500 泄漏，断言记录缺陷现状。"""
        resp = user_api.list(**case["params"])
        assert resp.json()["code"] == case["expected_code"]
        if "expected_rows" in case:
            assert len(resp.json()["rows"]) == case["expected_rows"]


@pytest.mark.user
@allure.feature("用户模块")
@allure.story("获取用户详情接口")
class TestUserQueryDetail:
    """用户详情查询用例：覆盖正常详情、查询不存在用户（500 泄漏）、非法路径参数（422）与不传 id 返回岗位+角色下拉列表四种行为。"""

    @allure.title("获取指定用户详情成功")
    def test_get_user_detail_success(self, user_api):
        """正向场景：查询种子账号 admin（userId=1）详情，断言返回完整用户信息且 userId 正确。"""
        # 以种子账号 admin（userId=1）为查询目标，断言详情返回完整用户信息
        resp = user_api.detail(1)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["data"]["userId"] == 1

    @pytest.mark.xfail(
        reason="已知缺陷：查询不存在用户时后端未判空，UserInfoModel(**None) 崩溃返回 500 并泄漏 Python 内部错误，"
               "正确应返回友好业务提示且不泄漏内部细节；前端已约束，客户端无法触发"
    )
    @allure.title("获取用户详情时，输入不存在的用户")
    def test_get_none_user(self, user_api):
        """已知缺陷用例（xfail）：查询不存在用户（9999）→ 500 泄漏：user_detail_services 无空值保护，None 结果构造模型触发 TypeError。"""

        # 该行为与角色/岗位/菜单详情的 200 全空行为不同，属于用户模块特有行为，作为反向场景固化
        resp = user_api.detail(9999)
        data = resp.json()
        # 核心断言：不得泄漏内部实现细节（当前实际泄漏 NoneType/类名 → 断言失败 → xfail）
        assert "NoneType" not in data["msg"]
        assert "must be a mapping" not in data["msg"]
        assert "UserInfoModel" not in data["msg"]
        # 用户详情链路无空值保护：user_detail_services 对 None 查询结果直接构造模型，触发 TypeError 返回 500
        # 业务层面：查询不存在用户应返回失败标识（可修复为 500/601 + 友好 msg）
        assert data["code"] == 500
        assert data["success"] is False

    @allure.title("获取用户详情的参数为非法值")
    def test_detail_non_numeric(self, user_api):
        """边界场景：路径参数为非数字，FastAPI int 类型解析失败，请求被参数层拦截返回干净的 HTTP 422。"""
        # 路径参数类型校验：detail("abc") 在 FastAPI 参数解析层拦截，返回干净的 HTTP 422
        with pytest.raises(requests.exceptions.HTTPError) as e:
            user_api.detail("abc")
        assert e.value.response.status_code == 422

    @allure.title("获取用户详情时不输入用户id会返回岗位+角色下拉列表")
    def test_get_user_detail_none(self, user_api):
        """边界场景：不传 user_id 时接口返回岗位+角色下拉列表（编辑页数据来源），data 字段为 None。"""
        # 不传 user_id 触发特殊分支：返回岗位+角色下拉列表（编辑页面的数据来源），data 为 None
        resp = user_api.detail(None)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["data"] is None
