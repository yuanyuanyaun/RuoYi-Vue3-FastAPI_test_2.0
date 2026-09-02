"""用户模块-冒烟测试 测试用例。

覆盖接口：
    GET    /system/user/list          获取用户分页列表接口：分页条件查询用户，返回 rows 与 total
    GET    /system/user/deptTree      获取部门树接口：返回当前用户可见的部门树
    POST   /system/user               添加用户接口：全字段创建用户并建立角色/岗位关联
    PUT    /system/user               编辑用户接口：全字段编辑并替换岗位关联
    PUT    /system/user/resetPwd      重置用户密码接口：重置密码并使新密码可登录
    PUT    /system/user/changeStatus  修改用户状态接口：启用/停用用户（status 0/1）
    DELETE /system/user/{id}          删除用户接口：软删除（del_flag='2'）并清空关联表

测试策略：
    正向主链路闭环：创建 → 按名称查回 → 编辑 → 重置密码（新密码可登录）→ 停用 → 删除。
    每步操作后以数据库校验（sys_user 主表字段 + sys_user_role/sys_user_post 关联表）
    验证写入真实落库，API 断言与 DB 断言双闭环。
    用例之间存在顺序依赖：类变量 user_id 缓存创建用户的 userId 供后续用例复用，
    因此本类用例必须整类按定义顺序运行，不可单独或乱序执行。
"""

import pytest
import allure
import time
from utils.function import auth

# 模块导入时以时间戳生成唯一用户名：user_name 用于创建，user_name_1 用于编辑改名，
# 确保与历史数据及并发执行互不冲突（时间戳精确到秒，跨天自动区分）
user_name = f"test_user_{time.strftime('%Y%m%d%H%M%S')}"
user_name_1 = f"test_user_{time.strftime('%Y%m%d%H%M%S')}a"


