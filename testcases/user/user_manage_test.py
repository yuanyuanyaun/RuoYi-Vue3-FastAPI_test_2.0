"""用户模块-管理 测试用例。

覆盖接口：
    PUT /system/user                     编辑用户接口：编辑用户信息并替换岗位关联
    DELETE /system/user/{userId}         删除用户接口：软删除并清空关联表
    PUT /system/user/resetPwd            重置用户密码接口：重置密码使新密码生效
    PUT /system/user/changeStatus        修改用户状态接口：启用/停用用户
    GET /system/user/profile             获取用户个人信息接口：返回当前登录用户信息
    PUT /system/user/profile/updatePwd   修改用户个人密码接口：校验旧密码后更新密码

测试策略：
    反向场景：编辑/重置/改状态不存在的用户 → 500（user_detail_services 用户不存在链路）。
    超管保护：重置/改状态 admin（userId=1）→ 500「不允许操作超级管理员」；
    删除 admin 自己 → 601「当前登录用户不能删除」（controller 前置拦截）。
    已知缺陷(xfail)：删除不存在的用户 → 200 假成功（后端无存在性校验，软删 0 行仍返回成功）。
    修改密码闭环：旧密码改新密码 → 新密码登录 → 用新 token 改回，保持种子密码不变。
    个人信息：修改昵称验证后恢复原值，避免污染 admin 种子数据。
"""

import pytest
import allure
from testcases.conftest import login_api


# 统一的不存在用户 ID（999）：本模块所有反向场景均以此 ID 触发用户不存在链路
invalid_id = 999


@pytest.mark.user
@allure.feature("用户模块")
class TestUserManage:
    """管理接口反向场景用例：覆盖编辑/删除/重置密码/改状态四个接口对不存在用户与超级管理员的防护行为，重点验证存在性校验与超管保护业务规则。"""

    @allure.story("编辑用户接口")
    @allure.title("编辑不存在的用户")
    def test_edit_nonexist_user(self, user_api):
        """反向场景：编辑不存在的用户 → user_detail_services 返回空 → service 抛「用户不存在」→ 500。"""
        # 编辑链路先经 user_detail_services 查用户：999 不存在返回空，service 抛「用户不存在」异常返回 500
        resp = user_api.update(
            userId=invalid_id,
            userName="none"
        )
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False

    @pytest.mark.xfail(reason="成功删除不存在的用户，但前端已做出约束，只能在存在的用户上使用删除功能")
    @allure.story("删除用户接口")
    @allure.title("删除不存在的用户")
    def test_delete_nonexist_user(self, user_api):
        """已知缺陷（xfail）：删除不存在的用户 → 200 假成功（后端无存在性校验，软删 0 行仍返回「删除成功」）。"""
        # 缺陷复现：后端删除不做存在性校验，软删 0 行也返回「删除成功」→ 200 假成功（期望 500）
        resp = user_api.delete(invalid_id)
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False

    @allure.story("删除用户接口")
    @allure.title("无法删除超级管理员")
    def test_delete_admin_rejected(self, user_api):
        """超管保护：删除列表包含当前登录用户（admin 删自己 userId=1）→ controller 前置拦截返回 601。"""
        # controller 前置拦截：删除用户列表包含当前登录用户时拒绝删除，返回 601「当前登录用户不能删除」
        resp = user_api.delete(1)
        assert resp.json()["code"] == 601
        assert resp.json()["success"] == False
        assert "当前登录用户不能删除" in resp.json()["msg"]

    @allure.story("重置用户密码接口")
    @allure.title("无法重置不存在的用户的密码")
    def test_reset_pwd_nonexist_user(self, user_api):
        """反向场景：重置不存在用户的密码 → 复用编辑链路 user_detail_services → 用户不存在 → 500。"""
        # 重置密码复用编辑链路：先查用户详情，999 不存在 → service 抛异常返回 500
        resp = user_api.reset_pwd(invalid_id, "NewPwd@123456")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False

    @allure.story("重置用户密码接口")
    @allure.title("无法重置超级管理员的密码")
    def test_reset_pwd_admin_rejected(self, user_api):
        """超管保护：重置 admin（userId=1）密码 → check_user_allowed_services 拦截 → 500「不允许操作超级管理员」。"""
        # 超管保护规则：check_user_allowed_services 识别 userId=1 为超级管理员，拒绝重置并返回 500
        resp = user_api.reset_pwd(1, "NewPwd@123456")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False
        assert "不允许操作超级管理员" in resp.json()["msg"]

    @allure.story("修改用户状态接口")
    @allure.title("无法修改不存在的用户的状态")
    def test_change_status_nonexist_user(self, user_api):
        """反向场景：修改不存在用户的状态 → 复用用户不存在链路 → 500。"""
        # 改状态同样先查用户：999 不存在 → 用户不存在链路返回 500
        resp = user_api.change_status(invalid_id, "1")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False

    @allure.story("修改用户状态接口")
    @allure.title("无法修改超级管理员的状态")
    def test_change_status_admin_rejected(self, user_api):
        """超管保护：修改 admin（userId=1）状态 → check_user_allowed_services 拦截 → 500「不允许操作超级管理员」。"""
        # 超管保护规则：改状态对超级管理员同样拦截，返回 500 并提示「不允许操作超级管理员」
        resp = user_api.change_status(1, "1")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False
        assert "不允许操作超级管理员" in resp.json()["msg"]


