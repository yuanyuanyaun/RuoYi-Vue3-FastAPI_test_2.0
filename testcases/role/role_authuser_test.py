"""角色模块-用户分配 测试用例。

覆盖接口：
    GET  /system/role/authUser/allocatedList    获取已分配用户列表接口：返回角色名下已分配的用户
    GET  /system/role/authUser/unallocatedList  获取未分配用户列表接口：返回角色名下未分配的用户
    PUT  /system/role/authUser/selectAll        分配用户接口：将用户批量分配/追加到角色
    PUT  /system/role/authUser/cancel           取消分配用户接口：移除角色与单个用户的关联
    PUT  /system/role/authUser/cancelAll        批量取消分配用户接口：批量移除角色与用户的关联

测试策略：
    正向：分配/取消/批量取消常规链路，以及已分配/未分配列表的名称、电话筛选。
    语义差异：selectAll 为追加+跳过语义（已存在的关联幂等跳过），与用户模块
    authRole 的替换语义不同，用例断言按追加语义设计。
    已知缺陷(xfail)：分配不存在用户返回成功并写入孤儿关联（sys_user_role 关联表，
    列表接口 JOIN 用户表查不到，需查库证明）；特殊值/空值触发 500 并泄漏 Pydantic
    校验细节；取消不存在的关联返回删除成功（200 假成功）。
    事务回滚：批量分配含非法值时整体回滚，已存在的分配不受影响。
    数据准备：自建角色由夹具 creat_role 创建并自动清理；角色 2 分配 niangao 为种子
    预置数据，仅用于查询类用例。
"""

