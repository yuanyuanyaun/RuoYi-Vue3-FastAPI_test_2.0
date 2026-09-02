"""角色模块-管理操作 测试用例。

覆盖接口：
    PUT    /system/role                     编辑角色接口：全字段更新角色及其菜单关联
    DELETE /system/role/{role_ids}          删除角色接口：按逗号分隔的角色 id 批量删除
    PUT    /system/role/changeStatus        修改角色状态接口：启用/停用角色
    GET    /system/role/deptTree/{role_id}  获取角色部门树接口：返回部门树与已勾选部门
    PUT    /system/role/dataScope           编辑角色数据权限接口：设置数据范围并绑定部门

测试策略：
    反向：对不存在的角色与超级管理员执行编辑/删除/改状态/改数据权限，
    验证后端保护性校验与错误返回。
    已知缺陷(xfail)：编辑缺 menuIds 触发 KeyError 500 泄漏、删除不存在的角色 200 假成功、
    不存在角色的部门树 200 假成功。
    事务回滚：批量删除含已分配角色时整体回滚，自建角色不被删除（全有或全无）。
    业务规则：编辑/删除均受唯一性检查与超级管理员保护；deptIds 仅在 dataScope 接口生效，
    新增/编辑接口均忽略。
    数据准备：自建角色由夹具 creat_role 创建并在测试结束后自动清理，避免残留数据。
"""

import time
import pytest
import allure
import requests


