"""菜单模块-管理 测试用例。

覆盖接口：
    PUT    /system/menu             编辑菜单：全量字段更新
    DELETE /system/menu/{menu_ids}  删除菜单：支持逗号分隔批量删除
    PUT    /system/menu/updateSort  批量保存菜单排序：menuIds/orderNums 一一对应更新 order_num

测试策略：
    反向场景：编辑不存在的菜单（500 菜单不存在）、编辑时上级菜单选择自己（500 菜单特有规则）。
    业务规则：删除被拒返回业务 code 601（存在子菜单/已分配角色），
    与角色/岗位模块删除被拒返回 500 的异常类型相区分。
    边界场景：排序参数数量不匹配/非数字/ID≤0 → 500 干净报错（不泄漏信息）。
    已知缺陷(xfail)：删除不存在菜单时删除 0 行也返回删除成功（200 假成功）；
    排序含不存在的菜单 ID 时静默更新 0 行返回保存成功（200 假成功）。
    事务回滚：批量删除含被拒菜单时整批回滚，保证全有或全无的数据一致性。
"""

import time
import pytest
import allure


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("编辑菜单接口")
class TestMenuEdit:
    """编辑菜单接口（PUT /system/menu）用例：覆盖反向校验与菜单特有业务规则。"""

    @allure.title("编辑不存在的菜单")
    def test_edit_nonexist(self, menu_api):
        """验证编辑不存在的菜单被拒：接口返回 500 且提示「菜单不存在」，成功标识为 False。"""
        # 编辑 999：menu_detail_services 返回空模型（menu_id=None），
        # edit_menu_services 以 if menu_info.menu_id 判空 → 「菜单不存在」→ 500
        # （编辑走全量校验，menuName/orderNum/menuType 必填，缺失会返回 601）
        resp = menu_api.update(
            menuId=999,
            menuName="none",
            orderNum=1,
            menuType="C"
        )
        # 断言编辑被拒契约：业务 code 500 + 成功标识为 False + 提示包含「菜单不存在」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "菜单不存在" in resp.json()["msg"]

    @allure.title("编辑时上级菜单选择自己")
    def test_edit_parent_is_self(self, menu_api, creat_menu):
        """验证编辑时上级菜单选择自己被拒：接口返回 500 且提示「上级菜单不能选择自己」。"""
        # parentId 传自己的 menuId：edit_menu_services 显式校验 menu_id == parent_id → 500
        # （菜单特有规则；新增时 menu_id 为 None 不可能相等，因此仅编辑场景可覆盖）
        _, menu_id, name = creat_menu()
        resp = menu_api.update(
            menuId=menu_id,
            menuName=name,
            menuType="C",
            parentId=menu_id,
            orderNum=1
        )
        # 断言编辑被拒契约：业务 code 500 + 成功标识为 False + 提示包含「上级菜单不能选择自己」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "上级菜单不能选择自己" in resp.json()["msg"]


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("删除菜单接口")
class TestMenuDelete:
    """删除菜单接口（DELETE /system/menu/{menu_ids}）用例：覆盖批量删除、业务拒绝与事务回滚。"""

    @allure.title("批量删除菜单成功")
    def test_delete_batch(self, menu_api, creat_menu):
        """验证批量删除成功：两个自建菜单同时删除后，列表复查均不可见。"""
        # 批量删除两个自建菜单：断言接口成功，并按名称过滤列表确认两个菜单均不可见
        _, mid1, name1 = creat_menu()
        _, mid2, name2 = creat_menu()
        resp = menu_api.delete(f"{mid1},{mid2}")
        # 断言批量删除成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] is True
        # 列表复查：两个自建菜单均不应再出现在列表数据中
        assert not [r for r in menu_api.list(menuName=name1).json()["data"] if r["menuName"] == name1]
        assert not [r for r in menu_api.list(menuName=name2).json()["data"] if r["menuName"] == name2]

    @pytest.mark.xfail(reason="删除不存在的菜单本应报错却返回删除成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("删除不存在的菜单")
    def test_delete_nonexist(self, menu_api):
        """已知缺陷用例：删除不存在的菜单应报错，而非无存在性校验返回删除成功（200 假成功）。"""
        # 缺陷路径：删除 999 无存在性校验，删除 0 行也返回「删除成功」→ 200 假成功
        resp = menu_api.delete(999)
        assert resp.json()["code"] == 500

    @allure.title("删除有子菜单的菜单")
    def test_delete_has_child(self, menu_api):
        """验证删除有子菜单的菜单被拒：存在子菜单触发业务校验返回 601。"""
        # 菜单 1（系统管理）含子菜单 100-107：has_child 检查触发 ServiceWarning → 601
        # （菜单/部门删除被拒为 601，角色/岗位为 500，异常类型不同）
        resp = menu_api.delete(1)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
        assert "存在子菜单,不允许删除" in resp.json()["msg"]

    @allure.title("删除已分配角色的菜单")
    def test_delete_assigned(self, menu_api):
        """验证删除已绑定角色的菜单被拒：菜单已分配角色触发业务校验返回 601。"""
        # 菜单 111（数据监控）无子菜单但已绑定角色：check_menu_exist_role_dao 命中 → 601
        resp = menu_api.delete(111)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
        assert "菜单已分配,不允许删除" in resp.json()["msg"]

    @allure.title("批量删除含已分配菜单（事务回滚）")
    def test_delete_batch_with_assigned(self, menu_api, creat_menu):
        """验证批量删除含被拒菜单时整批回滚：被拒后自建菜单必须未被删除（全有或全无）。"""
        # 批量参数 "1,id"：菜单 1 有子菜单触发 601 → 整个事务回滚，
        # 自建菜单必须未被删除（全有或全无的一致性保证）
        _, mid, name = creat_menu()
        resp = menu_api.delete(f"1,{mid}")
        assert resp.json()["code"] == 601
        # 事务回滚验证：自建菜单在列表中仍可查询到，确认未被级联删除
        assert [r for r in menu_api.list(menuName=name).json()["data"] if r["menuName"] == name]


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("保存菜单排序接口")
class TestMenuSort:
    """保存菜单排序接口（PUT /system/menu/updateSort）用例：覆盖成功、参数异常与已知缺陷。"""

    @allure.title("保存菜单排序成功")
    def test_sort_success(self, menu_api, creat_menu):
        """验证批量保存排序成功：menuIds/orderNums 一一对应更新 order_num，列表复查顺序已交换。"""
        # 模拟菜单管理页拖拽排序后的保存：menuIds/orderNums 一一对应批量更新 order_num
        _, mid1, name1 = creat_menu()
        _, mid2, name2 = creat_menu()
        resp = menu_api.update_sort(f"{mid1},{mid2}", "2,1")
        # 断言排序保存成功契约：业务 code 200 + 提示「保存成功」
        assert resp.json()["code"] == 200
        assert resp.json()["msg"] == "保存成功"
        # 列表复查核对显示顺序已交换：mid1 的 orderNum 应为 2，mid2 的应为 1
        rows1 = menu_api.list(menuName=name1).json()["data"]
        rows2 = menu_api.list(menuName=name2).json()["data"]
        assert [r for r in rows1 if r["menuId"] == mid1][0]["orderNum"] == 2
        assert [r for r in rows2 if r["menuId"] == mid2][0]["orderNum"] == 1

    @allure.title("保存排序时参数数量不匹配")
    def test_sort_mismatch(self, menu_api):
        """边界用例：排序参数数量不匹配时应被解析校验拦截，返回 500 干净报错。"""
        # 两个参数串必须一一对应：数量不一致 → 解析校验失败 → 500（干净报错，不泄漏）
        resp = menu_api.update_sort("1,2", "1")
        assert resp.json()["code"] == 500
        assert resp.json()["msg"] == "菜单排序参数不正确"

    @allure.title("保存排序时参数非数字")
    def test_sort_non_numeric(self, menu_api):
        """边界用例：排序参数非数字时应被解析校验拦截，返回 500 干净报错。"""
        # 非数字参数在解析阶段失败 → 500 干净报错
        resp = menu_api.update_sort("1", "abc")
        assert resp.json()["code"] == 500
        assert resp.json()["msg"] == "菜单排序参数不正确"

    @allure.title("保存排序时菜单ID为0或负数")
    def test_sort_invalid_id(self, menu_api):
        """边界用例：菜单 ID 为 0 或负数时应被显式校验拦截，返回 500 干净报错。"""
        # 后端显式校验 menu_id <= 0 → 500，故 0/负数作为边界值单独覆盖
        resp = menu_api.update_sort("0", "1")
        assert resp.json()["code"] == 500
        assert resp.json()["msg"] == "菜单排序参数不正确"

    @pytest.mark.xfail(reason="保存排序含不存在的菜单ID时静默更新0行，返回保存成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("保存排序含不存在的菜单")
    def test_sort_nonexist_id(self, menu_api):
        """已知缺陷用例：排序含不存在的菜单 ID 应报错，而非静默更新 0 行返回保存成功（200 假成功）。"""
        # 缺陷路径：999999 不存在时批量 UPDATE 匹配 0 行无异常 → 200「保存成功」假成功
        resp = menu_api.update_sort("999999", "1")
        assert resp.json()["code"] == 500
