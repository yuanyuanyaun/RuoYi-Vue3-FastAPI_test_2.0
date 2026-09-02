"""角色模块-冒烟链路 测试用例。

覆盖接口：
    GET    /system/role/list       获取角色分页列表接口：分页返回角色列表，支持按名称/权限字符/状态筛选
    POST   /system/role            添加角色接口：新增角色并写入菜单关联，返回 role_id
    GET    /system/role/{role_id}  获取角色详情接口：返回指定角色的完整字段
    PUT    /system/role            编辑角色接口：全字段更新角色及其菜单关联（替换式重写）
    DELETE /system/role/{role_ids} 删除角色接口：按逗号分隔的角色 id 批量软删除，并级联清理关联表

测试策略：
    正向主链路闭环：默认列表 → 全字段添加 → 按权限字符查回核对 → 详情 → 最大字段编辑 → 删除，
    覆盖角色 CRUD 全流程，验证接口层响应与数据库层落库的一致性。
    用例之间存在数据依赖：role_id 由添加用例查回后缓存在类变量，供详情/编辑/删除用例复用，
    因此本类用例必须按定义顺序执行，不可单独或乱序运行。
    数据准备：角色名称与权限字符以时间戳拼接保证全局唯一，避免与种子数据及历史运行残留冲突。
    数据库校验：每个写操作后核对 sys_role 主表字段，并校验 sys_role_menu、sys_role_dept
    两张关联表的写入与清理，验证菜单关联的替换语义与软删除(del_flag)行为。
    业务规则：新增/编辑接口均忽略 deptIds（后端仅写菜单关联），部门绑定只能经
    dataScope 接口完成，故删除前 sys_role_dept 恒为空。
"""

import pytest
import allure
import time