# ===== 参考：菜单ID对照（sys_menu.menu_id，仅列本文件用例用到的，完整 100 个以数据库为准） =====
# 1 系统管理(M目录)   2 系统监控(M目录)   3 系统工具(M目录)
# 100 用户管理  101 角色管理  102 菜单管理  103 部门管理  104 岗位管理
# 105 字典管理  106 参数设置  107 通知公告  108 日志管理(M目录)
# 109 在线用户  110 定时任务  111 数据监控  112 服务监控  113 缓存监控
# 说明：M=目录 C=菜单 F=按钮；角色挂载目录菜单时通常需连带子菜单挂载，权限方能生效；
#       编辑角色时 menuIds 为替换式语义（后端先清空旧菜单再写入新菜单）
# ================================================================================================


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("编辑角色接口")
class TestRoleEdit:
    """编辑角色接口（PUT /system/role），覆盖不存在角色、超级管理员保护、唯一性冲突与缺参缺陷。"""

    @allure.title("编辑不存在的角色")
    def test_edit_nonexist_role(self, role_api):
        """验证反向场景：编辑不存在的角色触发后端内部错误返回 500（已知缺陷，仅断言 code）。"""
        # 编辑 999：role_detail_services 返回空模型（role_id=None），if role_info 判断永远为真，
        # 直接走 UPDATE 匹配 0 行 → SQLAlchemy 报错 → 500 泄漏（缺陷，只断言 code 与成功标识）
        resp = role_api.update(
            roleId=999,
            roleName="none",
            roleKey="k_none",
            roleSort=9,
            menuIds=[1, 2, 100]
        )
        # 断言后端以 500 暴露内部错误，且成功标识为 False
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False

    @allure.title("无法编辑超级管理员")
    def test_edit_admin_rejected(self, role_api):
        """验证超级管理员保护：编辑 roleId=1 被后端保护性校验拦截返回 500。"""
        # 超管保护：roleId=1 → check_admin 置 admin=True → check_role_allowed_services 拦截
        resp = role_api.update(
            roleId=1,
            roleName="改名",
            roleKey="k_admin",
            roleSort=9,
            menuIds=[1, 2, 100]
        )
        # 断言拦截结果：code 500 + success False + 错误消息明确提示不允许操作超级管理员
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False
        assert "不允许操作超级管理员" in resp.json()["msg"]

    @allure.title("编辑时角色名称重复")
    def test_edit_duplicate_name(self, role_api, creat_role):
        """验证唯一性校验：编辑时角色名称与既有数据重复被拦截返回 500。"""
        # 先经夹具 creat_role 创建自建角色（测试结束自动清理），再尝试将名称改为种子"超级管理员"，
        # 触发名称唯一性检查（新增/编辑共用同一校验函数）→ 500
        _, role_id, _ = creat_role()
        resp = role_api.update(
            roleId=role_id, roleName="超级管理员",
            roleKey=f"k_{int(time.time() * 1000)}",
            roleSort=9,
            menuIds=[1, 2, 100]
        )
        # 断言拦截结果：code 500 + success False + 提示"角色名称已存在"
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False
        assert "角色名称已存在" in resp.json()["msg"]

    @allure.title("编辑时权限字符重复")
    def test_edit_duplicate_key(self, role_api, creat_role):
        """验证唯一性校验：编辑时权限字符与既有数据重复被拦截返回 500。"""
        # 将自建角色的权限字符改为种子的 "admin"，触发权限字符唯一性检查 → 500
        _, role_id, _ = creat_role()
        resp = role_api.update(
            roleId=role_id,
            roleName=f"n_{int(time.time() * 1000)}",
            roleKey="admin",
            roleSort=9,
            menuIds=[1, 2, 100]
        )
        # 断言拦截结果：code 500 + 提示"角色权限已存在"
        assert resp.json()["code"] == 500
        assert "角色权限已存在" in resp.json()["msg"]

    @pytest.mark.xfail(
        reason="编辑角色不带menuIds时后端KeyError崩溃返回500并泄漏内部键名，"
               "前端已经做出约束,一般情况下客户端OK"
    )
    @allure.title("编辑角色缺菜单权限")
    def test_edit_missing_menu_ids(self, role_api, creat_role):
        """验证已知缺陷：编辑请求缺 menuIds 时后端 KeyError 崩溃返回 500 并泄漏内部键名。"""
        # 缺陷根因（源码）：edit_role_services 里 model_dump(exclude_unset=True) 后
        # del edit_role['menu_ids'] —— 请求没传 menuIds 时字典里没有该键 → KeyError → 500 泄漏；
        # 期望正常返回 200，断言不成立 → xfail
        _, role_id, _ = creat_role()
        resp = role_api.update(
            roleId=role_id, roleName=f"n_{int(time.time() * 1000)}",
            roleKey=f"k_{int(time.time() * 1000)}", roleSort=9
        )
        assert resp.json()["code"] == 200


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("删除角色接口")
class TestRoleDelete:
    """删除角色接口（DELETE /system/role/{role_ids}），覆盖批量删除、事务回滚、保护性拦截与假成功缺陷。"""

    @allure.title("批量删除角色成功")
    def test_delete_batch(self, role_api, creat_role):
        """验证正向链路：批量删除两个自建角色成功，列表复查均查不到。"""
        # 经夹具创建两个自建角色，删除后按其名称复查
        _, rid1, name1 = creat_role()
        _, rid2, name2 = creat_role()
        # 逗号分隔批量删除：后端按 role_ids 逐个软删
        resp = role_api.delete(f"{rid1},{rid2}")
        # 断言批量删除成功契约：code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # API 复查：按名称分别查询，两个角色均不可见（total=0）
        assert role_api.list(roleName=name1).json()["total"] == 0
        assert role_api.list(roleName=name2).json()["total"] == 0

    @allure.title("批量删除含不存在的角色")
    def test_delete_batch_with_nonexist(self, role_api, creat_role):
        """验证幂等删除：批量删除含不存在的角色 id 时静默无操作，已存在角色正常删除。"""
        # "999,id"：999 无存在性校验（静默无操作），已存在的角色正常被删（幂等）
        _, rid, name = creat_role()
        resp = role_api.delete(f"999,{rid}")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # API 复查：存在的角色已被删除
        assert role_api.list(roleName=name).json()["total"] == 0

    @allure.title("批量删除含已绑定的角色（事务回滚）")
    def test_delete_batch_with_assigned(self, role_api, creat_role):
        """验证事务回滚：批量删除含已分配用户的角色时整体回滚，自建角色不被删除。"""
        # "2,id"：角色2已分配用户 → 删除时抛"已分配"异常 → 整个事务回滚，自建角色未被删
        _, rid, name = creat_role()
        resp = role_api.delete(f"2,{rid}")
        # 断言删除被拦截（code 500），且事务回滚后自建角色仍可查到（total=1，全有或全无）
        assert resp.json()["code"] == 500
        assert role_api.list(roleName=name).json()["total"] == 1

    @allure.title("批量删除含超级管理员（前置拦截）")
    def test_delete_batch_with_admin(self, role_api, creat_role):
        """验证前置拦截：批量删除含超级管理员时 controller 层直接拦截，删除逻辑未执行。"""
        # "1,id"：controller 前置检查超管直接拦截（在 service 之前），删除逻辑未执行
        _, rid, name = creat_role()
        resp = role_api.delete(f"1,{rid}")
        # 断言拦截结果（code 500），且自建角色未被删除（total=1）
        assert resp.json()["code"] == 500
        assert role_api.list(roleName=name).json()["total"] == 1

    @pytest.mark.xfail(reason="删除不存在的角色本应报错却返回删除成功，"
                              "前端已经做出约束,一般情况下客户端OK")
    @allure.title("删除不存在的角色")
    def test_delete_nonexist(self, role_api):
        """验证已知缺陷：删除不存在的角色返回"删除成功"（200 假成功），期望报错未实现。"""
        # 删除 999：无存在性校验，软删 0 行也返回「删除成功」→ 200 假成功（缺陷）；
        # 期望返回 500 报错，断言不成立 → xfail
        resp = role_api.delete(999)
        assert resp.json()["code"] == 500

    @allure.title("无法删除超级管理员")
    def test_delete_admin_rejected(self, role_api):
        """验证超级管理员保护：删除 roleId=1 被保护性校验拦截返回 500。"""
        # 超管保护：check_role_allowed_services 拦截 → 500
        resp = role_api.delete(1)
        assert resp.json()["code"] == 500
        assert "不允许操作超级管理员" in resp.json()["msg"]

    @allure.title("无法删除已分配用户的角色")
    def test_delete_assigned_rejected(self, role_api):
        """验证已分配保护：删除已分配用户的角色被拦截返回 500 并提示已分配。"""
        # 角色2（普通角色）已分配 niangao：count_user_role_dao > 0 → 500
        resp = role_api.delete(2)
        assert resp.json()["code"] == 500
        assert "已分配" in resp.json()["msg"]


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("修改角色状态接口")
class TestRoleStatus:
    """修改角色状态接口（PUT /system/role/changeStatus），覆盖不存在角色与超级管理员保护。"""

    @allure.title("修改不存在角色的状态")
    def test_change_status_nonexist(self, role_api):
        """验证反向场景：修改不存在角色的状态触发内部错误返回 500（角色无存在性保护）。"""
        # 改 999 状态：同编辑链路，UPDATE 0 行 → SQLAlchemy 500（角色无存在性保护）
        resp = role_api.change_status(999, "1")
        assert resp.json()["code"] == 500

    @allure.title("无法修改超级管理员的状态")
    def test_change_status_admin_rejected(self, role_api):
        """验证超级管理员保护：修改 roleId=1 的状态被拦截返回 500。"""
        # 超管保护 → 500
        resp = role_api.change_status(1, "1")
        assert resp.json()["code"] == 500
        assert "不允许操作超级管理员" in resp.json()["msg"]


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("获取角色部门树接口")
class TestRoleDeptTree:
    """获取角色部门树接口（GET /system/role/deptTree/{role_id}），覆盖正向查询与不存在角色的假成功缺陷。"""

    @allure.title("成功获取角色部门树")
    def test_dept_tree_success(self, role_api, creat_role):
        """验证正向链路：自建角色（未绑部门）的部门树返回全量部门且 checkedKeys 为空列表。"""
        # 自建角色（未绑部门）→ 部门树返回全量部门 + checkedKeys 空数组
        _, role_id, _ = creat_role()
        tree = role_api.get_dept_tree(role_id).json()
        # 断言成功契约与结构：code 200 + 部门树非空 + checkedKeys 为列表（未绑定部门时为空）
        assert tree["code"] == 200
        assert tree["depts"]
        assert isinstance(tree["checkedKeys"], list)

    @pytest.mark.xfail(reason="查询不存在角色的部门树本应报错却返回成功，"
                              "前端已经做出约束,一般情况下客户端OK")
    @allure.title("查询不存在角色的部门树")
    def test_dept_tree_nonexist(self, role_api):
        """验证已知缺陷：查询不存在角色的部门树返回成功（200 假成功），期望报错未实现。"""
        # 999：role_detail_services 返回空模型 → checkedKeys 空数组 → 200 假成功（缺陷）；
        # 期望返回 500 报错，断言不成立 → xfail
        resp = role_api.get_dept_tree(999)
        assert resp.json()["code"] == 500


