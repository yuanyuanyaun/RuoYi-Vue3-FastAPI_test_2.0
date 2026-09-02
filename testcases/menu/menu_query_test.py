"""菜单模块-查询 测试用例。

覆盖接口：
    GET /system/menu/list                          菜单列表：非分页接口，返回 data 数组
    GET /system/menu/treeselect                    菜单树：返回嵌套层级树结构
    GET /system/menu/roleMenuTreeselect/{role_id}  角色菜单树：返回菜单树与该角色已勾选菜单 ID 列表
    GET /system/menu/{menu_id}                     菜单详情：按 menuId 返回单个菜单完整字段

测试策略：
    正向场景：菜单名称（LIKE 模糊）与状态（精确）筛选、菜单树与角色菜单树结构校验。
    边界场景：详情路径参数为空（不匹配路由 → HTTP 404）、非数字（int 解析失败 → HTTP 422）。
    已知缺陷(xfail)：查询不存在角色的菜单树时后端判空缺失抛 AttributeError 返回 500 泄漏；
    查询不存在菜单的详情时空模型保护返回 200 全空。
    跨模块去重：列表接口无分页参数，分页相关边界场景由用户/角色模块覆盖，此处不重复。
"""

import pytest
import allure
import requests


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("获取菜单列表接口")
@allure.description(
    "菜单列表为不分页接口（返回 data 数组，无分页参数），"
    "分页相关边界场景在用户/角色模块已覆盖，此处不重复。"
    "仅测菜单特有筛选字段（menuName/status）。"
)
class TestMenuList:
    """菜单列表查询用例：验证菜单特有筛选字段（menuName/status），列表为非分页接口。"""

    @allure.title("按菜单名称筛选")
    def test_list_filter_by_name(self, menu_api):
        """验证按菜单名称筛选：menuName 为 LIKE 模糊匹配，种子菜单「系统管理」应被命中。"""
        # menuName 为 LIKE 模糊匹配：种子菜单「系统管理」应被关键字命中，
        # 断言列表中存在名称完全一致的节点
        resp = menu_api.list(menuName="系统管理")
        data = resp.json()
        # 断言列表接口成功契约：业务 code 200 + 成功标识为 True
        assert data["code"] == 200
        assert data["success"] is True
        assert any(row["menuName"] == "系统管理" for row in data["data"])

    @allure.title("按状态筛选")
    def test_list_filter_by_status(self, menu_api):
        """验证按状态筛选：status 为精确匹配，返回的所有行状态都应等于 "0"（启用）。"""
        # status 为精确匹配：返回的所有行状态字段都应等于 "0"（启用）
        resp = menu_api.list(status="0")
        data = resp.json()
        # 断言列表接口成功契约：业务 code 200 + 成功标识为 True + 返回数据非空
        assert data["code"] == 200
        assert data["success"] is True
        assert data["data"]
        assert all(row["status"] == "0" for row in data["data"])


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("获取菜单树接口")
class TestMenuTree:
    """菜单树与角色菜单树查询用例：验证嵌套树结构与角色勾选数据契约。"""

    @allure.title("成功获取菜单树")
    def test_treeselect_success(self, menu_api):
        """验证菜单树成功返回嵌套层级结构：顶级节点含种子菜单「系统管理」且携带子节点。"""
        # 菜单树为嵌套结构：种子菜单「系统管理」是顶级节点（id=1）且应携带子节点 children
        resp = menu_api.treeselect()
        data = resp.json()
        # 断言菜单树接口成功契约：业务 code 200 + 成功标识为 True
        assert data["code"] == 200
        assert data["success"] is True
        top = [row for row in data["data"] if row["id"] == 1]
        assert top and top[0]["label"] == "系统管理"
        assert top[0]["children"]

    @allure.title("成功获取指定角色的菜单树")
    def test_role_menu_tree_success(self, menu_api):
        """验证指定角色的菜单树成功返回：menus 为完整菜单树，checkedKeys 为该角色已勾选菜单 ID 列表。"""
        # 角色菜单树契约：menus 为完整菜单树，checkedKeys 为该角色已勾选的菜单 ID 列表，
        # 是角色权限编辑弹窗的数据来源
        resp = menu_api.role_menu_tree(2)
        data = resp.json()
        # 断言角色菜单树成功契约：业务 code 200 + 成功标识为 True + 两个字段均为列表
        assert data["code"] == 200
        assert data["success"] is True
        assert isinstance(data["menus"], list)
        assert isinstance(data["checkedKeys"], list)

    @pytest.mark.xfail(
        reason="查询不存在角色的菜单树时后端未判空，role为None时读取role_id属性崩溃，"
               "返回500并泄漏Python内部错误，前端已经做出约束,一般情况下客户端OK"
    )
    @allure.description(
        "实测：roleMenuTreeselect/999 时后端 role 为 None，"
        "get_role_menu_dao 读取 role.role_id 抛 AttributeError，"
        "500 泄漏信息为：'NoneType' object has no attribute 'role_id'"
    )
    @allure.title("查询不存在角色的菜单树")
    def test_role_menu_tree_nonexist(self, menu_api):
        """已知缺陷用例：查询不存在角色的菜单树应被拦截，而非因判空缺失返回 500 并泄漏内部错误。"""
        # 缺陷路径：999 角色不存在，RoleDao.get_role_detail_by_id 返回 None，
        # get_role_menu_dao 读取 role.role_id 抛 AttributeError → 500 泄漏
        resp = menu_api.role_menu_tree(999)
        assert resp.json()["code"] != 500


@pytest.mark.menu
@allure.feature("菜单模块")
@allure.story("获取菜单详情接口")
class TestMenuDetail:
    """菜单详情查询用例：覆盖正常路径、路径参数边界与已知缺陷场景。"""

    @pytest.mark.xfail(reason="获取不存在菜单的详情本应报错却返回成功，前端已经做出约束,一般情况下客户端OK")
    @allure.description(
        "实测：查询不存在的菜单时，接口返回 200 且菜单字段全部为空（menuId 为 null），"
        "没有返回'菜单不存在'之类的错误提示"
    )
    @allure.title("获取不存在菜单的详情")
    def test_detail_nonexist(self, menu_api):
        """已知缺陷用例：查询不存在菜单的详情应报错，而非因空模型保护返回 200 全空。"""
        # 缺陷路径：menu_detail_services 对不存在的菜单返回空模型 MenuModel() 保护，
        # 接口 200 返回全空字段而非错误提示
        resp = menu_api.detail(999)
        assert resp.json()["code"] == 500

    @allure.title("详情路径参数为空")
    def test_detail_empty_path(self, menu_api):
        """边界用例：详情路径参数为空时，不匹配 /{menu_id} 路由，应被 HTTP 404 拦截。"""
        # 空路径参数不匹配 /{menu_id} 路由 → HTTP 404（框架层拦截）
        with pytest.raises(requests.exceptions.HTTPError) as e:
            menu_api.detail("")
        assert e.value.response.status_code == 404

    @allure.title("详情路径参数非数字")
    def test_detail_non_numeric(self, menu_api):
        """边界用例：详情路径参数为非数字时，int 解析失败应被 HTTP 422 拦截（干净报错）。"""
        # 非数字路径参数在 FastAPI 参数层 int 解析失败 → HTTP 422（干净报错，无信息泄漏）
        with pytest.raises(requests.exceptions.HTTPError) as e:
            menu_api.detail("abc")
        assert e.value.response.status_code == 422
