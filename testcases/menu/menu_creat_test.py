"""菜单模块-新增 测试用例。

覆盖接口：
    POST /system/menu   新增菜单：创建目录(M)/菜单(C)/按钮(F) 节点

测试策略：
    数据驱动：用例数据由 data/menu/menu_creat_data.json 提供，
    fail_code_cases 为业务失败场景（HTTP 200 + 业务 code 校验拦截），
    fail_status_cases 为 HTTP 状态失败场景（4xx/5xx 抛 HTTPError）。
    边界场景：menuName/perms/remark 长度边界（模型层 @Size 校验与 DB varchar 上限），
    各覆盖恰好达标与恰好超限两档边界值。
    唯一性验证：除名称与路由外其他字段相同的重复新增可成功，验证唯一性约束的字段范围。
    已知缺陷(xfail)：parentId=999 未校验上级菜单存在性产生孤儿菜单假成功；
    备注超长未做模型层校验返回 500 并泄漏 SQL/表结构信息。
    工厂函数：make_menu 在默认数据上叠加 overrides 构造请求参数，用例内不重复造数。
"""

import json
import allure
import pytest
import requests
from utils.function import make_menu

# 模块导入时一次性加载数据驱动用例文件：失败场景的 overrides 与期望结果集中管理，
# 避免用例内硬编码数据，便于数据维护与用例扩展
with open("data/menu/menu_creat_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("添加菜单接口")
class TestMenuCreat:
    """新增菜单用例：覆盖数据驱动失败场景、字段唯一性与长度边界、已知缺陷（xfail）。"""

    # ===== 业务失败场景：HTTP 200 + 业务 code 校验拦截（601/500）=====
    @pytest.mark.parametrize("case", data["fail_code_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_code(self, case, menu_api):
        """验证数据驱动声明的业务失败场景：接口返回声明的业务 code 且成功标识为 False。"""
        # 在工厂默认数据上叠加 overrides 构造请求参数：必填字段缺省置 None 触发模型层校验拦截，
        # 唯一性冲突字段使用固定值触发数据库唯一约束，期望结果由用例数据文件声明
        resp = menu_api.creat(**make_menu(**case["overrides"]))
        # 断言业务失败契约：业务 code 与数据文件期望一致 + 成功标识为 False
        assert resp.json()["code"] == case["expected_code"]
        assert resp.json()["success"] is False

    # ===== HTTP 状态失败场景：4xx/5xx 拦截并抛 HTTPError =====
    @pytest.mark.parametrize("case", data["fail_status_cases"])
    @allure.title("{case[name]}")
    def test_creat_fail_status(self, case, menu_api):
        """验证数据驱动声明的 HTTP 状态失败场景：请求被 4xx/5xx 拦截并抛出 HTTPError。"""
        # HTTP 层失败以异常形式暴露：断言捕获的 HTTPError 中携带数据文件声明的期望状态码
        with pytest.raises(requests.exceptions.HTTPError) as e:
            menu_api.creat(**make_menu(**case["overrides"]))
        assert e.value.response.status_code == case["expected_status"]

    # ===== 已知缺陷：上级菜单不存在（parentId=999）→ 假成功 + 孤儿菜单 =====
    @pytest.mark.xfail(reason="新增时未校验上级菜单是否存在，parentId传不存在的值仍创建成功，产生孤儿菜单数据")
    @allure.title("添加上级菜单不存在的菜单")
    def test_creat_defect(self, creat_menu):
        """已知缺陷用例：新增接口未校验上级菜单存在性，parentId 传不存在的值时假成功并产生孤儿菜单数据。"""
        # 缺陷路径：后端无父级存在性校验 → 接口 200 假成功，菜单挂载到不存在的父级成为孤儿数据；
        # creat_menu 夹具负责登记并级联清理该残留，避免污染后续用例与共享数据库
        resp, _, _ = creat_menu(parentId=9999)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    # ===== 唯一性验证：除名称和路由外，其他字段相同可重复添加 =====
    @allure.title("除名称和路由外其他字段相同可重复添加")
    def test_creat_repeat_other_fields(self, creat_menu):
        """验证唯一性约束范围：除菜单名称与路由外，其余字段完全相同的重复新增允许成功。"""
        # 唯一性约束仅针对菜单名称（同级）与路由（path/routeName），
        # 其余字段（父级、排序、组件、类型、可见性、状态等）相同不影响新增
        common = {
            "parentId": 100,
            "orderNum": 1,
            "component": "system/user/index",
            "menuType": "C",
            "visible": "0",
            "status": "0",
            "icon": "user"
        }
        # 同一组公共字段连续新增两次，两次均应成功，验证唯一性约束不覆盖这些字段
        resp_a, _, _ = creat_menu(**common)
        resp_b, _, _ = creat_menu(**common)
        assert resp_a.json()["code"] == 200
        assert resp_b.json()["code"] == 200

    # ===== 长度边界：menuName 上限 50（模型层 @Size 校验）=====
    @allure.title("菜单名称恰好 50 字符成功")
    def test_creat_name_50(self, creat_menu):
        """边界值用例：菜单名称恰好 50 字符（模型层 @Size 上限）时新增成功。"""
        # 构造恰好 50 字符的名称（48 个 a + "1@"）：命中 @Size 上限边界值，应通过模型层校验
        resp, menu_id, _ = creat_menu(menuName="a" * 48 + "1@")
        assert resp.json()["code"] == 200
        assert menu_id is not None

    @allure.title("菜单名称恰好超过 50 字符")
    def test_creat_name_51(self, creat_menu):
        """边界值用例：菜单名称恰好超过 50 字符（51 字符）时被模型层 @Size 校验拦截。"""
        # 超限 1 字符 → @Size 校验拦截 → 业务 code 601（正常校验行为，区别于缺陷场景）
        resp, _, _ = creat_menu(menuName="a" * 49 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    # ===== 长度边界：perms 上限 100（模型层 @Size 校验）=====
    @allure.title("权限标识恰好 100 字符成功")
    def test_creat_perms_100(self, creat_menu):
        """边界值用例：权限标识恰好 100 字符（模型层 @Size 上限）时新增成功。"""
        # 构造恰好 100 字符的权限标识（98 个 a + "1@"）：命中 @Size 上限边界值，应通过校验
        resp, menu_id, _ = creat_menu(perms="a" * 98 + "1@")
        assert resp.json()["code"] == 200
        assert menu_id is not None

    @allure.title("权限标识恰好超过 100 字符")
    def test_creat_perms_101(self, creat_menu):
        """边界值用例：权限标识恰好超过 100 字符（101 字符）时被模型层 @Size 校验拦截。"""
        # 超限 1 字符 → @Size 校验拦截 → 业务 code 601
        resp, _, _ = creat_menu(perms="a" * 99 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False

    # ===== 长度边界：remark 上限 500（DB varchar(500) 上限，模型层无 @Size 约束）=====
    @allure.title("备注恰好 500 字符成功")
    def test_creat_remark_500(self, creat_menu):
        """边界值用例：备注恰好 500 字符（DB varchar(500) 上限）时新增成功。"""
        # 备注无模型层 @Size 约束，实际上限由 DB varchar(500) 决定；恰好 500 字符可正常落库
        resp, menu_id, _ = creat_menu(remark="a" * 498 + "1@")
        assert resp.json()["code"] == 200
        assert menu_id is not None

    # ===== 已知缺陷：501 字符 → 500 泄漏（模型层无长度校验，DB 层报错）=====
    @pytest.mark.xfail(reason=f"已知缺陷备注超过500字符未做长度校验，返回500并泄漏SQL/表结构，"
                              f"正常应返回601且不泄漏,前端并未做出约束,故该错误比较严重")
    @allure.title("添加菜单备注超过500字符")
    def test_creat_remark_501(self, creat_menu):
        """已知缺陷用例：备注超过 500 字符时模型层无长度校验，DB 层报错返回 500 并泄漏 SQL/表结构信息。"""
        # 缺陷路径：超限数据穿透模型层直达 DB → 500 + SQL/表结构泄漏；
        # 正确行为应如名称/权限标识一样由模型层拦截并返回业务 code 601
        resp, _, _ = creat_menu(remark="a" * 499 + "1@")
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