# ===== 参考：部门ID对照（sys_dept.dept_id，完整 10 个） =====
# 100 集团总公司（顶级）
# ├── 101 深圳分公司：103 研发 / 104 市场 / 105 测试 / 106 财务 / 107 运维
# └── 102 长沙分公司：108 市场 / 109 财务
# 数据范围按 ancestors 祖先链判断：绑 100=全公司，绑 101=深圳分公司及子部门，绑 105=仅测试部门
# 说明：新增/编辑角色接口均忽略 deptIds（源码确认只写菜单关联），
#       部门绑定必须通过 dataScope 接口设置
# ===== 参考：数据权限（dataScope）数字含义 =====
# "1" 全部数据权限      "2" 自定数据权限（绑部门 deptIds）
# "3" 本部门数据权限    "4" 本部门及以下数据权限    "5" 仅本人数据权限
# ===================================================================


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("编辑角色数据权限接口")
class TestRoleDataScope:
    """编辑角色数据权限接口（PUT /system/role/dataScope），覆盖正向绑定、保护性校验与非法值参数校验。"""

    @allure.title("数据权限改为全部成功")
    def test_data_scope_all(self, role_api, creat_role):
        """验证正向链路：将数据权限改为"全部"（dataScope="1"）成功，无需绑定部门。"""
        # dataScope="1"（全部数据权限）：不绑部门
        _, role_id, _ = creat_role()
        resp = role_api.update_data_scope(role_id, "1")
        assert resp.json()["code"] == 200

    @allure.title("数据权限改为自定并绑定部门成功")
    def test_data_scope_custom(self, role_api, creat_role):
        """验证正向链路：数据权限改为"自定"并绑定部门成功（dataScope="2" + deptIds）。"""
        # dataScope="2"（自定数据权限）+ deptIds=[100,101]：绑定部门
        _, role_id, _ = creat_role()
        resp = role_api.update_data_scope(role_id, "2", [100, 101])
        assert resp.json()["code"] == 200

    @allure.title("修改数据权限后部门树核对")
    def test_data_scope_dept_tree_check(self, role_api, creat_role):
        """验证闭环：绑定部门后查询部门树，checkedKeys 应包含已绑定的部门（部门绑定唯一生效途径）。"""
        # 绑部门后查部门树：checkedKeys 应包含绑定的 100/101（部门绑定唯一生效途径）
        _, role_id, _ = creat_role()
        role_api.update_data_scope(role_id, "2", [100, 101])
        tree = role_api.get_dept_tree(role_id).json()
        assert tree["code"] == 200
        checked = tree["checkedKeys"]
        assert 100 in checked and 101 in checked

    @allure.title("修改不存在角色的数据权限")
    def test_data_scope_nonexist(self, role_api):
        """验证反向场景：修改不存在角色的数据权限被拦截返回 500。"""
        # 999：role_datascope_services 里 role_info.role_id 为 None → 「角色不存在」→ 500
        resp = role_api.update_data_scope(999, "1")
        assert resp.json()["code"] == 500

    @allure.title("无法修改超级管理员的数据权限")
    def test_data_scope_admin_rejected(self, role_api):
        """验证超级管理员保护：修改 roleId=1 的数据权限被拦截返回 500。"""
        # 超管保护 → 500
        resp = role_api.update_data_scope(1, "1")
        assert resp.json()["code"] == 500
        assert "不允许操作超级管理员" in resp.json()["msg"]

    @allure.title("数据权限传非法值")
    def test_data_scope_invalid(self, role_api):
        """验证反向场景：dataScope 传非法值时 Pydantic 参数校验失败，HTTP 层返回 422。"""
        # dataScope 是 Literal['1'..'5']：传 "9" → Pydantic 校验失败 → HTTP 422
        with pytest.raises(requests.exceptions.HTTPError) as e:
            role_api.update_data_scope(999, "9")
        assert e.value.response.status_code == 422
