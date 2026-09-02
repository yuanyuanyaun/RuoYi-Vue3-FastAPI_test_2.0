"""流程测试（系统管理端到端配置链路）测试用例。

覆盖接口：
    POST   /system/user              新增用户：全字段创建（不含角色/岗位，后续步骤单独分配）
    POST   /system/dept              新增部门：挂在集团总公司（parentId=100）下
    POST   /system/post              新增岗位
    POST   /system/menu              新增菜单：目录（M）→ 菜单（C）→ 按钮（F）三级树逐级创建
    POST   /system/role              新增角色：menuIds 挂载三级菜单权限
    PUT    /system/user              编辑用户：为已建用户分配部门与岗位
    PUT    /system/user/authRole     给用户分配角色（替换语义）
    POST   /login                    用新配置的用户登录
    GET    /getInfo                  获取当前用户信息：验证角色/部门/岗位真实生效
    POST   /logout                   退出登录
    DELETE /system/user/{id}         删除用户（清理：释放角色/岗位关联）
    DELETE /system/role/{id}         删除角色（清理：释放菜单关联）
    DELETE /system/menu/{id}         删除菜单（清理：按钮→菜单→目录倒序）
    DELETE /system/dept/{id}         删除部门（清理）
    DELETE /system/post/{id}         删除岗位（清理）

测试策略：
    - 端到端闭环：模拟管理员在系统管理中完成"建人-建部门-建岗位-建三级菜单-建角色并挂权限-
      给人配岗位部门-给人配角色-新用户登录-验证权限生效-退出-逐级清理"完整链路，
      覆盖单模块用例测不到的"多模块组合使用"集成场景（流程测试的定位）。
    - 跨用例数据依赖：各创建用例把自建资源的 ID 登记到模块级全局变量（user_id/dept_id/
      post_id/role_id/dir_id/menu_id/btn_id），后续用例接力使用这些 ID，
      因此本类用例必须按定义顺序整类执行，不可单独或乱序运行。
"""

import pytest
import allure
import time

# 模块级毫秒时间戳：所有自建数据名以同一时间戳命名，保证整类用例名称唯一、互不重名
ts = int(time.time()) * 1000
# ===== 各资源的模块级唯一名称与 ID 登记位 =====
# 名称在模块加载时一次性生成；ID 由对应"创建用例"经列表反查后登记，供后续用例接力使用
user_name = f"user_name{ts}"
user_nick = f"流程测试用户昵称{ts}"
user_id = None
role_name = f"流程测试角色{ts}"
role_key = f"key_{ts}"
role_id = None
dept_name = f"流程测试部门{ts}"
dept_id = None
post_name = f"流程测试岗位{ts}"
post_code = f"code_{ts}"
post_id = None
dir_name = f"流程测试目录{ts}"
dir_path = f"/dir_{ts}"
dir_id = None
menu_name = f"流程测试菜单{ts}"
menu_path = f"/menu_{ts}"
menu_id = None
btn_name = f"流程测试按钮{ts}"
btn_id = None
login_token = None


