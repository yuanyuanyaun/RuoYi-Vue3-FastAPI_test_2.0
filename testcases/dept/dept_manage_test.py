"""部门模块-管理 测试用例。

覆盖接口：
    PUT    /system/dept                编辑部门接口：按主键更新部门字段
    DELETE /system/dept/{dept_ids}     删除部门接口：按主键批量删除（支持逗号分隔）
    PUT    /system/dept/updateSort     保存部门排序接口：批量更新部门 orderNum

测试策略：
    编辑：覆盖不存在部门（无存在性保护，返回 500 泄漏 SQLAlchemy 内部错误）、
    上级选择自身、停用部门但含未停用子部门（部门特有规则）三类场景。
    删除：覆盖批量成功、含下级部门/含用户 601 拦截、批量含子部门事务回滚。
    排序：排序参数异常场景（数量不匹配/非数字/ID 非法）与菜单模块共用同一套解析校验逻辑，
    已在菜单模块覆盖，此处仅测成功场景。
    已知缺陷(xfail)：删除不存在的部门本应报错却返回删除成功（假成功）。
    数据依赖：用例通过工厂夹具 creat_dept 创建临时部门，用例结束后自动级联清理。
"""

import time
import pytest
import allure


# ============ 参考：种子部门数据（sys_dept.dept_id） ============
# 100 集团总公司（顶级）→ 101 深圳分公司（103 研发 / 104 市场 / 105 测试 / 106 财务 / 107 运维）
#                        → 102 长沙分公司（108 市场 / 109 财务）
# 数据范围按 ancestors 祖先链判定：绑定 100 为全公司，绑定 101 为深圳分公司及子部门，绑定 105 为仅测试部门
# 说明：新增角色接口会忽略 deptIds（源码确认 add 仅插入 menu、不插入 role_dept 关联表），
#       部门绑定须通过数据权限接口（/dataScope）设置
# ============ 参考：数据权限（dataScope）取值含义 ============
# "1" 全部数据权限     "2" 自定数据权限（绑定部门 deptIds）
# "3" 本部门数据权限   "4" 本部门及以下数据权限   "5" 仅本人数据权限
# ===================================================================

