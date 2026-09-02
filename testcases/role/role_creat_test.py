"""角色模块-添加角色 测试用例。

覆盖接口：
    POST /system/role 添加角色接口：新增角色并写入菜单关联，返回 role_id

测试策略：
    正向：数据驱动成功用例（success_cases），断言业务 code 200 且返回非空 role_id。
    反向：业务失败（601 参数校验拦截 / 500 唯一性冲突）与 HTTP 状态失败（4xx/5xx 抛 HTTPError）。
    边界：roleName 30/31、roleKey 100/101、备注 500/501 字符长度的上下限。
    已知缺陷(xfail)：备注 501 字符返回 500 并泄漏 SQL/表结构（模型层缺长度校验，正常应 601 且不泄漏）。
    唯一性：仅 roleName/roleKey 参与唯一约束，其余字段相同可重复添加。
    数据驱动：用例数据来源 data/role/role_creat_data.json，模块导入时加载一次，
    按 success/fail_code/fail_status/defect 四类场景参数化驱动。
    数据准备：创建成功的角色由夹具 creat_role 登记，测试结束后自动级联清理。
"""

import pytest
import allure
import json
import requests
import time
from utils.function import make_role

# 模块导入时加载数据驱动用例文件，供 success/fail_code/fail_status/defect 四类参数化用例共享
with open("data/role/role_creat_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)
# 模块级时间戳：毫秒精度拼接唯一名称/权限字符，保证边界用例数据不与历史运行及种子数据冲突
ts = str(int(time.time() * 1000))


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("添加角色接口")
class TestCreatRole:
    """添加角色接口用例（POST /system/role），覆盖正向、反向、边界、已知缺陷与唯一性五类场景。"""

    # ===== 成功场景（数据驱动）：正向创建，断言成功契约与 role_id 非空 =====
    @pytest.mark.parametrize("case", data["success_cases"])
    @allure.title("{case[name]}")
    def test_creat_success(self, creat_role, case):
        """验证数据驱动成功用例：按 overrides 叠加工厂默认数据创建角色，接口成功且返回合法 role_id。"""
        # 夹具 creat_role：创建成功即登记 role_id，测试结束后自动级联清理，避免残留数据；
        # case["overrides"] 为对工厂默认数据的覆盖项，参数化驱动不同正向组合
        resp, role_id, _ = creat_role(**case["overrides"])
        # 断言成功契约：业务 code 200 且返回非空 role_id（供后续清理定位数据）
        assert resp.json()["code"] == 200
        assert role_id is not None

    # ===== 业务失败场景（HTTP 200 + 业务 code：601 校验拦截 / 500 唯一性冲突）=====
    @pytest.mark.parametrize("case", data["fail_code_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_code(self, creat_role, case):
        """验证业务失败场景：接口返回 HTTP 200 但业务 code 与成功标识符合预期拦截结果。"""
        # 在工厂默认数据上叠加 overrides（如 roleName=None 模拟缺字段、roleName="超级管理员" 模拟重复），
        # 经 make_role 工厂函数生成完整入参后调用创建接口
        resp, _, _ = creat_role(**make_role(**case["overrides"]))
        # 断言业务码与成功标识：expected_code 为 601（参数校验拦截）或 500（唯一性冲突）
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] == False

    # ===== HTTP 状态失败场景（4xx/5xx 抛 HTTPError）=====
    @pytest.mark.parametrize("case", data["fail_status_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_status(self, creat_role, case):
        """验证 HTTP 层失败场景：请求被框架层直接拦截并抛出 HTTPError，状态码与预期一致。"""
        # 此类失败由 HTTP 层拦截（响应体非业务 JSON），需捕获 requests 异常后核对状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            creat_role(**make_role(**case["overrides"]))
        assert e.value.response.status_code == case["expected_status"]

    # ===== 缺陷场景（xfail：期望正常拦截，实际 500 泄漏或假成功）=====
    # 将 defect_cases 逐条包装为 pytest.param 并统一打上 xfail 标记（已知缺陷），
    # reason 动态拼接缺陷描述，保证 Allure 报告可读
    defect_params = [
        pytest.param(
            use_data,
            marks=pytest.mark.xfail(
                reason=f"已知缺陷：{use_data['defect_desc']}，"
                       f"前端已经做出约束,一般情况下客户端OK"
            )
        )
        for use_data in data["defect_cases"]
    ]
    @pytest.mark.parametrize("case", defect_params)
    @allure.title("{case[name]}")
    def test_creat_defect(self, creat_role, case):
        """验证已知缺陷场景：期望后端正常拦截，实际表现为 500 泄漏或假成功，以 xfail 登记。"""
        # xfail 用例仍完整执行断言：若后端修复后返回 601 且 success=False，用例转为 XPASS，提示缺陷已修复
        resp, _, _ = creat_role(**case["overrides"])
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] == False

    # ===== 唯一性验证：除权限字符和名称外，其他字段相同可重复添加 =====
    @allure.title("除了权限和名称外重复添加角色无异常")
    def test_create_role_repeat_other_fields(self, creat_role):
        """验证唯一性约束范围：仅 roleName/roleKey 参与唯一约束，其余字段相同不阻塞重复添加。"""
        # 唯一性只卡 roleName/roleKey，其余字段（状态/数据权限/菜单/备注）相同不影响新增；
        # 构造两份仅名称与权限字符不同的角色数据，验证均能创建成功
        common = {
            "status": "0",
            "dataScope": "2",
            "menuIds": [1, 2, 100, 101],
            "deptIds": [100, 101],
            "menuCheckStrictly": True,
            "deptCheckStrictly": True,
            "remark": "1"
        }
        # 复用 common 公共字段，名称/权限字符以模块级时间戳 ts 拼接保证唯一
        resp_a, _, _ = creat_role(**{**common, "roleName": f"name_a_{ts}", "roleKey": f"key_a_{ts}"})
        assert resp_a.json()["code"] == 200
        resp_b, _, _ = creat_role(**{**common, "roleName": f"name_b_{ts}", "roleKey": f"key_b_{ts}"})
        assert resp_b.json()["code"] == 200

    # ===== 长度边界：roleName 上限 30（@Size 校验）=====
    @allure.title("角色名称恰好30个字符成功")
    def test_creat_role_name_30(self, creat_role):
        """验证边界值：roleName 恰好 30 字符（上限）时创建成功。"""
        # "1"*15 + "@b" + ts 恰好 30 字符：满足 @Size(max=30) 上限且内容唯一
        resp, role_id, _ = creat_role(roleName="1" * 15 + "@b" + ts)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert role_id is not None

    # ===== 长度边界：roleKey 上限 100（@Size 校验）=====
    @allure.title("角色权限字符恰好100个字符成功")
    def test_creat_role_key_100(self, creat_role):
        """验证边界值：roleKey 恰好 100 字符（上限）时创建成功。"""
        # "1"*85 + "@b" + ts 恰好 100 字符：满足 @Size(max=100) 上限且内容唯一
        resp, role_id, _ = creat_role(roleKey="1" * 85 + "@b" + ts)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert role_id is not None

    @allure.title("角色名称31个字符失败")
    def test_creat_role_name_31(self, creat_role):
        """验证边界值：roleName 超过上限 1 字符（31）时被参数校验拦截返回 601。"""
        # 超 1 字符 → @Size 校验拦截 → 601（正常行为，不是缺陷）；创建失败无数据，无需登记清理
        resp, _, _ = creat_role(roleName="1" * 16 + "@b" + ts)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] == False

    @allure.title("角色权限字符101个字符失败")
    def test_creat_role_key_101(self, role_api):
        """验证边界值：roleKey 超过上限 1 字符（101）时被参数校验拦截返回 601。"""
        # 超 1 字符 → @Size 校验拦截 → 601（正常行为）；此用例不经夹具直接调用接口，创建失败无残留数据
        resp = role_api.creat(**make_role(roleKey="1" * 86 + "@b" + ts))
        assert resp.json()["code"] == 601
        assert resp.json()["success"] == False

    # ===== 备注长度边界：恰好 500 成功（DB varchar(500) 上限）=====
    @allure.title("添加角色，备注刚好500个字符")
    def test_creat_remark_500(self, creat_role):
        """验证边界值：备注恰好 500 字符（数据库 varchar(500) 上限）时创建成功。"""
        # "a"*500 构造恰好 500 字符的备注，验证命中数据库字段长度上限时仍可正常落库
        resp, role_id, _ = creat_role(remark="a" * 500)
        assert resp.json()["code"] == 200
        assert role_id is not None

    # ===== 备注长度边界：501 → 500 泄漏（缺陷：模型层无长度校验，DB 层报错）=====
    @pytest.mark.xfail(reason="添加角色时备注超过500字符未做长度校验，返回500并泄漏SQL/表结构，正常应返回601且不泄漏")
    @allure.title("添加角色，备注刚好超过500个字符")
    def test_creat_remark_501(self, creat_role):
        """验证已知缺陷：备注 501 字符时模型层无长度校验，错误下沉数据库层返回 500 并泄漏 SQL/表结构。"""
        # 期望行为：601 参数校验拦截且不泄漏内部信息；
        # 实际缺陷：模型层缺长度校验，错误下沉到数据库层返回 500 并泄漏 SQL/表结构 → xfail
        resp, _, _ = creat_role(remark="a" * 501)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] == False