@pytest.mark.flow
@allure.feature("流程测试")
class TestFlow:
    """端到端流程用例：按定义顺序执行完整配置链路，跨用例共享模块级全局 ID，末尾统一按依赖倒序清理。"""

    @allure.title("创建用户")
    def test_creat_user(self, user_api):
        """正向场景：创建流程首位的测试用户，并把 userId 登记到全局变量供后续用例复用。"""
        global user_id, user_name
        # 数据直接经接口创建并登记 ID：资源生命周期由流程自身管理（贯穿整条链路，末尾统一回收）
        resp = user_api.creat(
            userName=user_name,
            nickName=user_nick,
            password="Flow@123456",
            email="flow@qq.com",
            phonenumber="17316992826",
        )
        # 断言新增用户成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # 创建响应体不含 ID，按唯一业务名反查列表登记 userId 供后续用例接力
        user_id = user_api.list(userName=user_name).json()["rows"][0]["userId"]

    @allure.title("创建部门")
    def test_creat_dept(self, dept_api):
        """正向场景：创建流程用部门，挂在集团总公司（parentId=100）下保证祖先链合法。"""
        global dept_id, dept_name
        resp = dept_api.creat(
            **{
                "deptName": dept_name,
                "parentId": 100,
                "orderNum": 9,
                "leader": "流程测试用户",
                "phone": "17316992826",
                "email": "flow@qq.com",
                "status": "0"
            }
        )
        # 断言新增部门成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        # 部门列表为非分页接口，按名称反查 data 数组登记 deptId
        dept_id = dept_api.list(deptName=dept_name).json()["data"][0]["deptId"]

    @allure.title("创建岗位")
    def test_creat_post(self, post_api):
        """正向场景：创建流程用岗位，postCode/postName 为业务唯一键。"""
        global post_id, post_name, post_code
        resp = post_api.creat(
            **{
                "postCode": post_code,
                "postName": post_name,
                "postSort": 9,
                "status": "0",
                "remark": "流程测试创建岗位"
            }
        )
        # 断言新增岗位成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        post_id = post_api.list(postName=post_name).json()["rows"][0]["postId"]

    @allure.title("创建目录，菜单，按钮")
    def test_creat_dir_menu_btn(self, menu_api):
        """正向场景：按 目录(M)→菜单(C)→按钮(F) 逐级创建三级菜单树，每级按名称反查登记 ID。

        菜单类型约定：M=目录、C=菜单、F=按钮（按钮不进路由，path/component 留空）。
        """
        global dir_name, dir_path, dir_id, menu_name, menu_path, menu_id, btn_name, btn_id
        # 1) 顶级目录：parentId=0，path 以 "/" 开头满足前端路由规范
        dir_resp = menu_api.creat(
            **{
                "menuName": dir_name,
                "parentId": 0,
                "orderNum": 1,
                "path": dir_path,
                "menuType": "M",
                "visible": "0",
                "status": "0",
                "icon": "tree",
                "remark": "流程测试目录"
            }
        )
        # 断言新增目录成功契约：业务 code 200 + 提示「新增成功」
        assert dir_resp.json()['code'] == 200
        assert dir_resp.json()["msg"] == "新增成功"
        # 菜单列表为非分页接口，按名称过滤 data 数组登记 dirId
        dir_id = [
            row["menuId"] for row in menu_api.list(
                menuName=dir_name
            ).json()["data"]
            if row["menuName"] == dir_name
        ][0]
        # 2) 目录下的菜单：component 指向具体页面，perms 为查询权限标识
        menu_resp = menu_api.creat(
            **{
                "menuName": menu_name,
                "parentId": dir_id,
                "orderNum": 1,
                "path": menu_path,
                "component": "system/user/index",
                "menuType": "C",
                "visible": "0",
                "status": "0",
                "perms": "system:smoke:list",
                "icon": "user",
                "remark": "流程测试菜单"
            }
        )
        # 断言新增菜单成功契约：业务 code 200 + 提示「新增成功」
        assert menu_resp.json()['code'] == 200
        assert menu_resp.json()["msg"] == "新增成功"
        menu_id = [
            row["menuId"] for row in menu_api.list(
                menuName=menu_name
            ).json()["data"]
            if row["menuName"] == menu_name
        ][0]
        # 3) 菜单下的按钮：menuType=F，perms 为操作权限标识，path/component 留空
        btn_resp = menu_api.creat(
            **{
                "menuName": btn_name,
                "parentId": menu_id,
                "orderNum": 1,
                "menuType": "F",
                "visible": "0",
                "status": "0",
                "perms": "system:smoke:add",
                "remark": "流程测试按钮"
            }
        )
        # 断言新增按钮成功契约：业务 code 200 + 提示「新增成功」
        assert btn_resp.json()['code'] == 200
        assert btn_resp.json()["msg"] == "新增成功"
        # 按钮 ID 登记到 btn_id（曾误赋给 menu_id 导致后续菜单权限错乱，需与上一步 menu_id 区分）
        btn_id = [
            row["menuId"] for row in menu_api.list(
                menuName=btn_name
            ).json()["data"]
            if row["menuName"] == btn_name
        ][0]

    @allure.title("创建角色并挂载三级菜单权限")
    def test_creat_role_with_menu(self, role_api):
        """正向场景：创建角色并一次性挂载目录+菜单+按钮三级权限，作为后续授权用户的数据基础。"""
        global role_id, role_name, role_key
        resp = role_api.creat(
            **{
                "roleName": role_name,
                "roleKey": role_key,
                "roleSort": 9,
                "status": "0",
                "menuIds": [dir_id, menu_id, btn_id],
                "remark": "流程测试添加数据最多角色"
            }
        )
        # 断言新增角色成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        role_id = role_api.list(roleName=role_name).json()["rows"][0]["roleId"]

    @allure.title("给用户分配岗位，部门")
    def test_user_post_dept(self, user_api):
        """正向场景：编辑用户为其挂部门与岗位。"""
        global user_id, user_name, dept_id, post_id, user_nick
        resp = user_api.update(
            userId=user_id,
            userName=user_name,
            nickName=user_nick,
            deptId=dept_id,
            postIds=[post_id],
            roleIds=[],
            role=[],
        )
        # 断言编辑成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

    @allure.title("给用户分配角色")
    def test_user_auth_role(self, user_api):
        """正向场景：通过 authRole（替换语义：先清空原角色再插入）把流程角色授予该用户。"""
        global role_id, user_id
        resp = user_api.assign_roles(user_id, str(role_id))
        # 断言分配成功契约：业务 code 200 + 成功标识为 True
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True

    @allure.title("用创建的用户登录")
    def test_login_user(self, login_api):
        """正向场景：持有完整配置（部门/岗位/角色）的新用户可正常登录，token 供后续用例复用。"""
        global login_token, user_name
        resp = login_api.login(
            username=user_name,
            password="Flow@123456"
        )
        # 断言登录成功契约：业务 code 200 + 成功标识为 True + 提示「登录成功」+ 返回 token
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()['msg'] == "登录成功"
        # 缓存登录 token：供后续 getInfo / logout 用例复用
        login_token = resp.json()['token']

    @allure.title("获取被创建用户的信息（权限/部门/角色生效验证）")
    def test_get_role_post_dept(self, login_api):
        """正向场景：getInfo 返回新用户信息，验证配置真实生效。"""
        global role_id, role_name, role_key, dept_id, user_name, user_id, login_token, user_nick
        resp = login_api.get_info(login_token)
        data = resp.json()
        # 断言接口成功契约：业务 code 200 + 成功标识为 True
        assert data["code"] == 200
        assert data["success"] == True
        # 角色生效：顶层 roles 应含本流程角色的 role_key（而非角色名）
        assert role_key in data["roles"]
        assert role_name not in data["roles"]
        # 用户基本信息一致：userId/userName/nickName 与创建时登记值相同
        assert data["user"]["userId"] == user_id
        assert data["user"]["userName"] == user_name
        assert data["user"]["nickName"] == user_nick
        # 部门生效：user 下嵌套的 dept.deptId 等于流程创建的部门
        assert data["user"]["dept"]["deptId"] == dept_id
        # 角色生效：user.roleIds 为角色 id 字符串，user.role 对象含角色 id/名称/key
        assert data["user"]["roleIds"] == str(role_id)
        assert data["user"]["role"][0]["roleId"] == role_id
        assert data["user"]["role"][0]["roleName"] == role_name
        assert data["user"]["role"][0]["roleKey"] == role_key

    @allure.title("退出登录")
    def test_logout(self, login_api):
        """正向场景：退出登录成功，流程 token 生命周期闭环（登录→使用→退出）。"""
        global login_token
        resp = login_api.logout(login_token)
        # 断言退出成功契约：业务 code 200 + 成功标识为 True + 提示「退出成功」
        assert resp.json()["code"] == 200
        assert resp.json()["success"] == True
        assert resp.json()["msg"] == "退出成功"

    @allure.title("清理用户与角色（删除菜单的前置条件）")
    def test_cleanup_user_role(self, user_api, role_api):
        """清理第 1 步：按依赖顺序删除用户与角色。
        后端校验约束（顺序颠倒会删除失败）：
            删角色前若仍有关联用户 → 「角色已分配,不能删除」（count_user_role > 0）；
            删菜单前若角色仍挂该菜单 → 「菜单已分配,不允许删除」（sys_role_menu 有记录）。
        因此必须先删用户（释放 sys_user_role）再删角色（释放 sys_role_menu），
        为下方删除三级菜单扫清前置条件。
        """
        global user_id, role_id
        user_resp = user_api.delete(user_id)
        # 断言删除用户成功契约：业务 code 200 + 提示「删除成功」
        assert user_resp.json()["code"] == 200
        assert user_resp.json()["msg"] == "删除成功"
        role_resp = role_api.delete(role_id)
        # 断言删除角色成功契约：业务 code 200 + 提示「删除成功」
        assert role_resp.json()["code"] == 200
        assert role_resp.json()["msg"] == "删除成功"

    @allure.title("删除按钮、菜单、目录成功并复查全部查不到")
    def test_delete_three_levels_menu(self, menu_api):
        """清理第 2 步：按 按钮→菜单→目录 倒序删除三级菜单，删后按名称复查全部不可见。

        子级必须先于父级删除，否则父级删除命中「存在子菜单,不允许删除」业务校验（601）。
        """
        global btn_id, dir_id, menu_id
        # 1) 删除按钮：三级中最深层，必须先删
        btn_resp = menu_api.delete(btn_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert btn_resp.json()['code'] == 200
        assert btn_resp.json()["msg"] == "删除成功"
        # 2) 删除菜单
        menu_resp = menu_api.delete(menu_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert menu_resp.json()['code'] == 200
        assert menu_resp.json()["msg"] == "删除成功"
        # 3) 删除目录
        dir_resp = menu_api.delete(dir_id)
        # 断言删除成功契约：业务 code 200 + 提示「删除成功」
        assert dir_resp.json()['code'] == 200
        assert dir_resp.json()["msg"] == "删除成功"
        # 4) 复查：按名称反查列表，三级菜单均应查不到（按钮/菜单/目录逐一验证）
        for menu_names in (btn_name, menu_name, dir_name):
            rows = menu_api.list(menuName=menu_names).json().get("data") or []
            assert all(row["menuName"] != menu_names for row in rows)

    @allure.title("清理部门与岗位")
    def test_cleanup_dept_post(self, dept_api, post_api):
        """清理第 3 步：删除部门与岗位（无下级节点/无引用，顺序自由）。"""
        global dept_id, post_id
        dept_resp = dept_api.delete(dept_id)
        # 断言删除部门成功契约：业务 code 200 + 提示「删除成功」
        assert dept_resp.json()["code"] == 200
        assert dept_resp.json()["msg"] == "删除成功"
        post_resp = post_api.delete(post_id)
        # 断言删除岗位成功契约：业务 code 200 + 提示「删除成功」
        assert post_resp.json()["code"] == 200
        assert post_resp.json()["msg"] == "删除成功"