@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("编辑部门接口")
class TestDeptEdit:
    """编辑部门接口用例：覆盖不存在部门、上级选择自身、停用含未停用子部门三类编辑场景。"""

    @allure.description(
        "实测：编辑不存在的部门时，后端无存在性校验，直接执行 UPDATE 匹配 0 行，"
        "返回 500 并泄漏 SQLAlchemy 内部错误（expected to update 1 row(s); 0 were matched）"
    )
    @allure.title("编辑不存在的部门")
    def test_edit_nonexist(self, dept_api):
        """验证编辑不存在部门时的实际行为：后端无存在性校验，UPDATE 匹配 0 行返回 500 并泄漏 SQLAlchemy 内部错误。"""
        # 编辑请求体：deptId 传不存在的 999，其余字段为合法值；名称用时间戳保证唯一避免干扰
        resp = dept_api.update(
            deptId=999,
            deptName=f"none_{int(time.time() * 1000)}",
            parentId=100,
            orderNum=1,
            status="0"
        )
        # 断言缺陷行为契约：code 500 + 失败标识（缺陷细节见类上方 allure.description 记录）
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False

    @allure.title("编辑时上级部门选择自己")
    def test_edit_parent_is_self(self, dept_api, creat_dept):
        """业务规则验证：编辑时上级部门选择自身构成环引用，被拦截并提示「上级部门不能是自己」。"""
        # 先通过工厂夹具创建临时部门拿到 dept_id，再编辑使 parentId 指向自身
        _, dept_id, _ = creat_dept()
        resp = dept_api.update(
            deptId=dept_id,
            deptName=f"self_{int(time.time() * 1000)}",
            parentId=dept_id,
            orderNum=1,
            status="0"
        )
        # 断言拦截契约：code 500 + 失败标识 + 提示语「上级部门不能是自己」
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "上级部门不能是自己" in resp.json()["msg"]

    @allure.title("编辑停用部门但含未停用的子部门")
    def test_edit_disable_with_children(self, dept_api, creat_dept):
        """业务规则验证：停用部门时若其下存在未停用子部门则被拦截，随后恢复父部门启用状态以支持级联清理。"""
        # 第一步创建父部门与子部门两级数据（子部门 parentId 指向父部门 dept_id）
        _, parent_id, parent_name = creat_dept()
        _, child_id, _ = creat_dept(parentId=parent_id)
        # 第二步将父部门编辑为停用（status="1"），期望被部门特有规则拦截：
        # code 500 + 提示语「该部门包含未停用的子部门」
        resp = dept_api.update(
            deptId=parent_id,
            deptName=parent_name,
            parentId=100,
            orderNum=1,
            status="1"
        )
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False
        assert "该部门包含未停用的子部门" in resp.json()["msg"]
        # 清理策略：将父部门恢复为启用（status="0"），保证工厂夹具的级联清理可正常删除两级部门，
        # 避免停用状态使清理被同一规则拦截而残留脏数据
        dept_api.update(
            deptId=parent_id,
            deptName=parent_name,
            parentId=100,
            orderNum=1,
            status="0"
        )


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("删除部门接口")
class TestDeptDelete:
    """删除部门接口用例：覆盖批量成功、存在性缺陷、下级/用户占用拦截与事务回滚。"""

    @allure.title("批量删除部门成功")
    def test_delete_batch(self, dept_api, creat_dept):
        """验证批量删除两个部门成功，且删除后按名称复查均不可见。"""
        # 创建两个独立临时部门（名称由工厂夹具保证唯一），批量删除传逗号分隔的 dept_id 串
        _, did1, name1 = creat_dept()
        _, did2, name2 = creat_dept()
        resp = dept_api.delete(f"{did1},{did2}")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] is True
        # API 复查：分别按名称筛选列表，确认两条数据均已不可见（软删除对查询透明）
        assert not [r for r in dept_api.list(deptName=name1).json()["data"] if r["deptName"] == name1]
        assert not [r for r in dept_api.list(deptName=name2).json()["data"] if r["deptName"] == name2]

    @pytest.mark.xfail(reason="删除不存在的部门本应报错却返回删除成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("删除不存在的部门")
    def test_delete_nonexist(self, dept_api):
        """已知缺陷验证：删除不存在的部门本应报错，实际无存在性校验返回删除成功（假成功），标记 xfail。"""
        # 缺陷表现：删除 999 时删除 0 行仍返回「删除成功」200；
        # 用例断言正常行为契约（code 500），当前实际失败故标记 xfail
        resp = dept_api.delete(999)
        assert resp.json()["code"] == 500

    @allure.title("删除有子部门的部门")
    def test_delete_has_child(self, dept_api):
        """业务规则验证：删除含下级部门的部门被拦截，返回 601 并提示「存在下级部门,不允许删除」。"""
        # 使用种子部门 100（集团总公司，下挂 101/102 等子部门）作为目标，
        # 触发下级部门占用检查（按 ancestors 祖先链统计子部门数量）
        resp = dept_api.delete(100)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
        assert "存在下级部门,不允许删除" in resp.json()["msg"]

    @allure.title("删除有用户的部门")
    def test_delete_has_user(self, dept_api):
        """业务规则验证：删除含用户的部门被拦截，返回 601 并提示「部门存在用户,不允许删除」。"""
        # 使用种子部门 103（研发部门，绑定有用户）作为目标，触发用户占用检查
        resp = dept_api.delete(103)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] is False
        assert "部门存在用户,不允许删除" in resp.json()["msg"]

    @allure.title("批量删除含子部门的部门（事务回滚）")
    def test_delete_batch_with_children(self, dept_api, creat_dept):
        """事务回滚验证：批量删除串中同时含占用部门与临时部门时，整个事务回滚，临时部门不被删除。"""
        # 构造 "100,{did}" 批量串：100 含下级部门必然触发校验异常，did 为新建临时部门
        _, did, name = creat_dept()
        resp = dept_api.delete(f"100,{did}")
        assert resp.json()["code"] == 601
        # 事务回滚验证：临时部门按名称复查仍存在于列表中，
        # 证明删除事务整体回滚（全有或全无），未产生部分删除的中间态
        assert [r for r in dept_api.list(deptName=name).json()["data"] if r["deptName"] == name]


@pytest.mark.dept
@allure.feature("部门模块")
@allure.story("保存部门排序接口")
@allure.description(
    "排序参数异常场景（数量不匹配/非数字/ID小于等于0/重复ID）与菜单模块的排序接口"
    "为同一套解析校验逻辑（parse_dept_sort_items 与 parse_menu_sort_items 同构），"
    "已在菜单模块覆盖，此处仅测成功场景。"
)
class TestDeptSort:
    """保存部门排序用例：仅覆盖成功场景（参数异常场景已在菜单模块覆盖）。"""

    @allure.title("保存部门排序成功")
    def test_sort_success(self, dept_api, creat_dept):
        """验证保存部门排序成功：两个部门的 orderNum 按传入排序串一一对应更新。"""
        # 创建两个临时部门后，调用 update_sort 传入有序 id 串与新的排序串 "2,1"，
        # 期望 did1.orderNum=2、did2.orderNum=1（排序串按位置对应各 dept_id）
        _, did1, name1 = creat_dept()
        _, did2, name2 = creat_dept()
        resp = dept_api.update_sort(f"{did1},{did2}", "2,1")
        assert resp.json()["code"] == 200
        assert resp.json()["msg"] == "保存成功"
        # 复查方式：按名称筛选列表后按 dept_id 定位对应行，核对各自的 orderNum
        rows1 = dept_api.list(deptName=name1).json()["data"]
        rows2 = dept_api.list(deptName=name2).json()["data"]
        assert [r for r in rows1 if r["deptId"] == did1][0]["orderNum"] == 2
        assert [r for r in rows2 if r["deptId"] == did2][0]["orderNum"] == 1