import pytest
import allure
from utils.function import auth


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("获取已分配用户列表接口")
class TestAllocatedList:
    """已分配用户列表接口用例（GET /system/role/authUser/allocatedList），基于种子预置数据：角色2 已分配 niangao。"""

    @allure.title("默认查询已分配用户列表")
    def test_allocated_default(self, role_api):
        """验证默认查询已分配用户列表：种子预置的 niangao 应出现在列表中。"""
        # 种子预置：角色2 已分配 niangao（user_id=2）→ 默认列表应包含 niangao
        data = role_api.allocated_users(2).json()
        # 断言成功契约：code 200 + success 为 True
        assert data["code"] == 200
        assert data["success"] is True
        names = [r["userName"] for r in data["rows"]]
        # 断言预置关联可见：用户名列表中应包含 niangao
        assert "niangao" in names

    @allure.title("按电话查询已分配用户列表")
    def test_allocated_by_phone(self, role_api):
        """验证按电话筛选已分配用户列表：精确匹配 niangao 的电话返回该用户。"""
        # 筛选条件：phonenumber 精确匹配（种子 niangao 的电话）
        data = role_api.allocated_users(2, phonenumber="15666666666").json()
        assert data["code"] == 200
        assert data["success"] is True
        names = [r["userName"] for r in data["rows"]]
        assert "niangao" in names

    @allure.title("按名称查询已分配用户列表")
    def test_allocated_by_name(self, role_api):
        """验证按用户名筛选已分配用户列表：精确匹配 niangao 返回该用户。"""
        # 筛选条件：userName 精确匹配
        data = role_api.allocated_users(2, userName="niangao").json()
        assert data["code"] == 200
        assert data["success"] is True
        names = [r["userName"] for r in data["rows"]]
        assert "niangao" in names

    @allure.title("按错误名称查询已分配用户列表")
    def test_allocated_wrong_name(self, role_api):
        """验证反向场景：按不存在的名称筛选返回空列表，接口正常不报错。"""
        # 筛选条件查不到 → 返回空列表（total=0），接口正常
        data = role_api.allocated_users(2, userName="不存在的名字").json()
        assert data["code"] == 200
        assert data["total"] == 0

    @allure.title("查询不存在角色的已分配用户列表")
    def test_allocated_nonexist_role(self, role_api):
        """验证反向场景：查询不存在角色的已分配列表返回空列表（后端不校验角色存在性）。"""
        # 角色 999 不存在：后端不校验角色存在性，返回空列表（假成功无副作用）
        data = role_api.allocated_users(999).json()
        assert data["code"] == 200
        assert data["total"] == 0


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("获取未分配用户列表接口")
class TestUnallocatedList:
    """未分配用户列表接口用例（GET /system/role/authUser/unallocatedList），基于种子预置数据：角色2 未分配 admin。"""

    @allure.title("默认查询未分配用户列表")
    def test_unallocated_default(self, role_api):
        """验证默认查询未分配用户列表：已分配的 niangao 不应出现在未分配列表中。"""
        # 已分配的 niangao 不应出现在未分配列表里（两个列表按是否已关联互补）
        data = role_api.unallocated_users(2).json()
        assert data["code"] == 200
        names = [r["userName"] for r in data["rows"]]
        assert "niangao" not in names

    @allure.title("按电话查询未分配用户列表")
    def test_unallocated_by_phone(self, role_api):
        """验证按电话筛选未分配用户列表：精确匹配 admin 的电话返回该用户。"""
        # 按 admin 的电话筛出未分配用户（admin 未绑定角色2）
        data = role_api.unallocated_users(2, phonenumber="15888888888").json()
        assert data["code"] == 200
        names = [r["userName"] for r in data["rows"]]
        assert "admin" in names

    @allure.title("按名称查询未分配用户列表")
    def test_unallocated_by_name(self, role_api):
        """验证按用户名筛选未分配用户列表：精确匹配 admin 返回该用户。"""
        # 筛选条件：userName 精确匹配（admin 未绑定角色2，应出现在未分配列表）
        data = role_api.unallocated_users(2, userName="admin").json()
        assert data["code"] == 200
        names = [r["userName"] for r in data["rows"]]
        assert "admin" in names

    @allure.title("按错误名称查询未分配用户列表")
    def test_unallocated_wrong_name(self, role_api):
        """验证反向场景：按不存在的名称筛选返回空列表，接口正常不报错。"""
        # 筛选条件查不到 → 返回空列表（total=0），接口正常
        data = role_api.unallocated_users(2, userName="不存在的名字").json()
        assert data["code"] == 200
        assert data["total"] == 0

    @allure.description(
        "实测：查询不存在角色的未分配列表时，接口返回 200 且包含全部用户，"
        "因为'角色999名下没有任何已分配用户'所以所有人都是未分配，与已分配列表返回空互补；"
        "后端不校验角色存在性，前端只能从存在的角色进入"
    )
    @allure.title("查询不存在角色的未分配用户列表")
    def test_unallocated_nonexist_role(self, role_api):
        """验证反向场景：查询不存在角色的未分配列表返回全部用户（与已分配列表返回空互补）。"""
        # 角色 999 无任何已分配 → 全员未分配（与 allocated/999 返回空互补）
        data = role_api.unallocated_users(999).json()
        assert data["code"] == 200
        names = [r["userName"] for r in data["rows"]]
        assert "admin" in names


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("分配用户给角色接口")
class TestAssignUser:
    """分配用户给角色接口用例（PUT /system/role/authUser/selectAll，query 参数 roleId + userIds）。"""

    @allure.title("分配用户给角色成功")
    def test_assign_success(self, role_api, creat_role):
        """验证正向链路：将 admin 分配给自建角色成功，已分配列表应包含 admin。"""
        # 先经夹具创建自建角色（测试结束自动清理），再向其分配 admin（user_id=1）
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "1")
        # 断言分配成功契约：业务 code 200
        assert resp.json()["code"] == 200
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        # 回查已分配列表，确认 admin 已进入角色名下
        assert "admin" in names

    @pytest.mark.xfail(reason="实测：userIds 传特殊值 'abc' 时后端 Pydantic 校验拦截，但错误以 500 返回并泄漏校验细节")
    @allure.title("分配时用户ID为特殊值")
    def test_assign_special_user_ids(self, role_api, creat_role):
        """验证已知缺陷：userIds 传特殊值 'abc' 时校验拦截但以 500 返回并泄漏校验细节。"""
        # userIds="abc"：service 里 UserRoleModel(userId="abc") int 校验失败 → 500 泄漏；
        # 期望干净报错（"validation error" 不应出现）→ xfail
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "abc")
        assert resp.json()["code"] == 500
        assert "validation error" not in resp.json()["msg"]

    @allure.title("分配多个用户给角色成功")
    def test_assign_multi(self, role_api, creat_role):
        """验证正向链路：批量分配 "1,2" 成功，追加语义下两个用户都在已分配列表。"""
        # 批量分配 "1,2"：追加语义下两个用户都在已分配列表
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "1,2")
        assert resp.json()["code"] == 200
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "admin" in names and "niangao" in names

    @allure.description(
        "实测：重复分配已分配的用户时接口返回 200，后端遍历 userIds 时已存在的关联直接跳过（幂等），不会报错"
    )
    @allure.title("重复分配已分配的用户")
    def test_assign_repeat(self, role_api, creat_role):
        """验证幂等语义：重复分配已关联的用户时后端跳过已存在关联，不报错。"""
        # 先分配 niangao 再重复分配：已存在则跳过（幂等），不报 Duplicate
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        resp = role_api.assign_users(ID, "2")
        assert resp.json()["code"] == 200
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "niangao" in names

    @pytest.mark.xfail(reason="分配不存在的用户本应拒绝却成功分配，"
                              "前端已经做出约束,一般情况下客户端OK")
    @allure.title("分配不存在的用户")
    def test_assign_nonexist_user(self, role_api, mysql, creat_role):
        """验证已知缺陷：分配不存在的用户返回成功并写入孤儿关联（sys_user_role），需查库证明。"""
        # "999"：不校验用户存在性 → 假成功，孤儿关联 (ID,999) 插入 sys_user_role
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "999")
        # DB 校验：孤儿关联确实被插入（API 列表 JOIN 用户表查不到，必须查库证明），
        # 断言 count==0 失败 → xfail
        row = mysql["one"]("select count(*) as c from sys_user_role where user_id = 999")
        assert row["c"] == 0
        assert resp.json()["code"] == 500

    @pytest.mark.xfail(
        reason="批量分配含不存在的用户时后端未校验用户存在性，"
               "返回成功且存在和不存在的用户都被记录，"
               "前端已经做出约束,一般情况下客户端OK"
    )
    @allure.title("批量分配时含一个不存在的用户")
    def test_assign_batch_with_nonexist_user(self, role_api, creat_role, mysql):
        """验证已知缺陷：批量分配含不存在用户时未校验存在性，存在与不存在的用户均被记录。"""
        # "1,999"：存在的 admin 正常插入，不存在的 999 也被记录（无存在性校验）
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "1,999")
        assert resp.json()["code"] == 500
        # DB 校验：孤儿关联 (999,ID) 存在（count 应 >0，断言 0 失败 → xfail）
        row1 = mysql["one"]("select count(*) as c from sys_user_role where user_id = 999")
        assert row1["c"] == 0
        # DB 校验：admin（user_id=1）被分配到自建角色 ID（断言集合不同 → xfail）
        row2 = mysql["all"]("select role_id as r from sys_user_role where user_id = 1")
        assert {row["r"] for row in row2} != {1, ID}
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "admin" not in names

    @pytest.mark.xfail(
        reason="批量分配含特殊值时后端校验虽拦截，但错误以500返回并泄漏Pydantic细节，"
               "前端下拉框产生不了该值"
    )
    @allure.title("批量分配时含一个特殊值")
    def test_assign_batch_with_special(self, role_api, creat_role):
        """验证已知缺陷：批量分配含特殊值时校验拦截，但错误以 500 返回并泄漏 Pydantic 细节。"""
        # "1,abc"：UserRoleModel(userId="abc") 校验失败 → 500，整体回滚（1 未被插入）
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "1,abc")
        # 回滚验证（API）：niangao 仍在、admin 未被分配（"1" 被回滚）
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "niangao" in names and "admin" not in names
        assert resp.json()["code"] != 500
        assert "validation error" not in resp.json()["msg"]

    @pytest.mark.xfail(
        reason="批量分配含空值时与特殊值同款：校验拦截但错误以500返回并泄漏Pydantic细节，"
               "前端勾选产生不了空元素"
    )
    @allure.title("批量分配时含一个空值")
    def test_assign_batch_with_empty(self, role_api, creat_role):
        """验证已知缺陷：批量分配含空值时校验拦截，但错误以 500 返回并泄漏 Pydantic 细节。"""
        # "1,,2"：空元素 userId="" 校验失败 → 500，整体回滚（1、2 均未插入）
        _, ID, _ = creat_role()
        resp = role_api.assign_users(ID, "1,,2")
        assert "validation error" not in resp.json()["msg"]
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "niangao" in names and "admin" not in names
        assert resp.json()["code"] != 500

    @allure.title("分配时用户ID为空串")
    def test_assign_empty_user_ids(self, client, token, creat_role):
        """验证反向场景：userIds 为空串时后端分支判断不满足新增条件返回 500。"""
        # userIds="" 空串：add_user_role_services 分支判断 user_id 有值但 role_ids 为空
        # → 走到 else → 「不满足新增条件」→ 500
        _, ID, _ = creat_role()
        resp = client.put(
            "system/role/authUser/selectAll",
            headers=auth(token),
            params={"roleId": ID, "userIds": ""}
        )
        assert resp.json()["code"] == 500
        assert "不满足新增条件" in resp.json()["msg"]

    @allure.title("分配时缺用户ID")
    def test_assign_missing_user_ids(self, client, token, creat_role):
        """验证反向场景：请求缺少 userIds 参数时后端返回"不满足新增条件"。"""
        # 缺 userIds 参数（None）→ 「不满足新增条件」→ 500
        _, ID, _ = creat_role()
        resp = client.put(
            "system/role/authUser/selectAll",
            headers=auth(token),
            params={"roleId": ID}
        )
        assert resp.json()["code"] == 500
        assert "不满足新增条件" in resp.json()["msg"]

    @allure.title("分配时缺角色ID")
    def test_assign_missing_role_id(self, client, token):
        """验证反向场景：请求缺少 roleId 参数时后端返回"不满足新增条件"。"""
        # 缺 roleId 参数 → 「不满足新增条件」→ 500
        resp = client.put(
            "system/role/authUser/selectAll",
            headers=auth(token),
            params={"userIds": "1"}
        )
        assert resp.json()["code"] == 500
        assert "不满足新增条件" in resp.json()["msg"]


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("取消分配用户接口")
class TestCancelUser:
    """取消分配用户接口用例（PUT /system/role/authUser/cancel，body 参数 roleId + userId）。"""

    @allure.title("取消分配用户成功")
    def test_cancel_success(self, role_api, creat_role):
        """验证正向链路：先分配再取消 niangao，已分配列表不再包含该用户。"""
        # 先分配 niangao 再取消：已分配列表不再包含 niangao
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        resp = role_api.cancel_user(ID, 2)
        assert resp.json()["code"] == 200
        names = [r["userName"] for r in role_api.allocated_users(ID).json()["rows"]]
        assert "niangao" not in names

    @pytest.mark.xfail(reason="取消不存在的关联本应报错却返回删除成功，前端已经做出约束,一般情况下客户端OK")
    @allure.title("取消不存在的关联")
    def test_cancel_nonexist_relation(self, role_api, creat_role):
        """验证已知缺陷：取消不存在的关联返回"删除成功"（200 假成功），期望报错未实现。"""
        # 取消 (ID,999)：该关联不存在，DELETE 0 行也返回「删除成功」→ 200 假成功（缺陷）；
        # 期望返回 500 报错，断言不成立 → xfail
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        resp = role_api.cancel_user(ID, 999)
        assert resp.json()["code"] == 500

    @allure.title("取消时缺用户ID")
    def test_cancel_missing_user_id(self, client, token, creat_role, role_api):
        """验证反向场景：请求 body 缺少 userId 时后端返回"传入用户角色关联信息为空"。"""
        # body 缺 userId → delete_user_role_services 参数不满足 → 「传入用户角色关联信息为空」→ 500
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        resp = client.put(
            "system/role/authUser/cancel",
            headers=auth(token),
            json={"roleId": ID}
        )
        assert resp.json()["code"] == 500
        assert "传入用户角色关联信息为空" in resp.json()["msg"]