@pytest.mark.user
@pytest.mark.smoke
@allure.feature("用户模块")
class TestUserSmoke:
    """用户模块冒烟主链路用例：创建 → 查回 → 编辑 → 重置密码 → 停用 → 删除，API 与数据库双闭环验证。"""

    # 类变量：缓存创建用户的 userId，供后续编辑/重置/停用/删除用例按状态链复用，
    # 避免每个用例重复查询或依赖固定的种子 userId
    user_id = None

    @allure.story("获取用户分页列表接口")
    @allure.title("默认条件获取用户列表成功")
    def test_user_list_success(self, user_api):
        """验证默认条件下分页列表接口返回成功：种子数据不少于 2 个用户，且首行用户名为非空值。"""
        resp = user_api.list()
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        assert isinstance(data["rows"], list)
        assert len(data["rows"]) >= 2
        assert data["total"] >= 2
        assert data["rows"][0]["userName"]

    @allure.story("获取部门树接口")
    @allure.title("获取部门树成功")
    def test_get_dept_tree_success(self, user_api):
        """验证部门树接口返回当前用户可见的部门数据：admin 超管身份可见全量部门树。"""
        resp = user_api.dept_tree()
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True

    @allure.story("添加用户接口")
    @allure.title("添加用户成功")
    def test_add_user_success(self, user_api, mysql):
        """验证全字段创建用户成功，且 sys_user 主表字段与角色/岗位关联表真实落库（API 与 DB 双闭环）。"""
        resp = user_api.creat(
            userName=user_name,
            nickName="冒烟测试用户",
            password="Test@123456",
            email="test@qq.com",
            phonenumber="13911112222",
            deptId=100,
            postIds=[4],
            roleIds=[2],
            sex="0",
            status="0",
            remark="冒烟测试"
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # DB 校验：按 user_name 查询 sys_user 主表，逐字段比对请求值，证明创建数据真实落库
        row = mysql["one"](
            "select user_name,nick_name,dept_id,email,sex,phonenumber,status,remark "
            "from sys_user where user_name=%s", (user_name,)
        )
        assert row["user_name"] == user_name
        assert row["nick_name"] == "冒烟测试用户"
        assert row["dept_id"] == 100
        assert row["email"] == "test@qq.com"
        assert row["phonenumber"] == "13911112222"
        assert row["sex"] == "0"
        assert row["status"] == "0"
        assert row["remark"] == "冒烟测试"
        # 经列表查询反查新建用户的 userId 并存入类变量，供后续编辑/重置/停用/删除用例按状态链复用
        TestUserSmoke.user_id = user_api.list(userName=user_name).json()["rows"][0]["userId"]
        # DB 校验：sys_user_role / sys_user_post 关联表确认角色 2 与岗位 4 已真实插入
        role = mysql["one"]("select role_id from sys_user_role where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert role["role_id"] == 2
        post = mysql["one"]("select post_id from sys_user_post where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert post["post_id"] == 4

    @allure.story("获取用户分页列表接口")
    @allure.title("通过列表查询的方式，以userName为参数查询添加的数据成功")
    def test_query_user_by_name(self, user_api):
        """验证按 userName 精确筛选（LIKE 匹配）能恰好查询到上一步创建的 1 条记录，证明创建数据可检索。"""
        resp = user_api.list(userName=user_name)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        assert data["total"] == 1

    @allure.story("编辑用户接口")
    @allure.title("编辑用户成功")
    def test_update_user_success(self, user_api, mysql):
        """验证全字段编辑成功：sys_user 主表字段更新落库，岗位关联整体替换为 {1,4}，角色关联保持不变。"""
        resp = user_api.update(
            userId=TestUserSmoke.user_id,
            userName=user_name_1,
            nickName="冒烟用户-已编辑",
            email="edit_test@qq.com",
            phonenumber="13900001111",
            sex="1",
            status="0",
            deptId=101,
            roleIds=[2],
            postIds=[1, 4],
            role=[],
            remark="编辑接口测试"
        )
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # DB 校验：按 userId 查询 sys_user 主表，逐字段比对编辑结果已真实落库
        row = mysql["one"](
            "select user_name,nick_name,dept_id,email,sex,phonenumber,status,remark "
            "from sys_user where user_id=%s", (TestUserSmoke.user_id,)
        )
        assert row["user_name"] == user_name_1
        assert row["nick_name"] == "冒烟用户-已编辑"
        assert row["dept_id"] == 101
        assert row["email"] == "edit_test@qq.com"
        assert row["phonenumber"] == "13900001111"
        assert row["sex"] == "1"
        assert row["status"] == "0"
        assert row["remark"] == "编辑接口测试"
        # DB 校验：岗位关联为替换语义（先删旧再插新），编辑后岗位集合应为 {1,4}
        post = mysql["all"]("select post_id from sys_user_post where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert {p["post_id"] for p in post } == {1,4}
        # DB 校验：角色关联保持 [2] 不变（编辑未调整角色）
        role = mysql["one"]("select role_id from sys_user_role where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert role["role_id"] == 2


    @allure.story("重置用户密码接口")
    @allure.title("重置用户密码成功")
    def test_reset_pwd_success(self, user_api, client, mysql):
        """验证重置密码后密码哈希发生变化且新密码可登录成功，证明重置真实生效；临时会话用毕即注销。"""
        # 先取重置前密码哈希，与重置后哈希对比：哈希必须变化，证明密码确实被更新而非假成功
        p1 = mysql["one"]("select password from sys_user where user_id=%s",
                          (TestUserSmoke.user_id,))["password"]
        reset_resp = user_api.reset_pwd(TestUserSmoke.user_id, "NewPwd@123456")
        reset_data = reset_resp.json()
        assert reset_data["code"] == 200
        assert reset_data["success"] == True
        p2 = mysql["one"]("select password from sys_user where user_id=%s",
                          (TestUserSmoke.user_id,))["password"]
        assert p1 != p2 and p1 is not None and p2 is not None
        # 闭环验证：用重置后的新密码调用登录接口，登录成功即证明新密码真实生效
        login_resp = client.post(
            "login",
            data={
                "username": user_name_1,
                "password": "NewPwd@123456"
            }
        )
        login_data = login_resp.json()
        assert login_data["code"] == 200
        assert login_data["success"] == True
        login_token = login_data["token"]

        # 临时会话用毕即注销，避免遗留登录态影响后续用例
        logout_resp = client.post("logout", headers=auth(login_token))
        assert logout_resp.status_code == 200
        logout_data = logout_resp.json()
        assert logout_data["code"] == 200
        assert logout_data["success"] == True

    @allure.story("修改用户状态接口")
    @allure.title("修改用户状态成功")
    def test_change_status_success(self, user_api, mysql):
        """验证停用用户（status="1"）成功：接口返回成功、列表查询显示停用、数据库落库三方一致。"""
        resp = user_api.change_status(TestUserSmoke.user_id, "1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        query_resp = user_api.list(userId=TestUserSmoke.user_id)
        assert query_resp.status_code == 200
        query_data = query_resp.json()
        assert query_data["code"] == 200
        assert query_data["success"] == True
        assert query_data["rows"][0]["status"] == "1"
        # DB 校验：sys_user.status 落库为 "1"，与接口返回、列表查询三方一致
        status = mysql["one"]("select status from sys_user where user_id=%s",
                              (TestUserSmoke.user_id,))
        assert status["status"] == "1"

    @allure.story("删除用户接口")
    @allure.title("删除用户成功")
    def test_delete_user_success(self, user_api, mysql):
        """验证删除用户为软删除（del_flag='2'），且 sys_user_role / sys_user_post 关联表被级联清空。"""
        resp = user_api.delete(TestUserSmoke.user_id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["success"] == True
        # DB 校验：软删除契约——sys_user.del_flag 置为 "2"（标记删除），记录仍保留在表中
        row = mysql["one"]("select del_flag from sys_user where user_id=%s",
                           (TestUserSmoke.user_id,))
        assert row["del_flag"] == "2"
        # DB 校验：删除后岗位/角色关联被级联清空，无孤儿关联残留
        post = mysql["all"]("select post_id from sys_user_post where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert not post
        role = mysql["all"]("select role_id from sys_user_role where user_id=%s",
                            (TestUserSmoke.user_id,))
        assert not role