@pytest.mark.role
@pytest.mark.smoke
@allure.feature("角色模块")
class TestRoleSmoke:
    """角色模块冒烟用例：验证角色 CRUD 主链路（列表/添加/详情/编辑/删除）的完整正向闭环。"""

    # 类级共享状态：role_id 由添加用例按权限字符查回后登记，供链路内后续用例复用；
    # 名称/权限字符以秒级时间戳拼接，保证每次运行生成的测试数据全局唯一，避免与既有数据冲突
    role_id = None
    name = f"test_role{time.strftime('%Y%m%d%H%M%S')}"
    key = f"test_key{time.strftime('%Y%m%d%H%M%S')}"

    @allure.story("获取角色分页列表接口")
    @allure.title("默认条件获取角色列表成功")
    def test_role_list_success(self, role_api):
        """验证不传任何查询参数时列表接口返回成功契约，且默认分页参数与预置数据基线成立。"""
        # 调用不带查询参数，验证接口默认分页契约（pageNum=1/pageSize=10）；
        # 种子角色（超级管理员/普通角色）保证 total>=2 基线成立，作为后续链路用例的数据前提
        resp = role_api.list()
        # 断言接口成功契约：HTTP 200 + 业务 code 200 + 成功标识为 True
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # 断言默认分页参数回显：pageSize=10、pageNum=1，与请求侧默认值保持一致
        assert data["pageSize"] == 10
        assert data["pageNum"] == 1
        # 断言数据基线：预置角色数量 >= 2，保证链路内"按唯一权限字符筛选命中 1 条"等断言成立
        assert data["total"] >= 2

    @allure.story("添加角色接口")
    @allure.title("添加角色成功")
    def test_add_role_success(self, role_api, mysql):
        """验证全字段正向创建角色成功：接口返回成功契约，且主表与菜单关联表落库正确。"""
        # 全字段正向创建：覆盖名称/权限字符/排序/状态/数据权限(自定)/严格模式开关/菜单/部门/备注，
        # 验证接口对全量入参的支持；deptIds 虽传入但按业务规则应被后端忽略
        resp = role_api.creat(
            **{
                "roleName": TestRoleSmoke.name,
                "roleKey": TestRoleSmoke.key,
                "roleSort": 99,
                "status": "0",
                "dataScope": "2",
                "menuCheckStrictly": True,
                "deptCheckStrictly": True,
                "deptIds": [100, 101],
                "menuIds": [1, 2, 100, 101],
                "remark": "冒烟测试添加数据最多角色"
            }
        )
        # 断言创建成功契约：HTTP 200 + 业务 code 200 + 成功标识为 True
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # API 验证：按权限字符（唯一键）查回新角色并逐个字段核对，
        # 确认新增数据可被检索且字段与入参完全一致
        query = role_api.list(roleKey=TestRoleSmoke.key)
        query_data = query.json()
        # 唯一性前提：权限字符为时间戳唯一值，查询结果应恰好命中 1 条
        assert query_data["total"] == 1
        assert query_data["rows"][0]["roleName"] == TestRoleSmoke.name
        assert query_data["rows"][0]["roleKey"] == TestRoleSmoke.key
        assert query_data["rows"][0]["roleSort"] == 99
        assert query_data["rows"][0]["status"] == "0"
        assert query_data["rows"][0]["dataScope"] == "2"
        assert query_data["rows"][0]["remark"] == "冒烟测试添加数据最多角色"
        # 记录 roleId 到类变量，供详情/编辑/删除用例复用，避免链路内重复查询
        TestRoleSmoke.role_id = query_data["rows"][0]["roleId"]
        # DB 校验：查询 sys_role 主表，核对新增字段全部落库，与接口返回保持一致
        row = mysql["one"](
            "select role_name,role_key,role_sort,status,data_scope,remark "
            "from sys_role where role_id=%s", (TestRoleSmoke.role_id,)
        )
        assert row["role_name"] == TestRoleSmoke.name
        assert row["role_key"] == TestRoleSmoke.key
        assert row["role_sort"] == 99
        assert row["status"] == "0"
        assert row["data_scope"] == "2"
        assert row["remark"] == "冒烟测试添加数据最多角色"
        # DB 校验：sys_role_menu 关联表按 menuIds 全量写入，验证菜单关联落库无遗漏
        menu = mysql["all"]("select menu_id from sys_role_menu where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert {r["menu_id"] for r in menu} == {1, 2, 100, 101}
        # DB 校验：新增接口忽略 deptIds（后端仅写菜单关联），sys_role_dept 应保持为空
        dept = mysql["all"]("select dept_id from sys_role_dept where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert not dept

    @allure.story("获取角色详情接口")
    @allure.title("成功获取角色详情")
    def test_get_role_success(self, role_api):
        """验证携带链路内创建的角色 id 查询详情时返回成功契约，字段级断言交由编辑用例承担。"""
        # 详情用例仅校验响应码；字段级断言由编辑用例的详查接口承担，避免链路内重复断言
        resp = role_api.get_detail(TestRoleSmoke.role_id)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

    @allure.story("编辑角色接口")
    @allure.title("最大程度的编辑角色成功")
    def test_update_role_success(self, role_api, mysql):
        """验证全字段编辑角色成功：接口返回成功契约，且主表与菜单关联表按替换语义更新落库。"""
        # 全字段编辑：修改名称/权限字符/排序/状态(停用)/数据权限(本部门)，菜单更换为 [1,2,3,100]，
        # 验证编辑接口对全量字段的覆盖能力
        resp = role_api.update(
            **{
                "roleId": TestRoleSmoke.role_id,
                "roleName": f"update_{TestRoleSmoke.name}",
                "roleKey": f"update_{TestRoleSmoke.key}",
                "roleSort": 88,
                "status": "1",
                "dataScope": "3",
                "menuCheckStrictly": False,
                "deptCheckStrictly": False,
                "deptIds": [102],
                "menuIds": [1, 2, 3, 100],
                "remark": "最大程度编辑"
            }
        )
        # 断言编辑成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # API 验证：详查编辑后的角色，核对各字段与入参一致，确认编辑覆盖生效
        query = role_api.get_detail(TestRoleSmoke.role_id)
        query_data = query.json()
        assert query_data["code"] == 200
        assert query_data["success"] == True
        assert query_data["data"]["roleName"] == f"update_{TestRoleSmoke.name}"
        assert query_data["data"]["roleKey"] == f"update_{TestRoleSmoke.key}"
        assert query_data["data"]["roleSort"] == 88
        assert query_data["data"]["status"] == "1"
        assert query_data["data"]["dataScope"] == "3"
        assert query_data["data"]["remark"] == "最大程度编辑"
        # DB 校验：查询 sys_role 主表，核对编辑后的字段已落库
        row = mysql["one"](
            "select role_name,role_key,role_sort,status,data_scope,remark "
            "from sys_role where role_id=%s", (TestRoleSmoke.role_id,)
        )
        assert row["role_name"] == f"update_{TestRoleSmoke.name}"
        assert row["role_key"] == f"update_{TestRoleSmoke.key}"
        assert row["role_sort"] == 88
        assert row["status"] == "1"
        assert row["data_scope"] == "3"
        assert row["remark"] == "最大程度编辑"
        # DB 校验：菜单关联为替换语义（先清空旧关联再写入新关联），结果应恰为 {1,2,3,100}
        menu = mysql["all"]("select menu_id from sys_role_menu where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert {r["menu_id"] for r in menu} == {1, 2, 3, 100}
        # DB 校验：编辑接口同样忽略 deptIds，部门关联仍为空（部门绑定仅 dataScope 接口生效）
        dept = mysql["all"]("select dept_id from sys_role_dept where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert not dept

    @allure.story("删除角色接口")
    @allure.title("删除角色成功")
    def test_delete_role_success(self, role_api, mysql):
        """验证删除自建角色成功：接口返回成功契约，列表查不到且主表软删除标记与关联表清理落库。"""
        # 删除链路内自建角色：该角色未分配任何用户，可正常通过后端"已分配"保护校验，删除应成功
        resp = role_api.delete(TestRoleSmoke.role_id)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # API 验证：按编辑后的名称+权限字符组合查询，应查不到已删除的角色
        query = role_api.list(
            roleName=f"update_{TestRoleSmoke.name}",
            roleKey=f"update_{TestRoleSmoke.key}"
        )
        query_data = query.json()
        assert query_data["rows"] == []
        assert query_data["total"] == 0
        # DB 校验：删除采用软删除策略，主表 del_flag 置为 '2'，且菜单/部门关联表随之清空
        row = mysql["one"]("select del_flag from sys_role where role_id=%s",
                           (TestRoleSmoke.role_id,))
        assert row["del_flag"] == "2"
        menu = mysql["all"]("select menu_id from sys_role_menu where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert not menu
        dept = mysql["all"]("select dept_id from sys_role_dept where role_id=%s",
                            (TestRoleSmoke.role_id,))
        assert not dept