@pytest.mark.user
@allure.feature("用户模块")
class TestUserProfile:
    """个人信息与个人密码用例：个人信息修改后恢复原值、个人密码修改后改回，保证 admin 种子数据不被污染；改密过程验证新密码可登录、旧 token 失效等闭环行为。"""

    @allure.story("获取用户个人信息接口")
    @allure.title("查看用户个人信息成功")
    def test_get_profile_success(self, user_api):
        """正向场景：获取当前登录用户（admin）个人信息，断言 userId=1 且 userName=admin。"""
        # 当前登录会话为 admin（userId=1），个人信息接口返回其完整信息
        resp = user_api.profile()
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["data"]["userId"] == 1
        assert resp.json()["data"]["userName"] == "admin"

    @allure.story("修改用户个人信息接口")
    @allure.title("修改用户个人信息成功")
    def test_update_profile_success(self, user_api):
        """正向场景：修改昵称为临时值 → 查询验证生效 → 恢复原昵称「超级管理员」，避免污染 admin 种子数据。"""
        # 第一步：改昵称为临时值，接口返回成功即验证修改接口可用
        resp = user_api.update_profile(nickName="临时昵称")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

        # 回查个人信息：确认昵称已变更为临时值（修改真实生效）
        query = user_api.profile()
        assert query.json()["code"] == 200
        assert query.json()["success"] == True
        assert query.json()["data"]["nickName"] == "临时昵称"

        # 恢复原昵称：避免修改影响其他用例对 admin 昵称的断言
        update_resp = user_api.update_profile(nickName="超级管理员")
        assert update_resp.json()["code"] == 200
        assert update_resp.json()["success"] == True

        # 恢复后回查确认：昵称已还原为种子值「超级管理员」
        query_resp = user_api.profile()
        assert query_resp.json()["code"] == 200
        assert query_resp.json()["success"] == True
        assert query_resp.json()["data"]["nickName"] == "超级管理员"

    @allure.story("修改用户密码接口")
    @allure.title("修改用户个人密码成功")
    def test_update_pwd_success(self, user_api, login_api):
        """修改密码闭环：旧密码改新密码 → 新密码登录成功 → 用新密码 token 改回旧密码 → 临时会话退出，保持种子密码不变。"""
        # 第一步：用旧密码 admin123 修改为新密码，接口成功即证明旧密码校验通过
        resp = user_api.update_pwd("admin123", "NewPwd@123456")
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

        # 闭环验证：新密码登录成功，证明密码修改真实生效；同时换取新 token 用于后续改回操作
        login_resp = login_api.login(
            username="admin",
            password="NewPwd@123456"
        )
        assert login_resp.json()["code"] == 200
        assert login_resp.json()["success"] == True
        login_token = login_resp.json()["token"]

        # 改密后旧 token 已失效：需用新密码登录换取的新 token 将密码改回旧值，保持种子密码 admin123 不变
        resp_ag = user_api.update_pwd("NewPwd@123456", "admin123")
        assert resp_ag.json()["code"] == 200
        assert resp_ag.json()["success"] == True

        # 临时会话用毕即退出，避免遗留登录态
        logout_resp = login_api.logout(login_token)
        assert logout_resp.json()["code"] == 200
        assert logout_resp.json()["success"] == True

    @allure.story("修改用户密码接口")
    @allure.title("旧密码错误时修改密码失败")
    def test_update_pwd_wrong_old_password(self, user_api):
        """反向场景：旧密码错误 → PwdUtil.verify_password 校验失败 → service 抛「旧密码错误」→ 500。"""
        # 旧密码校验失败：verify_password 不通过，service 抛「旧密码错误」异常返回 500
        resp = user_api.update_pwd("wrong_old", "NewPwd@123456")
        assert resp.json()["code"] == 500
        assert resp.json()["success"] == False
        assert "旧密码错误" in resp.json()["msg"]

    @allure.story("获取用户岗位和角色列表接口")
    @allure.title("获取用户个人的岗位和角色列表成功")
    def test_get_profile_posts_roles(self, user_api):
        """正向场景：detail() 不传 id 返回岗位+角色下拉列表（编辑页数据来源），断言种子岗位 1 的 postCode 为 ceo。"""
        # detail() 不传 user_id 走特殊分支：返回岗位+角色下拉列表，断言种子岗位 postCode=ceo
        resp = user_api.detail()
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["posts"][0]["postCode"] == "ceo"
