"""部门模块-新增 测试用例。

覆盖接口：
    POST /system/dept    新增部门接口：新增部门，返回业务 code 与新增成功提示

测试策略：
    数据驱动：加载 data/dept/dept_creat_data.json，按 fail_code_cases（业务失败：
    HTTP 200 + 业务 code 601/500）与 fail_status_cases（HTTP 状态失败：4xx/5xx）两组参数化执行。
    边界值：部门名称长度上限 30 字符，覆盖恰好 30（成功）与 31（校验拦截）两个边界。
    业务规则：部门名称唯一性为同级唯一（parentId + deptName 组合判定），
    除名称外其他字段相同可重复新增；父部门停用时不允许新增。
    已知缺陷(xfail)：parentId 指向不存在的部门时，后端未校验上级部门存在性，
    直接读取其属性崩溃，返回 500 并泄漏 Python 内部错误。
    数据依赖：用例通过工厂夹具 creat_dept 创建临时部门，用例结束后自动级联清理。
"""

import json
import allure
import pytest
import requests
from utils.function import make_dept

# 加载数据驱动用例数据：模块导入时执行一次，读取部门新增场景的失败用例集
#（缺字段/重复/非法值等），供参数化用例复用
with open("data/dept/dept_creat_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("添加部门接口")
class TestDeptCreat:
    """添加部门用例：覆盖数据驱动失败场景、同级唯一性、名称长度边界值与已知缺陷(xfail)。"""

    @pytest.mark.parametrize("case", data["fail_code_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_code(self, case, dept_api):
        """验证数据驱动定义的业务失败场景：接口返回 HTTP 200 但业务 code 为预期拦截值，成功标识为 False。"""
        # 工厂函数 make_dept 生成默认合法的部门请求体，overrides 叠加场景定制
        #（如缺字段、非法值、重复名称），保证失败场景只修改单一变量
        resp = dept_api.creat(**make_dept(**case["overrides"]))
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] is False

    @pytest.mark.parametrize("case", data["fail_status_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_status(self, case, dept_api):
        """验证数据驱动定义的 HTTP 状态失败场景：请求直接抛出 HTTPError，且状态码与用例预期一致。"""
        # 此类场景由框架层直接返回非 2xx，requests 抛出 HTTPError，
        # 故用 pytest.raises 捕获异常后断言响应状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            dept_api.creat(**make_dept(**case["overrides"]))
        assert e.value.response.status_code == case["expected_status"]

    @pytest.mark.xfail(reason=f"新增时未校验上级部门是否存在，parentId传不存在的值直接读取其属性崩溃，"
                              f"返回500并泄漏Python内部错误前端已经做出约束,一般情况下客户端OK")
    @allure.title("添加上级部门不存在的部门")
    def test_creat_defect(self, creat_dept):
        """已知缺陷验证：parentId 指向不存在的部门时，期望正常拦截返回 601，实际后端崩溃返回 500 并泄漏内部错误，标记 xfail。"""
        # 缺陷触发点：新增时未校验上级部门是否存在，parentId 传不存在的值时直接读取其属性崩溃；
        # 用例断言「正常行为」的期望契约（601 + 失败标识），当前实际失败故标记 xfail
        resp, _, _ = creat_dept(parentId= 999)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    @allure.title("除部门名称外其他字段相同可重复添加")
    def test_creat_repeat_other_fields(self, creat_dept):
        """验证部门名称唯一性为同级唯一：除名称外其他字段完全相同的两个部门均可新增成功。"""
        # 构造公共请求体：除 deptName 由工厂夹具自动生成外，父级/排序/负责人/电话/邮箱/状态完全一致，
        # 两次新增均应成功，证明唯一性约束仅作用于 deptName（同级维度）
        common = {
            "parentId": 100,
            "orderNum": 1,
            "leader": "同一负责人",
            "phone": "13800138000",
            "email": "same@qq.com",
            "status": "0"
        }
        resp_a, _, _ = creat_dept(**common)
        resp_b, _, _ = creat_dept(**common)
        assert resp_a.json()["code"] == 200
        assert resp_b.json()["code"] == 200

    @allure.title("部门名称恰好 30 字符成功")
    def test_creat_name_30(self, creat_dept):
        """边界值验证：部门名称恰好 30 字符时新增成功，且返回有效的 dept_id。"""
        # 构造恰好 30 字符的名称（28 个 'a' + 占位符 "1@"），命中名称长度上限的正常边界
        resp, dept_id, _ = creat_dept(deptName="a" * 28 + "1@")
        assert resp.json()["code"] == 200
        assert dept_id is not None

    @allure.title("部门名称恰好超过 30 字符")
    def test_creat_name_31(self, creat_dept):
        """边界值验证：部门名称超过 30 字符时被长度校验拦截，返回业务 code 601。"""
        # 构造 31 字符名称（29 个 'a' + "1@"），超过长度上限 1 字符，期望命中长度校验返回 601
        resp, _, _ = creat_dept(deptName="a" * 29 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False


    @allure.title("父部门停用时不允许新增")
    def test_creat_parent_disabled(self, creat_dept):
        """业务规则验证：父部门停用（status=1）时，不允许在其下新增子部门。"""
        # 第一步先创建停用状态的父部门（status="1"），拿到其 dept_id 作为数据依赖
        _, parent_id, _ = creat_dept(status="1")
        # 第二步以停用父部门为 parentId 新增子部门，期望被业务规则拦截：
        # code 500 + 提示语「停用，不允许新增」
        resp, _, _ = creat_dept(parentId=parent_id)
        assert resp.json()["code"] == 500
        assert "停用，不允许新增" in resp.json()["msg"]
