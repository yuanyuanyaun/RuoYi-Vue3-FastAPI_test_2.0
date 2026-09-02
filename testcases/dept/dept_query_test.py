"""部门模块-查询 测试用例。

覆盖接口：
    GET /system/dept/list                    部门列表接口：返回部门树数据（不分页）
    GET /system/dept/list/exclude/{dept_id}  编辑部门下拉树接口：排除指定部门及其子孙部门
    GET /system/dept/{dept_id}               部门详情接口：按主键返回单个部门信息

测试策略：
    列表筛选：部门 list 为不分页接口（返回 data 数组），仅测部门特有筛选字段
    （deptName 模糊匹配 / status 精确匹配）；分页与时间筛选边界已在用户/角色模块覆盖，此处不重复。
    下拉树排除：exclude 树按 ancestors 祖先链排除指定部门及其子孙部门，
    验证返回树中不出现被排除节点。
    路径参数：详情接口覆盖路径参数为空（404）与非数字（422）两类参数层校验场景。
    已知缺陷(xfail)：exclude 999 查询不存在部门的编辑树本应报错却返回全量部门；
    详情 999 本应报错却返回成功（空数据），两处前端均已做出约束。
"""

import pytest
import allure
import requests


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("获取部门列表接口")
@allure.description(
    "部门列表为不分页接口（返回 data 数组），分页相关边界场景在用户/角色模块已覆盖，此处不重复。"
    "仅测部门特有筛选字段（deptName/status）。"
)
class TestDeptList:
    """不分页部门列表查询用例：仅覆盖部门特有筛选字段（deptName/status）。"""

    @allure.title("按部门名称筛选")
    def test_list_filter_by_name(self, dept_api):
        """验证按部门名称筛选时返回数据包含目标部门（deptName 为模糊匹配）。"""
        # 种子部门「研发部门」为预置数据，按名称筛选后断言返回树中存在该部门
        resp = dept_api.list(deptName="研发部门")
        # 断言接口调用成功契约：HTTP 200 + 业务 code 200 + 成功标识为 True
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert any(row["deptName"] == "研发部门" for row in data["data"])

    @allure.title("按状态筛选")
    def test_list_filter_by_status(self, dept_api):
        """验证按状态筛选时返回的全部部门状态均为指定值（status 为精确匹配）。"""
        # 种子数据中正常状态（"0"）部门非空；用 all 断言保证返回树每一行状态一致，
        # 排除混入停用部门的可能
        resp = dept_api.list(status="0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        assert data["data"]
        assert all(row["status"] == "0" for row in data["data"])


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("获取编辑部门下拉树接口")
class TestDeptExcludeList:
    """编辑部门下拉树用例：验证树数据正确排除指定部门及其子孙部门。"""

    @allure.title("获取排除指定部门及其子部门的树")
    def test_exclude_list_success(self, dept_api):
        """验证排除指定部门（102 长沙分公司）后，其自身及子孙部门（108/109）均不出现在下拉树中。"""
        # 部门 102（长沙分公司）下挂子部门 108（市场）/109（财务），
        # 排除后三者都应从返回树中消失，验证 exclude 按 ancestors 祖先链递归排除
        resp = dept_api.exclude_list(102)
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] is True
        # 先收集返回树全部 deptId 再逐个断言，避免嵌套遍历
        ids = [row["deptId"] for row in data["data"]]
        assert 102 not in ids
        assert 108 not in ids
        assert 109 not in ids

    @pytest.mark.xfail(reason="查询不存在部门的编辑树本应报错却返回全量部门，前端已经做出约束,一般情况下客户端OK")
    @allure.title("获取不存在部门的编辑树")
    def test_exclude_list_nonexist(self, dept_api):
        """已知缺陷验证：exclude 999 查询不存在部门的编辑树，期望报错，实际返回全量部门，标记 xfail。"""
        # 缺陷表现：后端未校验部门存在性，直接返回全量部门树；
        # 用例断言正常行为契约（code 500），当前实际失败故标记 xfail
        resp = dept_api.exclude_list(999)
        assert resp.json()["code"] == 500


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("获取部门详情接口")
class TestDeptDetail:
    """部门详情接口用例：覆盖存在性缺陷与路径参数两类场景。"""

    @pytest.mark.xfail(reason="获取不存在部门的详情本应报错却返回成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("获取不存在部门的详情")
    def test_detail_nonexist(self, dept_api):
        """已知缺陷验证：查询不存在部门的详情，期望报错，实际返回成功（空数据），标记 xfail。"""
        # 缺陷表现：详情 999 返回 200 而非错误提示；
        # 用例断言正常行为契约（code 500），当前实际失败故标记 xfail
        resp = dept_api.detail(999)
        assert resp.json()["code"] == 500

    @allure.title("详情路径参数为空")
    def test_detail_empty_path(self, dept_api):
        """路径参数校验：详情路径参数为空字符串时不匹配 /{dept_id} 路由，返回 HTTP 404。"""
        # 空路径无法路由到详情端点，由框架层返回 404，
        # requests 抛出 HTTPError，捕获后断言响应状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            dept_api.detail("")
        assert e.value.response.status_code == 404

    @allure.title("详情路径参数非数字")
    def test_detail_non_numeric(self, dept_api):
        """路径参数校验：详情路径参数为非数字时，FastAPI 参数层 int 解析失败，返回 HTTP 422。"""
        # "abc" 无法解析为 int，由参数层（FastAPI 类型转换）返回 422，无内部错误泄漏
        with pytest.raises(requests.exceptions.HTTPError) as e:
            dept_api.detail("abc")
        assert e.value.response.status_code == 422