@pytest.mark.role
@allure.feature("角色模块")
@allure.story("批量取消分配用户接口")
class TestCancelAllUsers:
    """批量取消分配用户接口用例（PUT /system/role/authUser/cancelAll，query 参数 roleId + userIds）。"""

    @allure.title("批量取消分配成功")
    def test_cancel_all_success(self, role_api, creat_role):
        """验证正向链路：批量取消分配 admin+niangao 后，已分配列表为空。"""
        # 先分配 admin+niangao，再批量取消 → 已分配列表为空
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "1,2")
        resp = role_api.cancel_all_users(ID, "1,2")
        assert resp.json()["code"] == 200
        assert role_api.allocated_users(ID).json()["rows"] == []

    @pytest.mark.xfail(reason="批量取消含不存在的用户本应报错却返回删除成功，"
                              "前端已经做出约束,一般情况下客户端OK")
    @allure.title("批量取消含不存在的用户")
    def test_cancel_all_with_nonexist(self, role_api, creat_role, mysql):
        """验证已知缺陷：批量取消含不存在的用户时 999 静默无操作、2 正常取消（200 假成功）。"""
        # "999,2"：999 无关联静默无操作，2 被正常取消 → 200 假成功（缺陷）
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        # DB 校验：niangao(user_id=2) 原有角色2的关联存在（count==2 断言失败 → xfail）
        row = mysql["one"]("select count(*) as c from sys_user_role where user_id = 2")
        assert row["c"] == 2
        resp = role_api.cancel_all_users(ID, "999,2")
        assert resp.json()["code"] == 500

    @allure.title("批量取消时缺用户ID")
    def test_cancel_all_missing_user_ids(self, client, role_api, token, creat_role):
        """验证反向场景：请求缺少 userIds 参数时后端返回"传入用户角色关联信息为空"。"""
        # 缺 userIds 参数 → 「传入用户角色关联信息为空」→ 500
        _, ID, _ = creat_role()
        role_api.assign_users(ID, "2")
        resp = client.put(
            "system/role/authUser/cancelAll",
            headers=auth(token),
            params={"roleId": 2}
        )
        assert resp.json()["code"] == 500
        assert "传入用户角色关联信息为空" in resp.json()["msg"]
