"""
UserApi：用户模块接口封装。

覆盖接口（统一前缀 /system/user）：
    查询类：list（分页列表）/ deptTree（用户可见部门树）/ detail（详情；
            不传 id 时返回岗位+角色下拉数据）/ profile（当前用户个人信息）/
            authRole/{id}（指定用户已分配角色列表）
    管理类：creat / update / delete（批量逗号分隔）/ resetPwd（重置密码）/
            changeStatus（启用停用）
    个人信息：profile(PUT)（修改个人信息）/ profile/updatePwd（修改个人密码）
    角色分配：authRole（PUT，替换语义：先清空原分配再插入新分配）

设计要点：
    - 构造时传入 token，统一组装 Authorization 头，用例层不再关心认证细节
    - detail(user_id=None)：不传 id 请求 "system/user/"（返回岗位+角色下拉列表），
      传 id 请求 "system/user/{id}" 返回详情
    - assign_roles 为替换语义（roleIds 为空即清空用户全部角色），
      与角色模块 selectAll 的追加语义相反
"""
class UserApi:
    """用户模块接口封装：URL 与认证头统一集中管理，用例层仅传业务参数。"""

    def __init__(self, client, token):
        self.client = client
        # 统一组装认证头：用户模块所有接口均需携带登录后获取的 token
        self.headers = {
            "Authorization": f"Bearer {token}"
        }

    # ===== 查询类接口：分页列表 / 部门树 / 详情 / 个人信息 / 已分配角色 =====
    def list(self, **params):
        """用户分页列表：支持 userName/status/deptId 筛选与分页参数透传。"""
        return self.client.get(
            "system/user/list",
            headers=self.headers,
            params=params
        )

    def dept_tree(self):
        """用户可见部门树（部门选择器数据来源）。"""
        return self.client.get(
            "system/user/deptTree",
            headers=self.headers
        )

    def detail(self, user_id=None):
        """用户详情；user_id 为 None 时请求下拉列表接口（岗位+角色下拉数据），否则请求指定用户详情。"""
        if user_id is None:
            return self.client.get(
                "system/user/",
                headers=self.headers
            )
        return self.client.get(
            f"system/user/{user_id}",
            headers=self.headers
        )

    def profile(self):
        """当前登录用户个人信息（个人中心展示数据）。"""
        return self.client.get(
            "system/user/profile",
            headers=self.headers
        )

    def allocated_roles(self, user_id):
        """指定用户已分配角色列表（角色分配页面数据源）。"""
        return self.client.get(
            f"system/user/authRole/{user_id}",
            headers=self.headers
        )

    # ===== 管理类接口：新增 / 编辑 / 删除 / 重置密码 / 启用停用 =====
    def creat(self, **data):
        """新增用户：data 为用户字段字典（含 userName/nickName/password 等必填项）。"""
        return self.client.post(
            "system/user",
            headers=self.headers,
            json=data
        )

    def update(self, **data):
        """编辑用户：data 需含 userId 及待修改字段。"""
        return self.client.put(
            "system/user",
            headers=self.headers,
            json=data
        )

    def delete(self, user_ids):
        """删除用户：支持逗号分隔的用户 id 列表批量删除。"""
        return self.client.delete(
            f"system/user/{user_ids}",
            headers=self.headers
        )

    def reset_pwd(self, user_id, password):
        """重置指定用户密码：后端校验新密码强度后落库。"""
        return self.client.put(
            "system/user/resetPwd",
            headers=self.headers,
            json={
                "userId": user_id,
                "password": password
            }
        )

    def change_status(self, user_id, status):
        """修改用户状态：status 为 "0"（正常）/ "1"（停用）。"""
        return self.client.put(
            "system/user/changeStatus",
            headers=self.headers,
            json={
                "userId": user_id,
                "status": status
            }
        )

    # ===== 个人信息类接口：修改资料 / 修改密码 =====
    def update_profile(self, **data):
        """修改当前登录用户个人信息。"""
        return self.client.put(
            "system/user/profile",
            headers=self.headers,
            json=data
        )

    def update_pwd(self, old_password, new_password):
        """修改当前登录用户密码：需同时提供原密码与新密码。"""
        return self.client.put(
            "system/user/profile/updatePwd",
            headers=self.headers,
            json={
                "oldPassword": old_password,
                "newPassword": new_password
            }
        )

    # ===== 角色分配类接口：替换语义，先清空再插入 =====
    def assign_roles(self, user_id, role_ids):
        """给用户分配角色（query 参数）：替换语义——roleIds 为空即清空用户全部角色。"""
        return self.client.put(
            "system/user/authRole",
            headers=self.headers,
            params={
                "userId": user_id,
                "roleIds": role_ids
            }
        )
