"""用户模块-角色分配 测试用例。

覆盖接口：
    GET /system/user/authRole/{id}   获取用户已分配角色列表接口：返回用户信息与已分配角色列表
    PUT /system/user/authRole        给用户分配角色接口：按角色 ID 列表分配/清空角色

测试策略：
    正向 / 反向 / 边界 / 已知缺陷(xfail) 场景全覆盖：
    - 替换语义：authRole 先清空再插入（roleIds="" 表示清空角色），与角色模块
      selectAll 的追加+跳过语义不同；
    - 已知缺陷(xfail)：给不存在的用户/角色分配 → 200 假成功 + sys_user_role 孤儿关联，
      孤儿关联 JOIN 用户表查询不到，必须依赖数据库校验证明；
    - 边界值：特殊值/空值 → Pydantic 拦截但 500 泄漏校验细节；重复角色 ID →
      Duplicate entry 500；
    - 回滚验证：批量分配含非法元素时整体回滚，用户原有角色保持不变。
    清理策略：孤儿关联由 role_api.cancel_user 清理；自建用户删除时其关联被级联清理。
"""

import pytest
import allure
import requests
import time

# 模块级毫秒时间戳：配合 creat_user 生成唯一 userName（类中所有用例共用，避免重名冲突）
name = int(time.time() * 1000)


@pytest.mark.user
@allure.feature("用户模块")
class TestUserAuthRole:
    """用户角色分配接口用例：覆盖已分配角色查询、替换分配、清空角色，以及不存在用户/角色、特殊值、重复 ID 等已知缺陷（xfail）场景；缺陷断言均辅以数据库校验作为铁证。"""

    @allure.story("获取用户已分配角色列表接口")
    @allure.title("成功获取指定用户的已分配角色列表")
    def test_get_allocated_roles(self, creat_user, user_api):
        """正向场景：自建带角色 2 的用户后查询已分配角色列表，断言返回用户信息且角色列表非空。"""
        # 自建用户并指定角色 roleIds=[2]，作为已分配角色查询的数据前提
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.allocated_roles(ID)
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["user"]["userName"] == str(name)
        assert resp.json()["roles"]

    @pytest.mark.xfail(
        reason="已知缺陷：查询不存在用户时后端未判空，UserInfoModel(**None) 崩溃返回 500 并泄漏 Python 内部错误，"
               "正确应返回友好业务提示且不泄漏内部细节；前端已约束，客户端无法触发"
    )
    @allure.story("获取用户已分配角色列表接口")
    @allure.title("获取不存在用户的已分配角色列表")
    def test_get_allocated_roles_nonexist_user(self, user_api):
        """正确契约：不应以框架崩溃方式返回，且不得泄漏内部错误细节。"""
        resp = user_api.allocated_roles(9999)
        data = resp.json()
        # 核心断言：不得泄漏内部实现细节（当前实际泄漏 NoneType/类名 → 断言失败 → xfail）
        assert "NoneType" not in data["msg"]
        assert "must be a mapping" not in data["msg"]
        assert "UserInfoModel" not in data["msg"]
        # 业务层面：查询不存在用户应返回失败标识（可修复为 500/601 + 友好 msg）
        assert data["success"] is False
        assert data["code"] == 500

    @allure.story("给用户分配角色接口")
    @allure.title("给指定用户分配角色")
    def test_assign_role_success(self, user_api, creat_user):
        """正向场景：替换语义分配——将用户角色从 [2] 替换为 [1]，回查确认仅剩角色 1。"""
        # 替换语义：assign_roles 先清空再插入，把该用户原有角色 [2] 整体替换为 [1]
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        data = user_api.allocated_roles(ID).json()
        assert data["user"]["role"][0]["roleId"] == 1

    @allure.story("给用户分配角色接口")
    @allure.title("给用户分配空角色列表（清空角色），数据库已经完成校验")
    def test_assign_empty_role_ids(self, user_api, creat_user, mysql):
        """正向场景：roleIds="" 触发替换语义的清空分支（只清空不插入），回查角色为空且 DB 关联清空。"""
        # roleIds="" 走替换语义的分支 2：只清空不插入，即清空该用户全部角色
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        data = user_api.allocated_roles(ID).json()
        assert data["user"]["role"] == []
        # DB 校验：sys_user_role 中该用户的关联记录数应为 0，证明清空真实落库
        row = mysql["one"]("select count(*) as c from sys_user_role where user_id = %s", (ID,))
        assert row["c"] == 0

    @pytest.mark.xfail(reason="给根本不存在的用户分配角色时本应拒绝却成功分配，"
                              "数据库已完成校验，发现不应该存在的数据，取消后又消失"
                              "前端已经做出约束，不可能,一般情况下客户端OK"
                       )
    @allure.story("给用户分配角色接口")
    @allure.title("给不存在的用户分配角色时应被拒绝")
    def test_assign_nonexist_user(self, user_api, role_api, mysql):
        """已知缺陷（xfail）：给不存在的用户（999）分配角色本应拒绝，实际 200 假成功并产生孤儿关联 (999,2)。"""
        try:
            # 缺陷复现：后端不校验用户存在性，分配接口返回 200 假成功，并插入孤儿关联 (999,2)
            resp = user_api.assign_roles(999, "2")
            # DB 铁证：孤儿关联 JOIN 用户表查询不到，只能直接查 sys_user_role 证明其真实插入
            row = mysql["one"]("select role_id as r from sys_user_role where user_id = 999")
            assert row["r"] == 2
            assert resp.json()["code"] != 200
            assert resp.json()["success"] is False
        finally:
            # 清理孤儿：无论断言结果如何，均调用 role_api.cancel_user 删除孤儿关联 (999,2) 并验证清空
            role_api.cancel_user(2, 999)
            none = mysql["one"]("select count(*)as c from sys_user_role where user_id = 999")
            assert none["c"] == 0

    @pytest.mark.xfail(reason="给用户分配不存在的角色本应拒绝却成功分配，"
                              "前端已经做出约束,一般情况下客户端OK"
                       )
    @allure.story("给用户分配角色接口")
    @allure.title("给用户分配不存在的角色时应该被拒绝")
    def test_assign_nonexist_role(self, user_api, creat_user, mysql):
        """已知缺陷（xfail）：分配不存在的角色（999）本应拒绝，实际假成功并产生孤儿关联 (ID,999)。"""
        # 缺陷复现：后端不校验角色存在性，role_id=999 的关联被真实插入（假成功）
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "999")
        # DB 铁证：直接查 sys_user_role 确认孤儿关联存在；自建用户删除时该关联会被级联清理
        row = mysql["one"]("select role_id as r from sys_user_role where user_id = %s", (ID,))
        assert row["r"] == 999
        assert resp.json()["code"] != 200
        assert resp.json()["success"] is False

    @allure.story("给用户分配角色接口")
    @allure.title("给用户分配角色时用户ID为特殊值")
    def test_assign_role_invalid_user_id(self, user_api):
        """边界场景：userId 传非数字字符串 → FastAPI 参数层 int 解析失败 → 返回干净的 HTTP 422。"""
        # userId 为 query 参数 int 类型："abc" 在 FastAPI 参数解析层即被拦截，返回干净的 HTTP 422
        with pytest.raises(requests.exceptions.HTTPError) as e:
            user_api.assign_roles("abc", "1")
        assert e.value.response.status_code == 422

    @allure.story("给用户分配角色接口")
    @allure.title("给用户分配角色时角色ID为特殊值")
    def test_assign_role_invalid_role_ids(self, user_api, creat_user):
        """边界场景：roleIds 传非数字字符串 → 参数层放行，service 构造 UserRoleModel(roleId="abc") 触发 Pydantic 校验失败 → 500 泄漏校验细节。"""
        # roleIds 为 str 类型可通过参数层校验，进入 service 后构造 UserRoleModel(roleId="abc")
        # Pydantic int 校验失败 → 500 并泄漏校验细节，作为边界行为记录
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "abc")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] is False

    @allure.story("给用户分配角色接口")
    @allure.title("给指定角色分配多个角色")
    def test_assign_multi_roles(self, user_api, creat_user):
        """正向场景：批量分配 [1,2] → 替换语义下最终两个角色均存在且数量为 2。"""
        # 批量分配 "1,2"：替换语义先清空原角色 [2] 再插入 1、2，最终角色集合应为 {1,2}
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1,2")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        data = user_api.allocated_roles(ID).json()
        role_ids = [r["roleId"] for r in data["user"]["role"]]
        assert 1 in role_ids and 2 in role_ids and len(role_ids) == 2

    @pytest.mark.xfail(
        reason="批量分配含不存在的角色时后端未校验角色存在性，"
               "返回成功且不存在的角色也被记录，"
               "前端已经做出约束,一般情况下客户端OK"
    )
    @allure.story("给用户分配角色接口")
    @allure.title("批量分配时含一个不存在的角色")
    def test_assign_batch_with_nonexist_role(self, user_api, creat_user, mysql):
        """已知缺陷（xfail）：批量分配含不存在的角色（1,999）→ 后端不校验角色存在性，999 也被记录，孤儿关联落库。"""
        # 缺陷复现：已存在的角色 1 正常插入，不存在的角色 999 同样被记录（无存在性校验）
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1,999")
        assert resp.json()["code"] != 200
        # DB 铁证：role_id=999 的孤儿关联真实存在，直接查 sys_user_role 证明
        row = mysql["one"]("select role_id as r from sys_user_role where user_id = %s", (ID,))
        assert row["r"] == 999

    @pytest.mark.xfail(
        reason="批量分配含特殊值时后端未做类型校验，"
               "炸到数据库返回500并泄漏SQL，"
               "前端下拉框产生不了该值,所以客户端一般情况下都OK"
    )
    @allure.story("给用户分配角色接口")
    @allure.title("批量分配时含一个特殊值")
    def test_assign_batch_with_special(self, user_api, creat_user):
        """已知缺陷（xfail）：批量分配含特殊值（1,abc）→ 模型校验失败返回 500 并泄漏 SQL，整体回滚后用户原有角色 2 保持不变。"""
        # 缺陷复现：UserRoleModel(roleId="abc") 校验失败 → 500 泄漏 SQL
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1,abc")
        # 回滚验证：批量插入整体回滚，用户原有角色 2 应保持不变（API 层面回查确认）
        data = user_api.allocated_roles(ID).json()
        role_ids = [r["roleId"] for r in data["user"]["role"]]
        assert 2 in role_ids
        assert resp.json()["code"] != 500

    @pytest.mark.xfail(
        reason="批量分配含空值时后端虽被Pydantic拦截，"
               "但错误以500返回并泄漏校验细节，前端勾选产生不了空元素"
    )
    @allure.story("给用户分配角色接口")
    @allure.title("批量分配时含空值，数据库回滚已校验")
    def test_assign_batch_with_empty(self, user_api, creat_user, mysql):
        """已知缺陷（xfail）：批量分配含空值（1,,2）→ Pydantic 拦截但错误以 500 返回并泄漏校验细节；DB 校验整体回滚，仅剩原角色 2 一条。"""
        # 缺陷复现：空元素触发 Pydantic 校验失败 → 500 并泄漏校验细节
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1,,2")
        role_ids = [r["roleId"] for r in user_api.allocated_roles(ID).json()["user"]["role"]]
        # DB 回滚铁证：整体回滚后 sys_user_role 仅剩原有角色 2 且只有 1 条（"1" 未被插入）
        row = mysql["one"]("select role_id,count(*) as c from sys_user_role where user_id = %s", (ID,))
        assert row["role_id"] == 2 and row["c"] == 1
        assert 2 in role_ids
        assert resp.json()["code"] != 500

    @pytest.mark.xfail(
        reason="批量分配相同角色ID时后端未去重（已经数据库校验未发现应有数据），"
               "插入重复主键返回500并泄漏SQL，"
               "前端多选组件会去重故前端无法触发，"
    )
    @allure.story("给用户分配角色接口")
    @allure.title("批量分配相同的角色ID")
    def test_assign_duplicate_role_ids(self, user_api, creat_user, mysql):
        """已知缺陷（xfail）：批量分配相同角色 ID（1,1）→ 后端未去重，重复主键插入返回 500 并泄漏 SQL；期望 2 条关联实际回滚。"""
        # 缺陷复现：后端未对角色 ID 去重，重复主键插入触发 Duplicate entry → 500 回滚
        _, ID, _ = creat_user(roleIds=[2], userName=str(name))
        resp = user_api.assign_roles(ID, "1,1")
        # DB 校验：期望出现 2 条关联记录（缺陷断言，实际回滚后不满足 → xfail）
        row = mysql["one"]("select count(*) as c from sys_user_role where user_id = %s", (ID,))
        assert row["c"] == 2
        assert resp.json()["code"] == 200
